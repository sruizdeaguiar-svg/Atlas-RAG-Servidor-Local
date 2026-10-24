"""Stop only this installed Atlas application and its verified owned server."""
import os,subprocess,sys,sqlite3,json
from pathlib import Path
import psutil
app=Path.home()/'Applications/Atlas RAG.app';root=app/'Contents/Resources/runtime'
state=Path.home()/'Library/Application Support/Atlas RAG'
setting=subprocess.run(['/usr/bin/defaults','read','local.atlas.rag','AtlasStateDirectory'],capture_output=True,text=True)
if setting.returncode==0 and setting.stdout.strip():state=Path(setting.stdout.strip())
secret_setting=subprocess.run(['/usr/bin/defaults','read','local.atlas.rag','AtlasSecretDirectory'],capture_output=True,text=True)
private_vault=Path(secret_setting.stdout.strip()) if secret_setting.returncode==0 and secret_setting.stdout.strip() else Path.home()/'Library/Application Support/Atlas RAG Credentials'
if root.exists():
    # Persist only active jobs. The next server checks current collection permissions
    # and resumes incrementally, preserving completed document transactions.
    database=state/'rag.sqlite3'
    if database.exists():
        with sqlite3.connect(database,timeout=30) as conn:
            pending=[]
            for cid, in conn.execute("SELECT DISTINCT collection_id FROM jobs WHERE state IN ('queued','running')"):
                owner=conn.execute('SELECT value FROM settings WHERE key=?',('index_owner_'+str(cid),)).fetchone()
                if not owner:
                    owner=conn.execute("SELECT json(id) FROM users WHERE active=1 AND role='admin' ORDER BY id LIMIT 1").fetchone()
                if owner: pending.append({'collection_id':cid,'user_id':json.loads(owner[0])})
            conn.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',('resume_after_update',json.dumps(pending)))
    result=subprocess.run([str(root/'python/bin/python3.14'),'-B',str(root/'scripts/control.py'),'stop'],env={**os.environ,'RAG_STATE_DIR':str(state),'RAG_SECRET_DIR':str(private_vault),'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=25)
    if result.returncode:raise RuntimeError('Atlas controller could not stop its server safely')
for p in psutil.process_iter(['exe']):
    try:
        if p.info['exe']==str(app/'Contents/MacOS/AtlasRAG'):
            p.terminate()
            try:p.wait(8)
            except psutil.TimeoutExpired:p.kill();p.wait(3)
    except (psutil.NoSuchProcess,psutil.AccessDenied):pass
print('Only the installed Atlas app and its owned server stopped for update.')
