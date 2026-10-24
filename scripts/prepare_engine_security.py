"""Create reproducible security overlays without changing vendor installations."""
import subprocess,sys,importlib.metadata
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
required={'certifi':'2026.10.23','filelock':'4.2.1','setuptools':'84.1.0','opentelemetry-api':'1.45.1','pillow':'13.0.0'}
for name,version in [('omlx','3.11'),('vllm','3.12')]:
    target=ROOT/'build'/'engine-security'/name
    installed={d.metadata['Name'].lower():d.version for d in (importlib.metadata.Distribution.at(p) for p in target.glob('*.dist-info') if p.is_dir() and not p.name.startswith('._'))}
    if all(installed.get(n)==v for n,v in required.items()):continue
    subprocess.run(['uv','pip','install','--target',str(target),'--python-version',version,'--python-platform','aarch64-apple-darwin','--no-deps','--upgrade']+[n+'=='+v for n,v in required.items()],check=True)
