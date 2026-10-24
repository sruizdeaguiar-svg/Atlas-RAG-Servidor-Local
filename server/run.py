import argparse,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
p=argparse.ArgumentParser(); p.add_argument('--port',type=int,required=True); p.add_argument('--owner',required=True); args=p.parse_args()
os.environ['RAG_INSTANCE']=args.owner
import uvicorn,threading
from server import network
c=network.config()
if c.get("enabled"):
    network.public(c) # Validate the listener before binding.
    cert,key=network.paths()
    lan=uvicorn.Server(uvicorn.Config("server.app:app",host=c["host"],port=c["port"],ssl_certfile=str(cert),ssl_keyfile=str(key),lifespan="off",access_log=False,proxy_headers=False,log_level="info"))
    threading.Thread(target=lan.run,daemon=True,name="atlas-lan-tls").start()
uvicorn.run('server.app:app',host='127.0.0.1',port=args.port,proxy_headers=False,access_log=False,log_level='info',timeout_graceful_shutdown=8)
