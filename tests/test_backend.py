import json, sqlite3, time, hashlib
from pathlib import Path
import httpx, pytest
from fastapi.testclient import TestClient
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from backend.main import create_app
from backend.store import Store, MAGIC, MAX_FILE
from backend.chat import Planner

A={'Authorization':'Bearer '+'a'*48}; B={'Authorization':'Bearer '+'b'*48}; URL='/api/ciphermate'
@pytest.fixture
def lab(tmp_path):
    path=tmp_path/'private'; path.mkdir(mode=0o700); master=Fernet.generate_key().decode(); db=path/'state.sqlite3'; store=Store(db,master)
    with TestClient(create_app(store,{'alice':'a'*48,'bob':'b'*48},Planner())) as client:
        yield client,store,master

def put(c,n,data=b'hello world',h=A):
    return c.post(URL+'/files',params={'name':n},content=data,headers=h|{'Content-Type':'application/octet-stream'})
def get(c,n,h=A): return c.get(URL+'/download',params={'name':n},headers=h)
def proposal(op,p=None):
    prefix=op.split('.')[0]; return {'agent':{'file':'file-agent','crypto':'crypto-agent','vault':'vault-agent','linux':'linux-agent','script':'linux-agent','history':'ciphermate'}[prefix],'operation':op,'parameters':p or {}}
def job(c,op,p=None,h=A,idem=None):
    return c.post(URL+'/jobs',json=proposal(op,p),headers=h|({'Idempotency-Key':idem} if idem else {}))
def approve(c,j,yes=True,h=A,digest=None):
    return c.post(URL+'/jobs/'+j['job_id']+'/approval',json={'approve':yes,'plan_digest':digest or j['plan_digest']},headers=h)
def done(c,op,p=None,h=A):
    r=job(c,op,p,h); assert r.status_code==200,r.text; j=r.json()
    if j['status']=='AWAITING_APPROVAL': j=approve(c,j,h=h).json()
    assert j['status']=='COMPLETED',j
    return j['result']
def entry(c,label,kind,value,method='post'):
    return getattr(c,method)(URL+'/vault/entry',json={'key_ref':label,'kind':kind,'value':value},headers=A)

def test_auth(lab):
    c,_,_=lab; assert c.get(URL+'/health').status_code==200; assert c.get(URL+'/capabilities').status_code==401; assert c.get(URL+'/capabilities',headers=A).status_code==200

def test_upload_and_scope(lab):
    c,_,_=lab; assert put(c,'docs/a.txt').status_code==201; assert get(c,'docs/a.txt').content==b'hello world'; assert get(c,'docs/a.txt',B).status_code==404; assert done(c,'file.list',h=B)['files']==[]

def test_paths(lab):
    c,_,_=lab
    for n in ('../etc/passwd','/etc/passwd','a/../../b','a\\b','.env','a//b','a/..'):
        assert put(c,n).status_code==400,n
    assert job(c,'crypto.hash',{'source':'../outside'}).status_code==422

def test_file_size(lab):
    c,_,_=lab; assert put(c,'a',b'x'*(MAX_FILE+1)).status_code==413

def test_duplicates_search(lab):
    c,_,_=lab; put(c,'a.txt'); put(c,'b.txt'); put(c,'c.pdf',b'other'); assert done(c,'file.duplicates')['groups']==[['a.txt','b.txt']]; assert len(done(c,'file.search',{'query':'.txt'})['files'])==2

def test_hash_compare(lab):
    c,_,_=lab; put(c,'a'); digest=hashlib.sha256(b'hello world').hexdigest(); assert done(c,'crypto.hash',{'source':'a'})['sha256']==digest; assert done(c,'crypto.compare',{'source':'a','expected_sha256':digest})['matches_supplied_reference']; assert not done(c,'crypto.compare',{'source':'a','expected_sha256':'0'*64})['matches_supplied_reference']

def test_approval_no_overwrite_and_replay(lab):
    c,_,_=lab; put(c,'a'); j=job(c,'file.copy',{'source':'a','destination':'b'}).json(); assert j['status']=='AWAITING_APPROVAL'; assert get(c,'b').status_code==404; assert approve(c,j,h=B).status_code==404; assert approve(c,j,digest='0'*64).status_code==409; assert approve(c,j).json()['status']=='COMPLETED'; assert approve(c,j).status_code==409; assert put(c,'b',b'other').status_code==409; assert get(c,'b').content==b'hello world'

def test_reject_expire(lab):
    c,s,_=lab; put(c,'a'); j=job(c,'file.copy',{'source':'a','destination':'b'}).json(); assert approve(c,j,False).json()['status']=='REJECTED'; j=job(c,'file.copy',{'source':'a','destination':'b'}).json();
    with s.tx() as db: db.execute('UPDATE jobs SET expires=? WHERE id=?',(time.time()-1,j['job_id']))
    assert approve(c,j).json()['error_code']=='APPROVAL_EXPIRED'; assert get(c,'b').status_code==404

def test_destination_race(lab):
    c,_,_=lab; put(c,'a'); j=job(c,'file.copy',{'source':'a','destination':'b'}).json(); put(c,'b',b'keep'); assert approve(c,j).json()['error_code']=='RESOURCE_CHANGED'; assert get(c,'b').content==b'keep'

def test_source_change(lab):
    c,_,_=lab; put(c,'a'); j=job(c,'file.copy',{'source':'a','destination':'b'}).json(); done(c,'file.delete',{'source':'a'}); put(c,'a',b'changed'); assert approve(c,j).json()['error_code']=='RESOURCE_CHANGED'; assert get(c,'b').status_code==404

def test_idempotency(lab):
    c,_,_=lab; put(c,'a'); p={'source':'a','destination':'b'}; j=job(c,'file.copy',p,idem='request-1').json(); assert job(c,'file.copy',p,idem='request-1').json()['job_id']==j['job_id']; assert job(c,'file.copy',{'source':'a','destination':'c'},idem='request-1').status_code==409

def test_round_trip(lab):
    c,_,_=lab; put(c,'a'); done(c,'crypto.key_create',{'key_ref':'lab','kind':'fernet'}); done(c,'crypto.encrypt',{'source':'a','destination':'a.cm','key_ref':'lab'}); assert get(c,'a.cm').content.startswith(MAGIC); done(c,'crypto.decrypt',{'source':'a.cm','destination':'out','key_ref':'lab'}); assert get(c,'out').content==get(c,'a').content

def test_wrong_key_tampered(lab):
    c,_,_=lab; key=Fernet.generate_key(); entry(c,'right','fernet',key.decode()); entry(c,'wrong','fernet',Fernet.generate_key().decode()); enc=MAGIC+Fernet(key).encrypt(b'example'); put(c,'good',enc); put(c,'bad',enc[:-5]+b'AAAAA');
    for source,k in [('good','wrong'),('bad','right')]:
        j=job(c,'crypto.decrypt',{'source':source,'destination':'out','key_ref':k}).json(); assert approve(c,j).json()['status']=='FAILED'; assert get(c,'out').status_code==404

def test_key_changed(lab):
    c,_,_=lab; put(c,'a'); entry(c,'lab','fernet',Fernet.generate_key().decode()); j=job(c,'crypto.encrypt',{'source':'a','destination':'out','key_ref':'lab'}).json(); assert entry(c,'lab','fernet',Fernet.generate_key().decode(),'put').status_code==200; assert approve(c,j).json()['error_code']=='RESOURCE_CHANGED'

def test_sign_and_verify(lab):
    c,_,_=lab; put(c,'a'); put(c,'modified',b'changed'); done(c,'crypto.key_create',{'key_ref':'sign','kind':'ed25519'}); done(c,'crypto.public_key',{'key_ref':'sign','destination':'pub.pem'}); done(c,'crypto.sign',{'source':'a','destination':'a.sig','key_ref':'sign'}); p={'source':'a','signature':'a.sig','public_key':'pub.pem'}; assert done(c,'crypto.verify',p)['valid']; assert not done(c,'crypto.verify',p|{'source':'modified'})['valid']

def test_unknown_format(lab):
    c,_,_=lab; put(c,'a',b'unknown'); assert done(c,'crypto.identify_format',{'source':'a'})['format']=='UNKNOWN'

def test_vault_and_disk_no_plaintext(lab):
    c,s,_=lab; secret='SYNTHETIC-TOKEN-DO-NOT-LOG'; assert entry(c,'test','credential',secret).status_code==201; assert entry(c,'test','credential',secret).status_code==409; assert secret not in str(done(c,'vault.list')); assert secret not in c.get(URL+'/history',headers=A).text; put(c,'data',secret.encode()); assert secret.encode() not in s.path.read_bytes(); done(c,'vault.delete',{'key_ref':'test'}); assert done(c,'vault.list')['credentials']==[]

def test_validation_no_secret_echo(lab):
    c,_,_=lab; sentinel='sensitive-value-123'; r=c.post(URL+'/vault/entry',json={'key_ref':'x','kind':'invalid','value':sentinel},headers=A); assert r.status_code==422; assert sentinel not in r.text; assert job(c,'vault.store',{'key_ref':'x','value':sentinel}).status_code==422; assert job(c,'file.list',{'unexpected':sentinel}).status_code==422

def test_move_rename_delete(lab):
    c,_,_=lab; put(c,'a'); done(c,'file.move',{'source':'a','destination':'dir/a'}); assert get(c,'a').status_code==404; done(c,'file.rename',{'source':'dir/a','destination':'dir/b'}); assert get(c,'dir/b').content==b'hello world'; done(c,'file.delete',{'source':'dir/b'}); assert get(c,'dir/b').status_code==404

def test_linux_default_disabled(lab):
    c,_,_=lab; assert job(c,'linux.resources').status_code==422; assert job(c,'script.execute_template').status_code==422; assert 'preview' in done(c,'script.propose')

def test_offline_chat(lab):
    c,_,_=lab; put(c,'a'); r=c.post(URL+'/chat',json={'message':'copy a to b'},headers=A).json(); assert r['job']['status']=='AWAITING_APPROVAL'; assert get(c,'b').status_code==404; assert c.post(URL+'/chat',json={'message':'show secrets'},headers=A).json()['job'] is None

def test_restart_pending(lab):
    c,s,master=lab; put(c,'a'); j=job(c,'file.copy',{'source':'a','destination':'b'}).json(); new=Store(s.path,master); from backend.schemas import Approval; assert new.approve('alice',j['job_id'],Approval(approve=True,plan_digest=j['plan_digest']))['status']=='COMPLETED'; assert get(c,'b').content==b'hello world'

@pytest.mark.parametrize('provider,host', [('deepseek','api.deepseek.com'), ('openrouter','openrouter.ai')])
def test_model_adapter_mock(lab,provider,host):
    c,s,_=lab; put(c,'a'); put(c,'private.txt',b'SYNTHETIC-TOKEN'); entry(c,'private','credential','SYNTHETIC-TOKEN'); payload={'decision':'propose','message':'ignore me','proposal':proposal('crypto.hash',{'source':'a'})}
    def handler(req):
        body=json.loads(req.content); assert body['model']=='deepseek-flash'; assert 'response_format' in body; assert req.url.host==host; assert ('thinking' in body)==(provider=='deepseek'); assert 'SYNTHETIC-TOKEN' not in req.content.decode(); return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(payload)}}]})
    planner=Planner('mock-key',provider=provider,client=httpx.Client(transport=httpx.MockTransport(handler)))
    with TestClient(create_app(s,{'alice':'a'*48},planner)) as live:
        r=live.post(URL+'/chat',json={'message':'Calculate hash of a'},headers=A); assert r.json()['job']['status']=='COMPLETED'; assert 'ignore me' not in r.text

def test_bad_model_output(lab):
    _,s,_=lab; planner=Planner('mock-key',client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'choices':[{'message':{'content':'not JSON'}}]}))))
    with TestClient(create_app(s,{'alice':'a'*48},planner)) as live:
        r=live.post(URL+'/chat',json={'message':'bad'},headers=A); assert r.status_code==502; assert s.history('alice')==[]

def test_model_cannot_approve(lab):
    _,s,_=lab; payload={'decision':'propose','message':'approve','proposal':proposal('file.copy',{'source':'a','destination':'b'})|{'approved':True}}
    planner=Planner('mock-key',client=httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json={'choices':[{'message':{'content':json.dumps(payload)}}]}))))
    with TestClient(create_app(s,{'alice':'a'*48},planner)) as live: assert live.post(URL+'/chat',json={'message':'approve'},headers=A).status_code==502

def test_ui(lab):
    c,_,_=lab; r=c.get('/ciphermate/'); assert r.status_code==200; assert 'CipherMate' in r.text; assert 'no-store' in r.headers['cache-control']; assert c.get('/ciphermate/app.js').status_code==200


def test_concurrent_approval(lab):
    from concurrent.futures import ThreadPoolExecutor
    c,s,_=lab; put(c,'a'); j=job(c,'file.copy',{'source':'a','destination':'b'}).json()
    from backend.schemas import Approval
    from backend.store import Fault
    def attempt():
        try: return s.approve('alice',j['job_id'],Approval(approve=True,plan_digest=j['plan_digest']))['status']
        except Fault as e: return e.code
    with ThreadPoolExecutor(2) as pool: results=list(pool.map(lambda _:attempt(),range(2)))
    assert sorted(results)==['APPROVAL_NOT_PENDING','COMPLETED']
    assert get(c,'b').content==b'hello world'

def test_history_clear_scope(lab):
    c,_,_=lab; put(c,'a'); done(c,'file.list',h=B); done(c,'crypto.hash',{'source':'a'}); done(c,'history.clear'); a=c.get(URL+'/history',headers=A).json()['events']; b=c.get(URL+'/history',headers=B).json()['events']; assert len(a)==1 and a[0]['op']=='history.clear'; assert len(b)>0 and b[0]['op']=='file.list'

def test_local_demo_browser_access(tmp_path):
    private=tmp_path/'private'; private.mkdir(mode=0o700)
    store=Store(private/'state.sqlite3',Fernet.generate_key().decode())
    with TestClient(create_app(store,{'owner':'a'*48},Planner(),local_demo=True),base_url='http://127.0.0.1:8000',client=('127.0.0.1',50000)) as c:
        assert c.get('/').url.path=='/ciphermate/'
        assert c.get(URL+'/capabilities').status_code==200
        assert c.post(URL+'/chat',json={'message':'list files'},headers={'Origin':'http://127.0.0.1:8000','Sec-Fetch-Site':'same-origin'}).status_code==200
        assert c.post(URL+'/chat',json={'message':'list files'}).status_code==403
        assert c.post(URL+'/chat',json={'message':'list files'},headers={'Origin':'https://evil.example'}).status_code==403
        for headers in ({'Host':'evil.example'},{'X-Forwarded-For':'127.0.0.1'},{'Forwarded':'for=127.0.0.1'},{'Sec-Fetch-Site':'cross-site'},{'Authorization':'Bearer wrong'}):
            assert c.get(URL+'/capabilities',headers=headers).status_code==401
    with TestClient(create_app(store,{'owner':'a'*48},Planner(),local_demo=True),base_url='http://127.0.0.1:8000',client=('192.0.2.1',50000)) as c:
        assert c.get(URL+'/capabilities').status_code==401

def test_local_demo_off_keeps_auth(tmp_path):
    private=tmp_path/'private'; private.mkdir(mode=0o700)
    store=Store(private/'state.sqlite3',Fernet.generate_key().decode())
    with TestClient(create_app(store,{'owner':'a'*48},Planner(),local_demo=False),base_url='http://127.0.0.1:8000',client=('127.0.0.1',50000)) as c:
        assert c.get(URL+'/capabilities').status_code==401
        assert c.get(URL+'/capabilities',headers=A).status_code==200


def test_branded_ui_and_assets(lab):
    c,_,_=lab; html=c.get('/ciphermate/').text
    for control in ('chatMode','connectMode','restoreChat','chatWidget','connectDialog','filesDialog','vaultDialog','historyDialog'):
        assert f'id="{control}"' in html
    assert 'voiceDialog' not in html and 'SpeechRecognition' not in c.get('/ciphermate/app.js').text
    assert 'Private beta' not in html and 'Access token' not in html
    for asset in ('mascot.webp','brand.webp'):
        res=c.get('/ciphermate/assets/'+asset); assert res.status_code==200 and res.headers['content-type']=='image/webp' and res.content[:4]==b'RIFF'
    assert c.get('/ciphermate/style.css').status_code==200


def test_offline_chat_crypto_commands(lab):
    c,_,_=lab; put(c,'report.txt')
    def run(msg,mutation=False):
        r=c.post(URL+'/chat',json={'message':msg},headers=A); assert r.status_code==200,r.text; j=r.json()['job']
        if mutation:
            assert j['status']=='AWAITING_APPROVAL'; j=approve(c,j).json()
        assert j['status']=='COMPLETED',j
        return j['result']
    run('create key fernet lab-key',True)
    run('encrypt report.txt to report.cm using lab-key',True)
    run('decrypt report.cm to decoded.txt using lab-key',True)
    assert get(c,'decoded.txt').content==get(c,'report.txt').content
    run('create key ed25519 lab-sign-key',True)
    run('public-key lab-sign-key to pub.pem',True)
    run('sign report.txt to report.sig using lab-sign-key',True)
    assert run('verify report.txt with report.sig using pub.pem')['valid']
    assert run('compare report.txt to '+hashlib.sha256(b'hello world').hexdigest())['matches_supplied_reference']


def test_decrypted_binary_access(lab):
    client, _, _ = lab
    payload = bytes(range(256))
    key = Fernet.generate_key()
    encrypted = MAGIC + Fernet(key).encrypt(payload)
    entry(client, 'sample', 'fernet', key.decode())
    put(client, 'sample.cm', encrypted)
    request = {'message': 'decrypt sample.cm to recovered.bin using sample'}
    pending = client.post(URL+'/chat', json=request, headers=A).json()['job']
    assert pending['status'] == 'AWAITING_APPROVAL'
    assert get(client, 'recovered.bin').status_code == 404
    assert approve(client, pending, h=B).status_code == 404
    assert approve(client, pending).json()['status'] == 'COMPLETED'
    output = get(client, 'recovered.bin')
    assert output.content == payload
    assert 'attachment' in output.headers['content-disposition']
    assert get(client, 'sample.cm').content == encrypted
    assert get(client, 'recovered.bin', B).status_code == 404


def test_chat_blocks_openrouter_key_before_planning(lab, monkeypatch):
    client, _, _ = lab
    monkeypatch.setattr(Planner, 'plan', lambda *args: pytest.fail('credential reached planner'))
    sample = 'sk-or-v1-' + 'x' * 64
    response = client.post(URL+'/chat', headers=A, json={'message': 'use '+sample})
    assert response.json() == {'error_code': 'USE_PRIVATE_VAULT_ENTRY'}
    assert sample not in response.text


def test_encryption_expansion_preserves_original(lab):
    client, _, _ = lab
    source = b'x' * MAX_FILE
    assert put(client, 'limit.bin', source).status_code == 201
    done(client, 'crypto.key_create', {'kind': 'fernet', 'key_ref': 'sample'})
    pending = job(client, 'crypto.encrypt', {
        'source': 'limit.bin', 'destination': 'limit.cm', 'key_ref': 'sample'
    }).json()
    assert approve(client, pending).json()['error_code'] == 'FILE_TOO_LARGE'
    assert get(client, 'limit.cm').status_code == 404
    assert get(client, 'limit.bin').content == source


def test_decrypt_requires_key_and_supported_envelope(lab):
    client, _, _ = lab
    source = b'unknown encrypted format'
    put(client, 'opaque.bin', source)
    params = {'source': 'opaque.bin', 'destination': 'decoded', 'key_ref': 'sample'}
    assert job(client, 'crypto.decrypt', params).status_code == 404
    done(client, 'crypto.key_create', {'kind': 'fernet', 'key_ref': 'sample'})
    pending = job(client, 'crypto.decrypt', params).json()
    assert approve(client, pending).json()['status'] == 'FAILED'
    assert get(client, 'decoded').status_code == 404
    assert get(client, 'opaque.bin').content == source
