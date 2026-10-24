"""Enable Atlas's private HTTPS listener for the explicitly requested iPad client."""
import os,sys,json,subprocess
from pathlib import Path
app=Path.home()/'Applications/Atlas RAG.app';runtime=app/'Contents/Resources/runtime'
state=Path.home()/'Library/Application Support/Atlas RAG'
r=subprocess.run(['/usr/bin/defaults','read','local.atlas.rag','AtlasStateDirectory'],capture_output=True,text=True)
if r.returncode==0 and r.stdout.strip():state=Path(r.stdout.strip())
secret_setting=subprocess.run(['/usr/bin/defaults','read','local.atlas.rag','AtlasSecretDirectory'],capture_output=True,text=True)
private_vault=Path(secret_setting.stdout.strip()) if secret_setting.returncode==0 and secret_setting.stdout.strip() else Path.home()/'Library/Application Support/Atlas RAG Credentials'
r=subprocess.run([str(runtime/'python/bin/python3.14'),'-B',str(runtime/'scripts/control.py'),'network-enable'],env={**os.environ,'RAG_STATE_DIR':str(state),'RAG_SECRET_DIR':str(private_vault),'PYTHONDONTWRITEBYTECODE':'1'},check=True,capture_output=True,text=True,timeout=30)
status=json.loads(r.stdout)
assert status.get('healthy') and status.get('network',{}).get('healthy'),'HTTPS listener is not healthy'
record={'network':status['network'],'loopback':status['url'],'running':status['running'],'state':str(state)}
(Path(__file__).resolve().parents[1]/'evidence/production-lan.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record))
