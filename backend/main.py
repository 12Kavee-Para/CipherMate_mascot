import hashlib, json, os, re, secrets, threading, time
from collections import defaultdict, deque
from pathlib import Path
from contextlib import asynccontextmanager
from urllib.parse import quote
from fastapi import FastAPI, Depends, Header, Request, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from .schemas import Proposal, Approval, Chat, PrivateEntry
from .store import Store, Fault, MAX_FILE
from .chat import Planner, ROOT

PREFIX='/api/ciphermate'
class BodyLimit:
    def __init__(self, app): self.app=app
    async def __call__(self, scope, receive, send):
        if scope['type']!='http': return await self.app(scope,receive,send)
        limit=MAX_FILE if scope['path']==PREFIX+'/files' and scope['method']=='POST' else 32768
        chunks=[]; size=0
        while True:
            event=await receive()
            if event['type']=='http.disconnect': return
            data=event.get('body',b''); size+=len(data)
            if size>limit:
                return await JSONResponse({'error_code':'REQUEST_TOO_LARGE'},413)(scope,receive,send)
            chunks.append(data)
            if not event.get('more_body',False): break
        sent=False
        async def replay():
            nonlocal sent
            if sent: return await receive()
            sent=True; return {'type':'http.request','body':b''.join(chunks),'more_body':False}
        async def secure_send(event):
            if event['type']=='http.response.start':
                event.setdefault('headers',[]).extend([(b'cache-control',b'no-store'),(b'x-content-type-options',b'nosniff'),(b'referrer-policy',b'no-referrer'),(b'x-frame-options',b'DENY'),(b'content-security-policy',b"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")])
            await send(event)
        return await self.app(scope,replay,secure_send)

def create_app(store=None, users=None, planner=None, local_demo=None):
    # No default passwords or keys. Production configuration is injected by the operator.
    if users is None: users=json.loads(os.environ['CM_USERS_JSON'])
    if not isinstance(users,dict) or not users or len(users)>100 or any(not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',u) or not isinstance(t,str) or len(t)<32 for u,t in users.items()) or len(set(users.values()))!=len(users): raise RuntimeError('CM_USERS_JSON must map unique account IDs to unique strong tokens')
    token_hashes={u:hashlib.sha256(t.encode()).digest() for u,t in users.items()}
    # Opt-in convenience for a direct, loopback-only developer session.
    # Never enable on a public server or behind a reverse proxy.
    if local_demo is None: local_demo=os.getenv('CM_LOCAL_DEMO')=='1'
    if local_demo and set(users)!={'owner'}:
        raise RuntimeError('Local demo requires exactly one owner account')
    if store is None: store=Store(os.environ['CM_DB_PATH'],os.environ['CM_MASTER_KEY'],os.getenv('CM_LAB_LINUX')=='1')
    if planner is None:
        if os.getenv('OPENROUTER_API_KEY'):
            planner = Planner(os.environ['OPENROUTER_API_KEY'], os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini'), provider='openrouter')
        else:
            planner = Planner(os.getenv('DEEPSEEK_API_KEY', ''), os.getenv('CM_MODEL', 'deepseek-flash'))
    @asynccontextmanager
    async def lifespan(app):
        yield
        if hasattr(planner,'client'): planner.client.close()
    app=FastAPI(title='CipherMate private MVP',version='1.0.0',lifespan=lifespan,docs_url=None,redoc_url=None,openapi_url=None)
    app.add_middleware(BodyLimit)
    times=defaultdict(deque); mutex=threading.Lock(); slots=threading.BoundedSemaphore(4)
    def identity(request:Request, authorization:str|None=Header(default=None)):
        if authorization is None and local_demo:
            host=request.headers.get('host','').lower()
            # Reject DNS rebinding, forwarded traffic and cross-origin requests.
            if (not request.client or request.client.host not in ('127.0.0.1','::1')
                or not re.fullmatch(r'(?:127\.0\.0\.1|localhost|\[::1\])(?::[0-9]{1,5})?',host)
                or any(k=='forwarded' or k.startswith('x-forwarded-') or k in ('x-real-ip','via') for k in request.headers.keys())
                or request.headers.get('sec-fetch-site') in ('cross-site','same-site')):
                raise Fault('UNAUTHENTICATED',401)
            origin=request.headers.get('origin')
            expected='http://'+host
            if (origin is not None and origin!=expected) or (request.method not in ('GET','HEAD','OPTIONS') and origin!=expected):
                raise Fault('ORIGIN_NOT_ALLOWED',403)
            return 'owner'
        if not authorization or not authorization.startswith('Bearer ') or len(authorization)>512: raise Fault('UNAUTHENTICATED',401)
        digest=hashlib.sha256(authorization[7:].encode()).digest()
        match=None
        for u,h in token_hashes.items():
            if secrets.compare_digest(digest,h): match=u
        if match is None: raise Fault('UNAUTHENTICATED',401)
        return match
    def rate(u):
        now=time.monotonic()
        with mutex:
            q=times[u]
            while q and now-q[0]>=60: q.popleft()
            if len(q)>=10: raise Fault('CHAT_RATE_LIMIT',429)
            q.append(now)
    @app.exception_handler(Fault)
    async def fault_handler(req,exc): return JSONResponse({'error_code':exc.code},status_code=exc.status)
    @app.exception_handler(RequestValidationError)
    async def validation_handler(req,exc): return JSONResponse({'error_code':'INVALID_REQUEST'},422)
    @app.exception_handler(Exception)
    async def unexpected(req,exc): return JSONResponse({'error_code':'INTERNAL_ERROR'},500)
    @app.get(PREFIX+'/health')
    def health(): return {'status':'ok'}
    @app.get(PREFIX+'/capabilities')
    def capabilities(u=Depends(identity)): return {'schema_version':'1.0','operations':store.capabilities(),'chat_mode':planner.provider if getattr(planner,'key',None) else 'offline','file_limit_bytes':MAX_FILE}
    @app.post(PREFIX+'/chat')
    def chat(req:Chat,u=Depends(identity)):
        if re.search(r'\bsk-or-v1-[A-Za-z0-9_-]+', req.message):
            raise Fault('USE_PRIVATE_VAULT_ENTRY', 422)
        rate(u)
        if not slots.acquire(blocking=False): raise Fault('MODEL_BUSY',503)
        try: reply=planner.plan(req.message,store.capabilities())
        finally: slots.release()
        if reply.decision=='propose':
            if reply.proposal is None: raise Fault('INVALID_MODEL_OUTPUT',502)
            # Never persist model reason, text, or postcondition claims. Never execute a model-proposed mutation without trusted approval.
            return {'decision':'propose','message':'Validated operation. Check the job status and exact parameters below.','job':store.submit(u,reply.proposal)}
        return {'decision':reply.decision,'message':reply.message,'job':None,'notice':'No operation was executed.'}
    @app.post(PREFIX+'/jobs')
    def jobs(p:Proposal,u=Depends(identity),idempotency_key:str|None=Header(default=None,max_length=100)):
        return store.submit(u,p,idempotency_key)
    @app.get(PREFIX+'/jobs/{job_id}')
    def status(job_id:str,u=Depends(identity)): return store.status(u,job_id)
    @app.post(PREFIX+'/jobs/{job_id}/approval')
    def approval(job_id:str,p:Approval,u=Depends(identity)): return store.approve(u,job_id,p)
    @app.post(PREFIX+'/files',status_code=201)
    async def upload(request:Request,name:str=Query(min_length=1,max_length=200),u=Depends(identity)):
        if request.headers.get('content-type','').split(';')[0]!='application/octet-stream': raise Fault('EXPECTED_OCTET_STREAM',415)
        data=await request.body()
        return await run_in_threadpool(store.upload,u,name,data)
    @app.get(PREFIX+'/download')
    def download(name:str=Query(min_length=1,max_length=200),u=Depends(identity)):
        return Response(store.download(u,name),media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name.split('/')[-1],safe='')})
    @app.post(PREFIX+'/vault/entry',status_code=201)
    def vault_entry(entry:PrivateEntry,u=Depends(identity)): return store.private_entry(u,entry)
    @app.put(PREFIX+'/vault/entry')
    def vault_update(entry:PrivateEntry,u=Depends(identity)): return store.private_entry(u,entry,replace=True)
    @app.get(PREFIX+'/history')
    def history(u=Depends(identity)): return {'events':store.history(u)}
    @app.get('/',include_in_schema=False)
    def home(): return RedirectResponse('/ciphermate/',status_code=307)
    app.mount('/ciphermate',StaticFiles(directory=ROOT/'frontend',html=True),name='ciphermate')
    return app
