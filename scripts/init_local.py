"""Create disposable local credentials OUTSIDE the repository. Refuses overwrite."""
import json, os, secrets, shlex
from pathlib import Path
from cryptography.fernet import Fernet
os.umask(0o077)
root=Path.home()/'.local/state/ciphermate'; root.mkdir(mode=0o700,parents=True,exist_ok=True)
if root.stat().st_mode & 0o077: raise SystemExit(f'Private directory required: chmod 700 {root}')
config=root/'runtime.env'; token=secrets.token_urlsafe(48)
values={'CM_DB_PATH':str(root/'state.sqlite3'),'CM_MASTER_KEY':Fernet.generate_key().decode(),'CM_USERS_JSON':json.dumps({'owner':token}),'CM_MODEL':'deepseek-flash','CM_LAB_LINUX':'0'}
try:
    with config.open('x') as f:
        for k,v in values.items(): f.write('export '+k+'='+shlex.quote(v)+'\n')
except FileExistsError: raise SystemExit(f'Already exists: {config}. Preserve this file; never reset the key for an existing database.')
print(f'Created private runtime configuration: {config}')
print('Use bash scripts/run_local.sh for local browser access. Keep all generated credentials private.')
