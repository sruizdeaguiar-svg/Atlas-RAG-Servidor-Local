"""Real tiny-model lifecycle; isolated ports/state; never stops external engines."""
import os,sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
os.environ['RAG_STATE_DIR']='/private/tmp/atlas-engine-live-qa'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
from server.store import init
init()
from server import engines
import httpx,psutil
engines.configure({'enabled':True})
results=[]
def check(name,needle):
    item=next(m for m in engines.local_models(name) if needle in m['path'])
    before=engines.record();t=time.monotonic()
    r=engines.select(name,item['id'],1024)
    if before.get('pid'):assert not psutil.pid_exists(before['pid'])
    response=httpx.post(f'http://127.0.0.1:{r["port"]}/v1/chat/completions',json={'model':r['api_model'],'messages':[{'role':'user','content':'Reply with a short greeting.'}],'max_tokens':16,'temperature':0},timeout=90,trust_env=False)
    response.raise_for_status();answer=response.json()['choices'][0]['message']['content'];assert answer
    results.append({'engine':name,'model':item['name'],'answer':answer,'seconds':round(time.monotonic()-t,2),'pid':r.get('pid'),'rss':engines.status()['rss'],'previous_pid_closed':True})
    print(json.dumps(results[-1]),flush=True)
try:
    if '--remaining' not in sys.argv:
        check('llama','SmolLM2-135M-Instruct-Q2_K.gguf')
        check('llama','SmolLM2-135M-Instruct-Q4_K_M.gguf')
    else:
        previous=ROOT/'evidence/engine-live.json'
        if previous.exists():results.extend(json.loads(previous.read_text()).get('results',[]))
    check('omlx','mlx-community/SmolLM2-135M-Instruct')
    check('vllm','models--Qwen--Qwen3-0.6B/snapshots/')
finally:
    final=engines.record();engines.stop_all()
    cleanup=not any(engines.listening(p) for p in engines.PORTS.values())
    assert cleanup
    (ROOT/'evidence/engine-live.json').write_text(json.dumps({'results':results,'owned_ports_closed':cleanup,'final_pid_closed':not final.get('pid') or not psutil.pid_exists(final['pid'])},indent=2))
