"""Resource-limited one-shot document reader inside the macOS sandbox."""
import os,sys,json,resource
from pathlib import Path

if __name__=='__main__':
    if sys.argv[1]!='--inside':
        work,mode,path=sys.argv[1:]
        resource.setrlimit(resource.RLIMIT_CPU,(25,25))
        resource.setrlimit(resource.RLIMIT_FSIZE,(32*1024*1024,32*1024*1024))
        resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
        os.execv('/usr/bin/sandbox-exec',['sandbox-exec','-f',str(Path(work)/'sandbox.sb'),sys.executable,'-B',__file__,'--inside',mode,path])
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from server import documents
    try:
        mode,path=sys.argv[2:]
        data=(documents._tables if mode=='tables' else documents._extract)(Path(path))
        result={'ok':True,'data':data}
    except Exception as exc:result={'ok':False,'error':str(exc)[:300]}
    print(json.dumps(result,ensure_ascii=False,default=str))
