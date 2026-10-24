"""Run vendor engines with Atlas's patched, isolated dependencies first."""
import sys,runpy,importlib.metadata
from pathlib import Path

name=sys.argv[1];root=Path(__file__).resolve().parents[1]
overlay=root/'build'/'engine-security'/name
required={'certifi':'2026.10.23','filelock':'4.2.1','setuptools':'84.1.0','opentelemetry-api':'1.45.1','pillow':'13.0.0'}
installed={d.metadata['Name'].lower():d.version for d in (importlib.metadata.Distribution.at(p) for p in overlay.glob('*.dist-info') if p.is_dir() and not p.name.startswith('._'))}
if any(installed.get(n)!=v for n,v in required.items()):raise SystemExit('Atlas engine security dependencies missing; rebuild/install the latest Atlas package')
sys.path.insert(0,str(overlay))
target=sys.argv[2];sys.argv=sys.argv[2:]
if name=='omlx':
    sys.argv[0]='omlx';runpy.run_module('omlx.cli',run_name='__main__')
else:runpy.run_path(target,run_name='__main__')
