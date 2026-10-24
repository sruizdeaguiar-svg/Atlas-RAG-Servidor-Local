"""Package the reproducible project structure without any loaded state or secrets."""
from pathlib import Path
import zipfile,json,hashlib,shutil
ROOT=Path(__file__).resolve().parents[1]
VERSION='1.1.1'
SCRIPTS=['build_app.sh','build_installer.sh','build_ios.sh','install.sh','install_ipad.sh','control.py','prepare_update.py','enable_lan.py','verify_release.py','verify_engine_lifecycle.py','mobile_qa.py','package_source.py']
files=[ROOT/n for n in ['README.md','LICENSE','NOTICE','.gitignore','requirements.txt','requirements.lock.txt','Abrir Atlas.command']]
for folder in ['server','web','native','ios']:
    files += [p for p in (ROOT/folder).rglob('*') if p.is_file() and not any(part.startswith('.') or part=='__pycache__' for part in p.relative_to(ROOT).parts) and p.suffix!='.pyc']
files += [ROOT/'scripts'/n for n in SCRIPTS]
files += list((ROOT/'tests').glob('test_*.py'))
files += [ROOT/'docs/ESTRUCTURA.md']+list((ROOT/'docs/screenshots').glob('*.png'))
files=sorted(set(files))
for p in files:
    assert p.is_file(),p
    assert p.suffix not in {'.sqlite3','.pem','.key','.mobileprovision'},p
    if p.suffix=='.ipa':
        with zipfile.ZipFile(p) as archive:assert not any('embedded.mobileprovision' in n or '_CodeSignature' in n for n in archive.namelist())
out=ROOT/'dist';out.mkdir(exist_ok=True)
archive=out/f'Atlas-RAG-{VERSION}-source.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in files:z.write(p,'Atlas-RAG-Servidor-Local/'+str(p.relative_to(ROOT)))
manifest=[{'path':str(p.relative_to(ROOT)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size} for p in files]
(out/f'Atlas-RAG-{VERSION}-source-manifest.json').write_text(json.dumps(manifest,indent=2))
export=ROOT/'publicacion';export.mkdir(exist_ok=True)
for p in files:
    dest=export/p.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)
print(json.dumps({'archive':str(archive),'files':len(files),'bytes':archive.stat().st_size,'loaded_data_included':False}))
