"""Stop only this installed Atlas application and its verified owned server."""
import os,subprocess,sys
from pathlib import Path
import psutil
app=Path.home()/'Applications/Atlas RAG.app';root=app/'Contents/Resources/runtime'
state=Path.home()/'Library/Application Support/Atlas RAG'
setting=subprocess.run(['/usr/bin/defaults','read','local.atlas.rag','AtlasStateDirectory'],capture_output=True,text=True)
if setting.returncode==0 and setting.stdout.strip():state=Path(setting.stdout.strip())
secret_setting=subprocess.run(['/usr/bin/defaults','read','local.atlas.rag','AtlasSecretDirectory'],capture_output=True,text=True)
private_vault=Path(secret_setting.stdout.strip()) if secret_setting.returncode==0 and secret_setting.stdout.strip() else Path.home()/'Library/Application Support/Atlas RAG Credentials'
if root.exists():
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
