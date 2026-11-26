"""Private, small-file MVP. SQLite is both the logical filesystem and state store."""
import base64, hashlib, json, os, platform, secrets, sqlite3, time, uuid
from contextlib import contextmanager
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.exceptions import InvalidSignature
import psutil
from .schemas import REGISTRY, check_name
from pydantic import ValidationError

MAX_FILE = 5*1024*1024
QUOTA = 50*1024*1024
MAX_FILES = 200
MAGIC = b'CM-FERNET-1\n'
SCRIPT = 'uname -s\nfree -m\ndf -h /\n' # illustrative only; execution uses fixed Python calls

def sha(data): return hashlib.sha256(data).hexdigest()
def canonical(data): return json.dumps(data, sort_keys=True, separators=(',',':'))
class Fault(Exception):
    def __init__(self, code, status=400): self.code, self.status = code,status

class Store:
    def __init__(self, path, master, lab_linux=False):
        self.path=Path(path).resolve(); self.lab_linux=lab_linux
        self._caps={k:{'parameters':v[0].model_json_schema(),'approval_required':v[1],'agent':v[2]} for k,v in REGISTRY.items() if lab_linux or not (k.startswith('linux.') or k=='script.execute_template')}
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        if self.path.parent.stat().st_mode & 0o077: raise RuntimeError('Data directory must be private (chmod 700)')
        raw=base64.b64decode(master,altchars=b'-_',validate=True)
        if len(raw)!=32: raise RuntimeError('CM_MASTER_KEY must encode 32 random bytes')
        def cipher(info): return Fernet(base64.urlsafe_b64encode(HKDF(algorithm=hashes.SHA256(),length=32,salt=None,info=info).derive(raw)))
        self.files=cipher(b'ciphermate/files/v1'); self.vault=cipher(b'ciphermate/vault/v1')
        with self.tx() as c:
            c.execute('PRAGMA journal_mode')
            c.executescript('''
            CREATE TABLE IF NOT EXISTS files(owner TEXT,name TEXT,blob BLOB,sha TEXT,size INTEGER,version TEXT,created REAL,PRIMARY KEY(owner,name));
            CREATE TABLE IF NOT EXISTS vault(owner TEXT,label TEXT,kind TEXT,blob BLOB,version TEXT,PRIMARY KEY(owner,label));
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,owner TEXT,op TEXT,params TEXT,snapshot TEXT,digest TEXT,status TEXT,created REAL,expires REAL,result TEXT,error TEXT,idem TEXT,UNIQUE(owner,idem));
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,owner TEXT,job TEXT,op TEXT,status TEXT,at REAL);
            ''')
        os.chmod(self.path,0o600)
    @contextmanager
    def tx(self):
        c=sqlite3.connect(self.path, timeout=10, isolation_level=None)
        c.row_factory=sqlite3.Row
        try:
            c.execute('BEGIN IMMEDIATE'); yield c; c.commit()
        except BaseException: c.rollback(); raise
        finally: c.close()
    def capabilities(self):
        return self._caps
    def _file(self,c,u,n):
        row=c.execute('SELECT * FROM files WHERE owner=? AND name=?',(u,n)).fetchone()
        if not row: raise Fault('FILE_NOT_FOUND',404)
        return row
    def _read(self,c,u,n):
        r=self._file(c,u,n)
        try: data=self.files.decrypt(r['blob'])
        except InvalidToken: raise Fault('STORAGE_AUTHENTICATION_FAILED',500)
        if sha(data)!=r['sha'] or len(data)!=r['size']: raise Fault('STORAGE_INTEGRITY_FAILED',500)
        return data
    def _put(self,c,u,n,data):
        check_name(n)
        if len(data)>MAX_FILE: raise Fault('FILE_TOO_LARGE',413)
        count,size=c.execute('SELECT count(*),coalesce(sum(size),0) FROM files WHERE owner=?',(u,)).fetchone()
        if count>=MAX_FILES or size+len(data)>QUOTA: raise Fault('WORKSPACE_QUOTA',413)
        if c.execute('SELECT 1 FROM files WHERE owner=? AND name=?',(u,n)).fetchone(): raise Fault('DESTINATION_EXISTS',409)
        digest=sha(data)
        c.execute('INSERT INTO files VALUES(?,?,?,?,?,?,?)',(u,n,self.files.encrypt(data),digest,len(data),uuid.uuid4().hex,time.time()))
        return {'name':n,'size':len(data),'sha256':digest}
    def upload(self,u,n,data):
        try: check_name(n)
        except ValueError: raise Fault('INVALID_NAME')
        with self.tx() as c: return self._put(c,u,n,data)
    def download(self,u,n):
        try: check_name(n)
        except ValueError: raise Fault('INVALID_NAME')
        with self.tx() as c: return self._read(c,u,n)
    def _secret(self,c,u,label):
        r=c.execute('SELECT * FROM vault WHERE owner=? AND label=?',(u,label)).fetchone()
        if not r: raise Fault('KEY_NOT_FOUND',404)
        return r
    def _key(self,c,u,label,kind):
        r=self._secret(c,u,label)
        if r['kind']!=kind: raise Fault('WRONG_KEY_TYPE')
        try: return self.vault.decrypt(r['blob'])
        except InvalidToken: raise Fault('VAULT_AUTHENTICATION_FAILED',500)
    def _validate_secret(self,kind,value):
        try:
            if kind=='fernet': Fernet(value)
            elif kind=='ed25519':
                if not isinstance(serialization.load_pem_private_key(value,password=None),Ed25519PrivateKey): raise ValueError()
        except (ValueError,TypeError): raise Fault('INVALID_KEY_FORMAT')
    def _set_secret(self,c,u,label,kind,value,replace=False):
        self._validate_secret(kind,value)
        exists=c.execute('SELECT 1 FROM vault WHERE owner=? AND label=?',(u,label)).fetchone()
        if exists and not replace: raise Fault('LABEL_EXISTS',409)
        if not exists and replace: raise Fault('KEY_NOT_FOUND',404)
        if not exists and c.execute('SELECT count(*) FROM vault WHERE owner=?',(u,)).fetchone()[0]>=100: raise Fault('VAULT_QUOTA',413)
        c.execute('INSERT OR REPLACE INTO vault VALUES(?,?,?,?,?)',(u,label,kind,self.vault.encrypt(value),uuid.uuid4().hex))
        return {'key_ref':label,'kind':kind}
    def private_entry(self,u,entry,replace=False):
        with self.tx() as c:
            result=self._set_secret(c,u,entry.key_ref,entry.kind,entry.value.encode(),replace)
            self._event(c,u,None,'vault.update' if replace else 'vault.store','COMPLETED')
            return result
    def _snapshot(self,c,u,op,p):
        s={}
        for field in ('source','signature','public_key'):
            if field in p:
                r=self._file(c,u,p[field]); s[field]=r['version']
        if 'destination' in p:
            r=c.execute('SELECT version FROM files WHERE owner=? AND name=?',(u,p['destination'])).fetchone()
            if r: raise Fault('DESTINATION_EXISTS',409)
            s['destination']='absent'
        if 'key_ref' in p:
            if op=='crypto.key_create':
                if c.execute('SELECT 1 FROM vault WHERE owner=? AND label=?',(u,p['key_ref'])).fetchone(): raise Fault('LABEL_EXISTS',409)
                s['key']='absent'
            else: s['key']=self._secret(c,u,p['key_ref'])['version']
        return s
    def _event(self,c,u,j,op,status):
        c.execute('INSERT INTO events(owner,job,op,status,at) VALUES(?,?,?,?,?)',(u,j,op,status,time.time()))
    def _view(self,r):
        return {'job_id':r['id'],'operation':r['op'],'parameters':json.loads(r['params']),'plan_digest':r['digest'],'status':r['status'],'expires_at':r['expires'],'result':json.loads(r['result']) if r['result'] else None,'error_code':r['error']}
    def _job(self,c,u,j):
        r=c.execute('SELECT * FROM jobs WHERE owner=? AND id=?',(u,j)).fetchone()
        if not r: raise Fault('JOB_NOT_FOUND',404)
        return r
    def _finish(self,c,r,status,result=None,error=None):
        c.execute('UPDATE jobs SET status=?,result=?,error=? WHERE id=?',(status,canonical(result) if result is not None else None,error,r['id']))
        self._event(c,r['owner'],r['id'],r['op'],status)
        return self._view(self._job(c,r['owner'],r['id']))
    def submit(self,u,proposal,idem=None):
        op=proposal.operation; caps=self.capabilities()
        if op not in caps: raise Fault('UNSUPPORTED_OPERATION',422)
        schema,approval,agent=REGISTRY[op]
        if proposal.agent!=agent: raise Fault('WRONG_DOMAIN',422)
        try: p=schema.model_validate(proposal.parameters).model_dump()
        except ValidationError: raise Fault('INVALID_PARAMETERS',422)
        with self.tx() as c:
            if idem:
                r=c.execute('SELECT * FROM jobs WHERE owner=? AND idem=?',(u,idem)).fetchone()
                if r:
                    if r['op']!=op or r['params']!=canonical(p): raise Fault('IDEMPOTENCY_CONFLICT',409)
                    return self._view(r)
            if c.execute('SELECT count(*) FROM jobs WHERE owner=?',(u,)).fetchone()[0]>=2000: raise Fault('JOB_QUOTA',429)
            s=self._snapshot(c,u,op,p); j=uuid.uuid4().hex; now=time.time(); digest=sha(canonical({'owner':u,'job':j,'op':op,'params':p,'snapshot':s}).encode())
            c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(j,u,op,canonical(p),canonical(s),digest,'AWAITING_APPROVAL' if approval else 'READY',now,now+300,None,None,idem))
            r=self._job(c,u,j); self._event(c,u,j,op,r['status'])
            if approval: return self._view(r)
            return self._run(c,r)
    def approve(self,u,j,decision):
        with self.tx() as c:
            r=self._job(c,u,j)
            if r['status']!='AWAITING_APPROVAL': raise Fault('APPROVAL_NOT_PENDING',409)
            if not secrets.compare_digest(r['digest'],decision.plan_digest): raise Fault('APPROVAL_MISMATCH',409)
            if time.time()>r['expires']: return self._finish(c,r,'REJECTED',error='APPROVAL_EXPIRED')
            if not decision.approve: return self._finish(c,r,'REJECTED',error='USER_REJECTED')
            try: current=self._snapshot(c,u,r['op'],json.loads(r['params']))
            except Fault: return self._finish(c,r,'REJECTED',error='RESOURCE_CHANGED')
            if canonical(current)!=r['snapshot']: return self._finish(c,r,'REJECTED',error='RESOURCE_CHANGED')
            return self._run(c,r)
    def _run(self,c,r):
        # Savepoint keeps failed operations atomic while retaining failure evidence.
        c.execute('SAVEPOINT execution')
        try:
            result=self._execute(c,r['owner'],r['op'],json.loads(r['params']))
            c.execute('RELEASE execution')
        except (Fault,InvalidToken,ValueError,TypeError,InvalidSignature) as e:
            c.execute('ROLLBACK TO execution'); c.execute('RELEASE execution')
            return self._finish(c,r,'FAILED',error=e.code if isinstance(e,Fault) else 'CRYPTO_OR_FORMAT_FAILURE')
        return self._finish(c,r,'COMPLETED',result=result)
    def status(self,u,j):
        with self.tx() as c: return self._view(self._job(c,u,j))
    def history(self,u):
        with self.tx() as c: return [dict(x) for x in c.execute('SELECT job,op,status,at FROM events WHERE owner=? ORDER BY id DESC LIMIT 100',(u,))]
    def _execute(self,c,u,op,p):
        if op in ('file.list','file.search','file.duplicates'):
            rows=[dict(x) for x in c.execute('SELECT name,size,sha,created FROM files WHERE owner=? ORDER BY name',(u,))]
            if op=='file.duplicates':
                groups={}
                for row in rows: groups.setdefault(row['sha'],[]).append(row['name'])
                return {'groups':[v for v in groups.values() if len(v)>1]}
            return {'files':[r for r in rows if p.get('query','').lower() in r['name'].lower()]}
        if op=='file.inspect':
            r=self._file(c,u,p['source']); return {k:r[k] for k in ('name','size','sha','created')}
        if op=='vault.list': return {'credentials':[dict(x) for x in c.execute('SELECT label,kind FROM vault WHERE owner=? ORDER BY label',(u,))]}
        if op=='vault.delete': c.execute('DELETE FROM vault WHERE owner=? AND label=?',(u,p['key_ref'])); return {'deleted':True}
        if op=='history.clear': c.execute('DELETE FROM events WHERE owner=?',(u,)); return {'cleared':True,'note':'Job records retained; clear event recorded.'}
        if op=='crypto.key_create':
            key=Fernet.generate_key() if p['kind']=='fernet' else Ed25519PrivateKey.generate().private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
            return self._set_secret(c,u,p['key_ref'],p['kind'],key)
        if op=='crypto.public_key':
            key=serialization.load_pem_private_key(self._key(c,u,p['key_ref'],'ed25519'),password=None)
            return self._put(c,u,p['destination'],key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))
        if op=='script.propose': return {'preview':SCRIPT,'note':'Review only; actual execution is fixed Python diagnostics, not arbitrary Bash.'}
        if op in ('linux.resources','linux.system','script.execute_template'):
            if not self.lab_linux: raise Fault('LINUX_DISABLED',403)
            # Only enable in a disposable environment: these are runtime/host metrics, not visitor PC.
            return {'scope':'backend lab environment','os':platform.system(),'cpu_percent':psutil.cpu_percent(interval=None),'memory_available':psutil.virtual_memory().available,'disk_free':psutil.disk_usage('/').free}
        data=self._read(c,u,p['source'])
        if op=='crypto.hash': return {'sha256':sha(data),'note':'No historical integrity claim without trusted baseline.'}
        if op=='crypto.compare': return {'sha256':sha(data),'matches_supplied_reference':secrets.compare_digest(sha(data),p['expected_sha256'].lower())}
        if op=='crypto.identify_format': return {'format':'CM-FERNET-1' if data.startswith(MAGIC) else 'UNKNOWN','note':'Marker only; authentication requires key and successful decryption.'}
        if op=='crypto.verify':
            pub=serialization.load_pem_public_key(self._read(c,u,p['public_key']))
            if not isinstance(pub,Ed25519PublicKey): raise Fault('UNSUPPORTED_PUBLIC_KEY')
            sig=self._read(c,u,p['signature'])
            try: pub.verify(sig,data); valid=True
            except InvalidSignature: valid=False
            return {'valid':valid,'algorithm':'Ed25519','note':'Validity under supplied key; identity trust not established by this check.'}
        if op=='file.delete': c.execute('DELETE FROM files WHERE owner=? AND name=?',(u,p['source'])); return {'deleted':True}
        if op in ('file.move','file.rename'):
            c.execute('UPDATE files SET name=?,version=? WHERE owner=? AND name=?',(p['destination'],uuid.uuid4().hex,u,p['source'])); return {'name':p['destination'],'sha256':sha(data)}
        if op=='file.copy': out=data
        elif op=='crypto.encrypt':
            cipher=Fernet(self._key(c,u,p['key_ref'],'fernet')); out=MAGIC+cipher.encrypt(data)
            if cipher.decrypt(out[len(MAGIC):])!=data: raise Fault('VERIFICATION_FAILED',500)
        elif op=='crypto.decrypt':
            if not data.startswith(MAGIC): raise Fault('UNSUPPORTED_FORMAT')
            out=Fernet(self._key(c,u,p['key_ref'],'fernet')).decrypt(data[len(MAGIC):])
        elif op=='crypto.sign':
            key=serialization.load_pem_private_key(self._key(c,u,p['key_ref'],'ed25519'),password=None); out=key.sign(data); key.public_key().verify(out,data)
        else: raise Fault('UNSUPPORTED_OPERATION',422)
        return self._put(c,u,p['destination'],out)|{'original_preserved':True}
