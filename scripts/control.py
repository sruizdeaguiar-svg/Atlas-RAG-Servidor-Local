#!/usr/bin/env python3
"""Project-scoped lifecycle. Never stops an unverified PID or external AI server."""
import sys,os,json,time,socket,subprocess,signal,fcntl,secrets,shutil,ssl
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from server.store import STATE, SECRET_STATE
from server import network
import psutil, httpx
RECORD=STATE/'service.json'

def process(record):
    try:
        p=psutil.Process(record['pid']); cmd=p.cmdline()
        if '--owner' not in cmd or record['owner'] not in cmd or str(ROOT/'server/run.py') not in cmd: return None
        if abs(p.create_time()-record['created'])>0.2: return None
        return p
    except (psutil.Error,KeyError): return None

def record():
    try: return json.loads(RECORD.read_text())
    except (OSError,ValueError): return {}

def status(include_setup=False):
    r=record(); p=process(r); disk=shutil.disk_usage(STATE); vm=psutil.virtual_memory(); rss=0; pids=[]
    if p:
        try:
            for child in [p]+p.children(recursive=True):
                try: rss+=child.memory_info().rss; pids.append(child.pid)
                except psutil.Error: pass
        except psutil.Error: pass
    result={'running':bool(p),'url':f"http://127.0.0.1:{r.get('port',8765)}",'pid':p.pid if p else None,'rss':rss,'pids':pids,'disk_free':disk.free,'memory_available':vm.available,'memory_total':vm.total,'swap':psutil.swap_memory().used,'log':str(STATE/'server.log'),'state':str(STATE)}
    result['network']=network.public()
    if p:
        try:
            h=httpx.get(result['url']+'/api/health',timeout=2,trust_env=False).json()
            result['healthy']=h.get('instance')==r['owner']; result['setup']=h.get('setup',False)
            if result['network'].get('enabled'):
                try:
                    tls=ssl.create_default_context(cafile=str(network.paths()[0]));h2=httpx.get(result['network']['url']+'/api/health',verify=tls,timeout=1,trust_env=False)
                    result['network']['healthy']=h2.status_code==200 and h2.json().get('instance')==r['owner']
                except Exception: result['network']['healthy']=False
            if include_setup and result['setup']: result['setup_token']=(SECRET_STATE/'setup.token').read_text()
        except Exception: result['healthy']=False
    return result

def start():
    r=record()
    if process(r): return status(True)
    if r.get('pid') and psutil.pid_exists(r['pid']): raise RuntimeError('State belongs to another running installation; stop it with its own controller')
    port=int(os.environ.get('RAG_PORT','8765'))
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        try: s.bind(('127.0.0.1',port))
        except OSError:
            s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
    owner=secrets.token_hex(20)
    log=STATE/'server.log'
    if log.exists() and log.stat().st_size>4*1024*1024: os.replace(log,STATE/'server.previous.log')
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONUNBUFFERED':'1','RAG_STATE_DIR':str(STATE),'RAG_SECRET_DIR':str(SECRET_STATE),'PATH':'/opt/homebrew/bin:/usr/bin:/bin'}
    with log.open('a') as output:
        p=subprocess.Popen([sys.executable,'-B',str(ROOT/'server/run.py'),'--port',str(port),'--owner',owner],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=output,start_new_session=True,close_fds=True)
    r={'pid':p.pid,'created':psutil.Process(p.pid).create_time(),'port':port,'owner':owner}
    RECORD.write_text(json.dumps(r)); RECORD.chmod(0o600)
    for _ in range(100):
        if p.poll() is not None: raise RuntimeError('Server exited; read '+str(log))
        try:
            health=httpx.get(f'http://127.0.0.1:{port}/api/health',timeout=0.5,trust_env=False).json()
            if health.get('instance')==owner:
                current=status(True)
                if not current['network'].get('enabled') or current['network'].get('healthy'): return current
        except Exception: pass
        time.sleep(.1)
    stop(); raise RuntimeError('Server startup timed out; read '+str(log))

def stop():
    r=record(); p=process(r)
    if p:
        # Snapshot descendants first; identity is checked before every signal.
        descendants=p.children(recursive=True)
        p.terminate()
        try: p.wait(timeout=12)
        except psutil.TimeoutExpired:
            if process(r): p.kill(); p.wait(timeout=3)
        for child in descendants:
            try:
                if child.is_running() and child.status()!=psutil.STATUS_ZOMBIE:
                    child.terminate()
                    try: child.wait(timeout=2)
                    except psutil.TimeoutExpired: child.kill()
            except psutil.Error: pass
    RECORD.unlink(missing_ok=True)
    return status()

if __name__=='__main__':
    try:
        action=sys.argv[1] if len(sys.argv)>1 else 'status'
        with (STATE/'control.lock').open('a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            if action=='start': out=start()
            elif action=='stop': out=stop()
            elif action=='restart':
                previous=record(); stop()
                if previous.get('port'): os.environ['RAG_PORT']=str(previous['port'])
                out=start()
            elif action in {'network-enable','network-disable'}:
                network.configure(action=='network-enable'); previous=record(); stop()
                if previous.get('port'): os.environ['RAG_PORT']=str(previous['port'])
                out=start()
            elif action=='native-status': out=status(True)
            elif action=='status': out=status()
            else: raise ValueError('Use start, stop, restart or status')
        print(json.dumps(out))
    except Exception as exc: print(json.dumps({'error':str(exc)})); sys.exit(1)
