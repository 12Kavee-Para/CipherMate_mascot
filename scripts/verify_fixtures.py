"""Test the previously supplied synthetic fixture archive without extracting private keys to the repo."""
import sys, tempfile, zipfile, json
from pathlib import Path
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.store import Store
from backend.chat import Planner

def main(path):
    with zipfile.ZipFile(path) as z, tempfile.TemporaryDirectory() as t:
        root='CipherMate_test_fixtures/'
        files={n[len(root+'workspace/'):]:z.read(n) for n in z.namelist() if n.startswith(root+'workspace/') and not n.endswith('/')}
        store=Store(Path(t)/'state.sqlite3',Fernet.generate_key().decode()); token='t'*48; h={'Authorization':'Bearer '+token}; api='/api/ciphermate'
        with TestClient(create_app(store,{'fixture-owner':token},Planner())) as c:
            for n,data in files.items(): assert c.post(api+'/files',params={'name':n},content=data,headers=h|{'Content-Type':'application/octet-stream'}).status_code==201
            for label,file,kind in [('lab-key','lab-fernet.key','fernet'),('wrong-key','wrong-fernet.key','fernet'),('lab-sign-key','lab-ed25519-private.pem','ed25519')]:
                r=c.post(api+'/vault/entry',headers=h,json={'key_ref':label,'kind':kind,'value':z.read(root+'private_lab_material/'+file).decode().strip()}); assert r.status_code==201,r.text
            def run(op,p,agent='crypto-agent'):
                r=c.post(api+'/jobs',headers=h,json={'agent':agent,'operation':op,'parameters':p}); assert r.status_code==200,r.text; j=r.json()
                if j['status']=='AWAITING_APPROVAL': j=c.post(api+'/jobs/'+j['job_id']+'/approval',headers=h,json={'approve':True,'plan_digest':j['plan_digest']}).json()
                return j
            assert ['documents/report-copy.txt','documents/report.txt'] in run('file.duplicates',{},'file-agent')['result']['groups']
            assert run('crypto.decrypt',{'source':'crypto/report.cm','destination':'decoded.txt','key_ref':'lab-key'})['status']=='COMPLETED'
            assert c.get(api+'/download',params={'name':'decoded.txt'},headers=h).content==files['documents/report.txt']
            for src,key in [('crypto/report.cm','wrong-key'),('crypto/report-tampered.cm','lab-key')]:
                assert run('crypto.decrypt',{'source':src,'destination':'bad-output.txt','key_ref':key})['status']=='FAILED'
                assert c.get(api+'/download',params={'name':'bad-output.txt'},headers=h).status_code==404
            p={'source':'documents/report.txt','signature':'crypto/report.sig','public_key':'crypto/lab-ed25519-public.pem'}
            for changes,expected in [({},True),({'source':'documents/report-modified.txt'},False),({'signature':'crypto/report-bad.sig'},False),({'public_key':'crypto/wrong-ed25519-public.pem'},False)]:
                assert run('crypto.verify',p|changes)['result']['valid'] is expected
            assert run('crypto.identify_format',{'source':'crypto/unknown-format.bin'})['result']['format']=='UNKNOWN'
        print('PASS: supplied fixture ZIP — duplicate grouping, exact decryption, wrong key, tampering, four signature checks, unknown format (9 checks).')
if __name__=='__main__': main(sys.argv[1])
