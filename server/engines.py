"""Exclusive local model lifecycle. Signals only processes created in Atlas's workspace."""
import os,json,time,socket,subprocess,threading,hashlib,signal,urllib.parse,re,functools
from pathlib import Path
import httpx,psutil
from .store import STATE,ROOT as APP_ROOT,setting,set_setting
from . import providers
NAMES=('llama','omlx','vllm','lmstudio')
LOCK=threading.RLock()
CANCEL=threading.Event()
JOB={'busy':False,'message':'','error':''}
CHILDREN={}
LMS_CACHE={}
LMS_STATUS={}
ROOT=STATE/'engines'
PORTS={'llama':18880,'omlx':18881,'vllm':18882,'lmstudio':18883}


@functools.lru_cache(maxsize=16)
def ranked_llama_binary(candidates):
    """Choose the newest detected build, caching by path + modification time."""
    scores=[]
    for order,(path,mtime) in enumerate(candidates):
        build=-1
        try:
            result=subprocess.run([path,'--version'],capture_output=True,text=True,timeout=5,env={'PATH':'/usr/bin:/bin'})
            match=re.search(r'(?:build\s+|\bb)(\d+)',result.stdout+'\n'+result.stderr,re.I)
            if result.returncode==0 and match:build=int(match.group(1))
        except (OSError,subprocess.TimeoutExpired):pass
        scores.append((build,-order,path))
    return max(scores)[2] if scores else ''

def detected_llama_binary(paths):
    entries=[]
    for path in paths:
        try:
            p=Path(path)
            if p.is_file():entries.append((str(p),p.stat().st_mtime_ns))
        except OSError:pass
    return ranked_llama_binary(tuple(entries))

def defaults():
    home=Path.home()
    roots=[str(p) for p in [Path('/Volumes/Seguridad/models'),Path('/Volumes/Seguridad/Llama'),home/'.cache/huggingface/hub',home/'.omlx/models',home/'.lmstudio/models'] if p.is_dir()]
    import shutil
    candidates={'llama':['/opt/homebrew/bin/llama-server','/usr/local/bin/llama-server','/Volumes/Seguridad/Llama/optimizacion-m4-pro/bin/llama-server','/Volumes/Seguridad/Llama/llama.cpp/build/bin/llama-server'],'omlx':['/Applications/oMLX.app/Contents/MacOS/omlx-cli','/opt/homebrew/bin/omlx'],'vllm':['/opt/homebrew/bin/vllm','/usr/local/bin/vllm'],'lmstudio':[str(home/'.lmstudio/bin/lms')]}
    binaries={n:next((p for p in paths if Path(p).is_file()),shutil.which({'llama':'llama-server','lmstudio':'lms'}.get(n,n)) or paths[0]) for n,paths in candidates.items()}
    binaries['llama']=detected_llama_binary(candidates['llama']) or binaries['llama']
    try:
        for volume in Path('/Volumes').iterdir():
            for suffix in ['models','Modelos']:
                directory=volume/suffix
                if directory.is_dir() and str(directory) not in roots:roots.append(str(directory))
    except OSError:pass
    return {'enabled':True,'memory_guard':False,'roots':roots,'binaries':binaries}
def config():return setting('engine_manager',defaults())
def configure(value):
    if JOB['busy']:raise ValueError('Wait for the current engine operation')
    cfg=config()
    if 'roots' in value:
        roots=[]
        for raw in value['roots']:
            p=Path(raw).expanduser().resolve()
            if not p.is_dir() or str(p) in {'/','/Volumes',str(Path.home())}:raise ValueError('Choose a model directory, not a system root')
            roots.append(str(p))
        if len(roots)>12:raise ValueError('At most 12 model directories')
        cfg['roots']=roots
    if 'enabled' in value:cfg['enabled']=bool(value['enabled'])
    if 'memory_guard' in value:cfg['memory_guard']=bool(value['memory_guard'])
    set_setting('engine_manager',cfg)
    return cfg

def record_path():ROOT.mkdir(parents=True,exist_ok=True);return ROOT/'active.json'
def record():
    try:return json.loads(record_path().read_text())
    except (OSError,ValueError):return {}
def save(r):record_path().write_text(json.dumps(r))
def alive(r):
    if not r.get('pid'):return None
    try:
        p=psutil.Process(r['pid'])
        if abs(p.create_time()-r['created'])>.01 or p.status()==psutil.STATUS_ZOMBIE or Path(p.cwd()).resolve()!=ROOT.resolve():return None
        return p
    except (psutil.Error,OSError):return None

def listening(port):
    with socket.socket() as s:s.settimeout(.25);return s.connect_ex(('127.0.0.1',port))==0

def engine_env():
    keep={'HOME','USER','LOGNAME','TMPDIR','LANG','LC_ALL','SHELL'}
    return {**{k:v for k,v in os.environ.items() if k in keep},'PATH':'/opt/homebrew/bin:/usr/bin:/bin','HF_HUB_OFFLINE':'1','HF_HUB_DISABLE_TELEMETRY':'1','TRANSFORMERS_OFFLINE':'1','PYTHONDONTWRITEBYTECODE':'1'}

def secured_command(name,args,env):
    if name not in {'omlx','vllm'}:return args,env
    overlay=APP_ROOT/'build'/'engine-security'/name
    if not overlay.is_dir():raise ValueError('Install the latest Atlas engine security dependencies before starting '+name)
    binary=Path(args[0]).resolve()
    if name=='omlx':
        app=binary.parents[1];resources=app/'Resources';python=resources/'Python/cpython-3.11/bin/python3'
        if not python.is_file():raise ValueError('Unsupported oMLX runtime; select the supported macOS app')
        env={**env,'PYTHONHOME':str(resources/'Python/cpython-3.11'),'PYTHONPATH':str(resources)+':'+str(resources/'Python/framework-mlx-base/lib/python3.11/site-packages')}
    else:
        with binary.open('rb') as handle:first=handle.readline(1024).decode(errors='strict').strip()
        python=Path(first[2:]) if first.startswith('#!') else Path('')
        if not python.is_absolute() or not python.is_file() or 'python3.12' not in str(python):raise ValueError('Unsupported vLLM Python runtime; use the supported Python 3.12 installation')
    return [str(python),'-B',str(APP_ROOT/'scripts/engine_entry.py'),name,*args],env

def command(args,timeout=40):
    try:r=subprocess.run(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,env=engine_env())
    except subprocess.TimeoutExpired:raise ValueError('Local engine command timed out. Open LM Studio on the Mac if its service is unavailable.')
    if r.returncode:raise ValueError((r.stderr or r.stdout or 'Engine command failed')[-1200:])
    return r.stdout

def _all_local_models(name):
    if name not in NAMES:raise ValueError('Unknown local engine')
    if name=='lmstudio':
        try:
            gui=any((p.info['name'] or '')=='LM Studio' for p in psutil.process_iter(['name']))
            if gui:
                if time.monotonic()-LMS_CACHE.get('time',0)<15:return LMS_CACHE['models']
                data=json.loads(command([config()['binaries']['lmstudio'],'ls','--json'],12))
                models=[]
                for m in data:
                    if m.get('type') not in {'llm','embedding'}:continue
                    key=m.get('modelKey') or m.get('indexedModelIdentifier')
                    if not key or key.startswith('-') or not m.get('sizeBytes'):continue
                    ident=hashlib.sha256(('lmstudio:'+key).encode()).hexdigest()[:20]
                    models.append({'id':ident,'name':m.get('displayName') or key,'path':m.get('path',key),'model_key':key,'size_bytes':m['sizeBytes'],'api_model':'atlas-'+ident,'type':m.get('type','llm'),'loaded':record().get('model')==ident,'active_context':record().get('context') if record().get('model')==ident else None})
                LMS_CACHE.update(time=time.monotonic(),models=models)
                ROOT.mkdir(parents=True,exist_ok=True);(ROOT/'lmstudio-catalog.json').write_text(json.dumps(models))
                return models
        except (ValueError,psutil.Error):pass
        cached=ROOT/'lmstudio-catalog.json'
        if cached.is_file():
            try:return json.loads(cached.read_text())
            except (OSError,ValueError):pass
    if name=='lmstudio':return []
    roots=[Path(p) for p in config()['roots']]
    result={};seen=set();count=0
    for base in roots:
        if not base.is_dir():continue
        for here,dirs,files in os.walk(base,followlinks=False):
            count+=1
            if count>30000:break
            rel=Path(here).relative_to(base)
            dirs[:]=[d for d in dirs if not d.startswith('.') and d not in {'blobs','__pycache__','node_modules','build','python','vendor','tests'} and len(rel.parts)<6]
            paths=[]
            if name in {'llama','lmstudio'}:
                paths=[Path(here)/f for f in files if f.lower().endswith('.gguf') and not f.startswith(('._','ggml-vocab-','mmproj-','mtp-','dflash-')) and ('-of-' not in f or '-00001-of-' in f)]
            if name in {'omlx','vllm','lmstudio'} and 'config.json' in files and any(f.endswith('.safetensors') for f in files):paths.append(Path(here))
            for path in paths:
                if str(path) in seen:continue
                seen.add(str(path))
                try:
                    size=path.stat().st_size if path.is_file() else sum(f.stat().st_size for f in path.glob('*.safetensors'))
                    if path.is_file() and '-00001-of-' in path.name:size=sum(f.stat().st_size for f in path.parent.glob(path.name.replace('-00001-of-','-*-of-')))
                    model_label=path.parent.parent.name if path.parent.name=='snapshots' else path.name
                    kind='embedding' if any(word in model_label.lower() for word in ['embed','bge-','minilm','e5-','gte-']) else 'llm'
                    if path.is_dir():
                        try:
                            meta=json.loads((path/'config.json').read_text());arch=' '.join(meta.get('architectures',[])).lower()
                            if any(x in arch for x in ['embedding','bertmodel','xlmroberta']):kind='embedding'
                        except (OSError,ValueError):pass
                    ident=hashlib.sha256(str(path).encode()).hexdigest()[:20]
                    api_model=path.name if name=='omlx' else 'atlas-'+ident
                    result[ident]={'id':ident,'name':(path.parent.parent.name.removeprefix('models--').replace('--','/')+' / '+path.name[:8]) if path.parent.name=='snapshots' else path.name,'path':str(path),'size_bytes':size,'api_model':api_model,'type':kind,'loaded':record().get('model')==ident,'active_context':record().get('context') if record().get('model')==ident else None}
                except OSError:pass
    return sorted(result.values(),key=lambda x:x['name'].casefold())[:1000]

def local_models(name,purpose='generation'):
    if purpose not in {'generation','embedding','all'}:raise ValueError('Unknown model purpose')
    items=_all_local_models(name)
    return [m for m in items if purpose=='all' or (m.get('type')=='embedding')==(purpose=='embedding')]

def lmstudio_app(action):
    helper=APP_ROOT/'build/EngineTools'
    if not helper.is_file():raise ValueError('Rebuild Atlas to install its native LM Studio controller')
    result=json.loads(command([str(helper),action],20))
    LMS_STATUS.clear()
    return result

def close_lmstudio_completely():
    # Explicit engine switches and stop-all also close an already-open LM Studio.
    family=[]
    for process in psutil.process_iter(['exe','uids','create_time']):
        try:
            exe=process.info['exe'] or ''
            if process.info['uids'].real==os.getuid() and ('/LM Studio.app/Contents/' in exe or ('.lmstudio' in exe and Path(exe).name=='llmster')):
                family.append((process,process.info['create_time']))
        except (psutil.Error,TypeError):pass
    if not family and not lmstudio_status()['application_running']:return
    cli=config()['binaries']['lmstudio']
    try:
        command([cli,'unload','--all'],60)
        command([cli,'server','stop'],20)
    except ValueError:pass
    lmstudio_app('quit')
    pending=[]
    for process,created in family:
        try:
            if process.is_running() and abs(process.create_time()-created)<.01:process.terminate();pending.append(process)
        except psutil.NoSuchProcess:pass
    _,pending=psutil.wait_procs(pending,timeout=8)
    for process in pending:
        try:process.kill()
        except psutil.NoSuchProcess:pass
    _,pending=psutil.wait_procs(pending,timeout=3)
    LMS_STATUS.clear()
    if pending:raise ValueError('LM Studio still has running processes; switch cancelled')

def lmstudio_status():
    now=time.monotonic()
    if now-LMS_STATUS.get('time',0)<5:return LMS_STATUS['value']
    gui=any((p.info['name'] or '')=='LM Studio' for p in psutil.process_iter(['name']))
    value={'application_running':gui,'api_running':False,'loaded_models':None}
    if gui:
        try:
            api=json.loads(command([config()['binaries']['lmstudio'],'server','status','--json'],3))
            value.update(api_running=bool(api.get('running')),port=api.get('port'))
            models=json.loads(command([config()['binaries']['lmstudio'],'ps','--json'],3))
            value['loaded_models']=len(models)
        except (ValueError,OSError):pass
    LMS_STATUS.update(time=now,value=value)
    return value

def status():
    job=dict(JOB)
    r=record();p=alive(r);rss=0;pids=[]
    if p:
        try:family=[p]+p.children(recursive=True)
        except psutil.Error:p=None;family=[]
        for child in family:
            try:rss+=child.memory_info().rss;pids.append(child.pid)
            except psutil.Error:pass
    running=bool(p) if r.get('name')!='lmstudio' else bool(r and listening(r['port']))
    return {'lmstudio':lmstudio_status(),'config':config(),'active':r if running else {},'running':running,'rss':rss if r.get('name')!='lmstudio' else None,'pids':pids,'job':job,'available':{n:Path(config()['binaries'][n]).is_file() for n in NAMES},'memory_available':psutil.virtual_memory().available}

def stop_all():
    r=record()
    if not r:return {'released':True,'remaining':[]}
    if r.get('name')=='lmstudio':
        # Touch only the exact model identifier and API instance Atlas started.
        if listening(r['port']):
            cli=config()['binaries']['lmstudio']
            current=json.loads(command([cli,'server','status','--json'],15))
            port=current.get('port') or current.get('server',{}).get('port')
            if port!=r['port']:raise ValueError('LM Studio ownership changed; Atlas will not stop another server')
            if r.get('api_model'):
                loaded=json.loads(command([cli,'ps','--json'],15))
                if any(m.get('identifier')==r['api_model'] for m in loaded):command([cli,'unload',r['api_model']],40)
            command([cli,'server','stop'],20)
        lmstudio_app('quit')
    else:
        p=alive(r)
        if p:
            family=[p]+p.children(recursive=True)
            identities={c.pid:c.create_time() for c in family}
            for c in reversed(family):
                try:
                    if abs(c.create_time()-identities[c.pid])<.01:c.terminate()
                except psutil.NoSuchProcess:pass
            _,pending=psutil.wait_procs(family,timeout=8)
            for c in pending:
                try:
                    if abs(c.create_time()-identities[c.pid])<.01:c.kill()
                except psutil.NoSuchProcess:pass
            _,pending=psutil.wait_procs(pending,timeout=3)
            live=[]
            for child in pending:
                try:
                    if child.is_running() and child.status()!=psutil.STATUS_ZOMBIE:live.append(child)
                except psutil.NoSuchProcess:pass
            if live:raise ValueError('An Atlas engine process could not be stopped')
            owned=CHILDREN.pop(r['pid'],None)
            if owned:owned.wait(timeout=2)
    owned=CHILDREN.pop(r.get('pid'),None)
    if owned and owned.poll() is not None:owned.wait(timeout=2)
    if listening(r['port']):raise ValueError('Engine port still open; no new engine was started')
    record_path().unlink(missing_ok=True)
    return {'released':True,'remaining':[]}

def budget(model,context):
    # Includes conservative buffers; KV layout still depends on the model/runtime.
    estimated=int(model['size_bytes']*1.5)+1024**3+context*65536
    available=psutil.virtual_memory().available
    if config().get('memory_guard',False) and estimated>available-2*1024**3:raise ValueError(f'Memoria insuficiente: pesos {model["size_bytes"]/1024**3:.1f} GB; estimación con contexto {context}: {estimated/1024**3:.1f} GB + 2 GB de reserva; disponibles ahora {available/1024**3:.1f} GB. Un MoE necesita todos sus pesos. Reduce el contexto o elige un modelo menor; Atlas no detiene motores externos automáticamente.')
    return estimated

def launch(name,model,context):
    cfg=config();binary=cfg['binaries'][name];port=PORTS[name]
    if not Path(binary).is_file():raise ValueError('Local engine is not installed: '+name)
    if listening(port):raise ValueError('Dedicated Atlas port is already in use; no external process was stopped')
    ROOT.mkdir(parents=True,exist_ok=True)
    api_model=model['api_model'] if model else ''
    embedding=bool(model and model.get('type')=='embedding')
    if embedding and Path(model['path']).is_dir():
        try:
            metadata=json.loads((Path(model['path'])/'config.json').read_text());limit=metadata.get('max_position_embeddings')
            if isinstance(limit,int) and limit>0:context=min(context,limit)
        except (OSError,ValueError):pass
    if name=='llama':
        args=[binary,'--host','127.0.0.1','--port',str(port)]
        args+=['--model',model['path'],'--alias',api_model,'--ctx-size',str(context),'--gpu-layers','99'] if model else ['--models-dir',cfg['roots'][0],'--models-max','1','--no-models-autoload']
        if embedding:args+=['--embedding','--pooling','mean']
    elif name=='omlx':
        base=ROOT/'omlx';base.mkdir(exist_ok=True)
        # Isolated settings prevent pinned/shared models being preloaded.
        model_dir=Path(model['path']).parent if model else Path(cfg['roots'][0])
        args=[binary,'serve','--host','127.0.0.1','--port',str(port),'--base-path',str(base),'--model-dir',str(model_dir),'--no-hf-cache','--no-cache','--initial-cache-blocks','1','--memory-guard','safe' if cfg.get('memory_guard',False) else 'off']
        if model:
            api_model=Path(model['path']).name
            (base/'model_settings.json').write_text(json.dumps({'version':1,'models':{api_model:{'max_context_window':context}}}))
    elif name=='vllm':
        if not model:return {'waiting_model':True}
        args=[binary,'serve',model['path'],'--host','127.0.0.1','--port',str(port),'--served-model-name',api_model,'--max-model-len',str(context),'--max-num-seqs','1','--gpu-memory-utilization','0.20','--kv-cache-memory-bytes','268435456']
        if embedding:args+=['--runner','pooling']
    else:
        # A shared LM Studio API must not be commandeered by automatic selection.
        prior=urllib.parse.urlsplit(providers.config()['lmstudio']['url']).port or 1234
        if listening(1234) or (prior!=port and listening(prior)):raise ValueError('LM Studio already has an external server. Stop it yourself before enabling Atlas management for LM Studio.')
        was_open=lmstudio_status()['application_running']
        if not was_open:save({'name':name,'port':port,'model':'','api_model':'','context':context})
        lmstudio_app('start')
        if CANCEL.is_set():lmstudio_app('quit');raise ValueError('Engine operation cancelled')
        # The freshly opened GUI can restore its own API and models automatically.
        # Stop that restored state before binding Atlas's dedicated loopback port.
        try:command([binary,'server','stop'],45)
        except ValueError as exc:
            if 'server is not running' not in str(exc).lower():raise
        existing=json.loads(command([binary,'ps','--json'],20))
        if existing:
            command([binary,'unload','--all'],90)
            if json.loads(command([binary,'ps','--json'],20)):raise ValueError('LM Studio did not release its restored models')
        if CANCEL.is_set():raise ValueError('Engine operation cancelled')
        command([binary,'server','start','--port',str(port),'--bind','127.0.0.1'],45)
        deadline=time.monotonic()+20
        while not listening(port):
            if time.monotonic()>deadline:raise ValueError('LM Studio did not open the dedicated Atlas port')
            if CANCEL.is_set():raise ValueError('Engine operation cancelled')
            time.sleep(.2)
        r={'name':name,'port':port,'model':model['id'] if model else '','api_model':api_model,'context':context};save(r)
        if model:
            command([binary,'load',model.get('model_key',model['path']),'--identifier',api_model]+([] if embedding else ['--context-length',str(context)])+['-y'],180)
            r.update(model=model['id'],api_model=api_model);save(r)
        if embedding:verify_embedding(port,api_model)
        return r
    log_path=ROOT/(name+'.log'); log_offset=log_path.stat().st_size if log_path.exists() else 0
    log=log_path.open('ab')
    env={**engine_env(),'OMLX_BASE_PATH':str(ROOT/'omlx')}
    args,env=secured_command(name,args,env)
    proc=subprocess.Popen(args,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True);log.close();CHILDREN[proc.pid]=proc
    r={'name':name,'pid':proc.pid,'created':psutil.Process(proc.pid).create_time(),'port':port,'model':model['id'] if model else '','api_model':api_model,'context':context};save(r)
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        if CANCEL.is_set():raise ValueError('Engine operation cancelled')
        if proc.poll() is not None:
            with log_path.open('rb') as diagnostic:
                diagnostic.seek(max(log_offset,log_path.stat().st_size-8192));tail=diagnostic.read(8192).decode('utf-8','replace')
            architecture=re.search(r"unknown model architecture: ['\"]([a-zA-Z0-9_.-]{1,80})",tail)
            if architecture:raise ValueError(f'llama.cpp no admite la arquitectura {architecture.group(1)} en esta compilación. Actualiza el motor o elige un modelo compatible. / This llama.cpp build does not support this model architecture.')
            raise ValueError(name+' stopped during startup; see its Atlas engine log')
        try:
            response=httpx.get(f'http://127.0.0.1:{port}/v1/models',timeout=1,trust_env=False)
            if response.status_code==200:break
        except httpx.HTTPError:pass
        time.sleep(.3)
    else:raise ValueError('Engine startup timed out')
    if name=='omlx' and model:
        response=httpx.post(f'http://127.0.0.1:{port}/v1/models/{urllib.parse.quote(api_model,safe="")}/load',timeout=180,trust_env=False)
        if response.status_code>=400:raise ValueError('oMLX rejected model load: HTTP '+str(response.status_code))
    if embedding:verify_embedding(port,api_model)
    return r

def verify_embedding(port,model):
    r=httpx.post(f'http://127.0.0.1:{port}/v1/embeddings',json={'model':model,'input':['Atlas readiness check']},timeout=90,trust_env=False)
    if r.status_code>=400:raise ValueError('Embedding model did not become ready: HTTP '+str(r.status_code))
    vectors=r.json().get('data',[])
    if not vectors or not vectors[0].get('embedding'):raise ValueError('Embedding server returned no vectors')

def select(name,model_id='',context=65536):
    if name not in NAMES:raise ValueError('Unknown local engine')
    if not config()['enabled']:raise ValueError('Enable Atlas engine management first')
    if not config()['roots']:raise ValueError('Configure at least one model directory')
    if not 512<=context<=65536:raise ValueError('Managed context must be between 512 and 65536')
    model=next((m for m in local_models(name,'all') if m['id']==model_id),None) if model_id else None
    if model_id and not model:raise ValueError('Choose an installed model from the catalog')
    current=record()
    if current.get('name')==name and current.get('model')==model_id and current.get('context')==context and status()['running']:return current
    stop_all() # Previous process exits completely before any new weights are loaded.
    close_lmstudio_completely()
    if model:budget(model,context)
    if CANCEL.is_set():raise ValueError('Engine operation cancelled')
    try:
        r=launch(name,model,context)
        if r.get('waiting_model'):return r
        cfg=providers.config();cfg[name]['url']=f'http://127.0.0.1:{PORTS[name]}/v1'
        if not model or model.get('type')!='embedding':cfg[name]['model']=r.get('api_model','')
        set_setting('providers',cfg)
        return r
    except Exception:
        stop_all();raise

def submit(action,name='',model='',context=65536,confirmation=''):
    with LOCK:
        if JOB['busy']:
            if action=='stop':
                CANCEL.set();threading.Thread(target=stop_all,daemon=True).start();return dict(JOB)
            raise ValueError('An engine operation is already running')
        CANCEL.clear()
        JOB.update(busy=True,error='',message=action)
    def work():
        try:
            if action=='stop-detected':stop_external(confirmation)
            elif action=='stop':stop_all();close_lmstudio_completely()
            elif action=='select':select(name,model,context)
            else:raise ValueError('Unknown engine action')
            JOB.update(message='complete')
        except Exception as e:JOB.update(error=str(e),message='failed')
        finally:JOB['busy']=False
    threading.Thread(target=work,daemon=True).start()
    return dict(JOB)

def external_inventory():
    """Candidate inference processes only; never native application windows."""
    found=[];own=record().get('pid')
    for p in psutil.process_iter(['pid','exe','cmdline','create_time','uids']):
        try:
            info=p.info;args=info['cmdline'] or [];exe=info['exe'] or ''
            if info['uids'].real!=os.getuid() or p.pid in {os.getpid(),own}:continue
            name=None
            if Path(exe).name=='llama-server' and any('llama' in str(Path(a)) for a in args[:1]):name='llama'
            elif any(a.endswith('/omlx/cli.py') or a.endswith('/omlx-cli') for a in args[:3]) and 'serve' in args:name='omlx'
            elif any(a.endswith('/bin/vllm') or a=='vllm.entrypoints.openai.api_server' for a in args[:3]) and ('serve' in args or '--model' in args):name='vllm'
            if name:found.append({'name':name,'pid':p.pid,'created':info['create_time']})
        except (psutil.Error,OSError,TypeError):pass
    # LM Studio's own CLI is the supported way to unload its models and stop its API.
    lm_port=urllib.parse.urlsplit(providers.config()['lmstudio']['url']).port or 1234
    if Path(config()['binaries']['lmstudio']).is_file() and (listening(lm_port) or lmstudio_status()['application_running']) and record().get('name')!='lmstudio':found.append({'name':'lmstudio','port':lm_port})
    found.sort(key=lambda x:(x['name'],x.get('pid',0)))
    return {'servers':found,'confirmation':hashlib.sha256(json.dumps(found,sort_keys=True).encode()).hexdigest()}

def stop_external(confirmation):
    inventory=external_inventory()
    if confirmation!=inventory['confirmation']:raise ValueError('The server list changed; review it again before stopping')
    stop_all()
    for item in inventory['servers']:
        if item['name']=='lmstudio':
            cli=config()['binaries']['lmstudio'];current=json.loads(command([cli,'server','status','--json'],15))
            if current.get('running') and (current.get('port') or current.get('server',{}).get('port'))!=item['port']:raise ValueError('LM Studio API ownership could not be verified')
            close_lmstudio_completely()
            if listening(item['port']):raise ValueError('LM Studio API is still running')
            continue
        try:
            p=psutil.Process(item['pid'])
            if abs(p.create_time()-item['created'])>.01:raise ValueError('Process identity changed')
            family=[p]+p.children(recursive=True)
            for child in reversed(family):child.terminate()
            _,pending=psutil.wait_procs(family,timeout=8)
            for child in pending:child.kill()
            _,pending=psutil.wait_procs(pending,timeout=3)
            if pending:raise ValueError('Some inference processes are still running')
        except psutil.NoSuchProcess:pass
    remaining=external_inventory()['servers']
    if remaining:raise ValueError('Some inference services restarted or remain running; inspect the remaining service list')
    return {'released':True,'remaining':[]}
