"""Directory-only browser for authenticated Atlas administrators."""
import os
from pathlib import Path
from .store import ROOT,STATE,SECRET_STATE

def roots():
    home=Path.home()
    return [p for p in [Path('/Volumes'),home/'Documents',home/'Desktop',home/'Downloads'] if p.is_dir()]

def protected(path):
    return any(path==p or path.is_relative_to(p) for p in [STATE,SECRET_STATE])

def browse(path='',query=''):
    bases=[p.resolve() for p in roots()]
    if not path:
        return {'path':'','parent':None,'name':'','selectable':False,'directories':[{'name':p.name,'path':str(p)} for p in bases],'truncated':False}
    p=Path(path).expanduser().resolve()
    if not any(p==root or p.is_relative_to(root) for root in bases) or protected(p):raise ValueError('Select an accessible document folder on the Mac')
    if not p.is_dir():raise ValueError('Folder no longer exists')
    entries=[];scanned=0;query=query.casefold()
    try:
        with os.scandir(p) as listing:
            for item in listing:
                scanned+=1
                if scanned>20000:break
                if item.name.startswith('.') or query not in item.name.casefold():continue
                try:
                    candidate=p/item.name
                    if item.is_dir(follow_symlinks=False) and not item.is_symlink() and not protected(candidate):entries.append({'name':item.name,'path':str(candidate)})
                except OSError:continue
    except PermissionError:raise ValueError('macOS denied access to this folder. Select it once from Atlas on the Mac to authorize access.')
    entries.sort(key=lambda e:e['name'].casefold())
    parent=str(p.parent) if any(p.parent==root or p.parent.is_relative_to(root) for root in bases) else ''
    return {'path':str(p),'parent':parent,'name':p.name,'selectable':p not in {Path('/Volumes'),Path.home(),ROOT},'directories':entries[:500],'truncated':len(entries)>500 or scanned>20000}
