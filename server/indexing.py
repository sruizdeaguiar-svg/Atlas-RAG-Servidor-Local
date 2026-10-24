import os, json, fnmatch, threading, time, uuid, math, re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from .store import db, rows, STATE, set_setting
from .documents import SUPPORTED, file_hash, extract, chunks, apple_embed
from .providers import embed
POOL=ThreadPoolExecutor(max_workers=2,thread_name_prefix='rag-index')
LOCK=threading.Lock(); CANCEL={}

def update(job,**kw):
    with db() as c: c.execute('UPDATE jobs SET '+','.join(k+'=?' for k in kw)+' WHERE id=?',(*kw.values(),job))

def start(cid,uid,force=False):
    with LOCK:
        if rows("SELECT id FROM jobs WHERE collection_id=? AND state IN ('queued','running')",(cid,)): raise ValueError('Collection already indexing')
        if uid: set_setting('index_owner_'+str(cid),uid)
        job=uuid.uuid4().hex; CANCEL[job]=threading.Event()
        with db() as c: c.execute('INSERT INTO jobs(id,collection_id,state,created) VALUES(?,?,?,?)',(job,cid,'queued',time.time()))
        POOL.submit(index,job,cid,uid,force)
    return job

def index(job,cid,uid,force=False):
    done=errors=0
    try:
        col=rows('SELECT * FROM collections WHERE id=?',(cid,))[0]; root=Path(col['path'])
        if not root.is_dir(): raise ValueError('Collection folder unavailable; existing index preserved')
        excludes=json.loads(col['exclusions']); candidates=[]
        for parent,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if not d.startswith('.') and not Path(parent,d).is_symlink() and not any(fnmatch.fnmatch(str(Path(parent,d).relative_to(root)),x) for x in excludes)]
            for name in files:
                p=Path(parent,name); rel=str(p.relative_to(root))
                if name.startswith('.') or p.is_symlink() or p.suffix.lower() not in SUPPORTED or any(fnmatch.fnmatch(rel,x) for x in excludes): continue
                if not p.resolve().is_relative_to(root): continue
                candidates.append((p,rel))
                if len(candidates)>50000: raise ValueError('Collection exceeds 50000 supported files')
        update(job,state='running',total=len(candidates),message='Indexing')
        with db() as c: c.execute("UPDATE collections SET status='indexing' WHERE id=?",(cid,))
        seen=set()
        for path,rel in candidates:
            if CANCEL[job].is_set(): break
            seen.add(rel); sha=''; stat=path.stat()
            try:
                sha=file_hash(path)
                old=rows('SELECT * FROM files WHERE collection_id=? AND path=?',(cid,rel))
                if old and old[0]['sha']==sha and old[0]['status']=='indexed' and not force:
                    done+=1; update(job,done=done); continue
                segments=chunks(extract(path))
                if not segments: raise ValueError('No extractable text')
                vectors=[]; model=''
                if col['embedding']!='none':
                    for i in range(0,len(segments),32):
                        texts=[x[1] for x in segments[i:i+32]]
                        e=apple_embed(texts,col['language']) if col['embedding']=='apple' else embed(uid,col['embedding'],col['model'],texts)
                        if model and model!=e['model']: raise ValueError('Embedding model changed during indexing')
                        model=e['model']; vectors.extend(e['vectors'])
                # One file is replaced atomically; no stale chunks survive a failed replacement.
                with db() as c:
                    c.execute('INSERT INTO files(collection_id,path,sha,size,mtime,status,error) VALUES(?,?,?,?,?,?,?) ON CONFLICT(collection_id,path) DO UPDATE SET sha=excluded.sha,size=excluded.size,mtime=excluded.mtime,status=excluded.status,error=excluded.error',(cid,rel,sha,stat.st_size,stat.st_mtime,'indexed',''))
                    fid=c.execute('SELECT id FROM files WHERE collection_id=? AND path=?',(cid,rel)).fetchone()[0]
                    c.execute('DELETE FROM chunks WHERE file_id=?',(fid,))
                    for i,(locator,text) in enumerate(segments): c.execute('INSERT INTO chunks(file_id,collection_id,locator,text,vector,model) VALUES(?,?,?,?,?,?)',(fid,cid,locator,text,json.dumps(vectors[i]) if vectors else None,model))
            except Exception as exc:
                errors+=1
                with db() as c:
                    c.execute('INSERT INTO files(collection_id,path,sha,size,mtime,status,error) VALUES(?,?,?,?,?,?,?) ON CONFLICT(collection_id,path) DO UPDATE SET status=excluded.status,error=excluded.error',(cid,rel,sha,stat.st_size,stat.st_mtime,'error',str(exc)[:300]))
                    c.execute('DELETE FROM chunks WHERE file_id IN (SELECT id FROM files WHERE collection_id=? AND path=?)',(cid,rel))
            done+=1; update(job,done=done,errors=errors,message=rel)
        cancelled=CANCEL[job].is_set()
        if not cancelled:
            with db() as c:
                for f in c.execute('SELECT id,path FROM files WHERE collection_id=?',(cid,)).fetchall():
                    if f['path'] not in seen: c.execute('DELETE FROM files WHERE id=?',(f['id'],))
                c.execute('UPDATE collections SET indexed=? WHERE id=?',(time.time(),cid))
        update(job,state='cancelled' if cancelled else 'complete',errors=errors,message='Cancelled' if cancelled else 'Index complete')
    except Exception as exc: update(job,state='failed',message=str(exc)[:300])
    finally:
        with db() as c: c.execute("UPDATE collections SET status='idle' WHERE id=?",(cid,))
        CANCEL.pop(job,None)

def search(query,ids,uid,mode='hybrid',limit=12):
    if not ids: return []
    placeholders=','.join('?' for _ in ids)
    tokens=re.findall(r'\w+',query,flags=re.UNICODE)[:30]
    lexical=[]
    if tokens and mode!='semantic':
        match=' OR '.join('"'+t.replace('"','')+'"' for t in tokens)
        lexical=rows(f'''SELECT c.id,c.file_id,c.collection_id,c.locator,c.text,f.path,f.sha,co.name AS collection_name,bm25(search_fts) AS rank FROM search_fts JOIN chunks c ON c.id=search_fts.rowid JOIN files f ON f.id=c.file_id JOIN collections co ON co.id=c.collection_id WHERE search_fts MATCH ? AND c.collection_id IN ({placeholders}) ORDER BY rank LIMIT 80''',(match,*ids))
    semantic=[]; warnings=[]
    if mode!='text':
        for col in rows(f'SELECT * FROM collections WHERE id IN ({placeholders})',ids):
            if col['embedding']=='none': continue
            try:
                e=apple_embed([query],col['language']) if col['embedding']=='apple' else embed(uid,col['embedding'],col['model'],[query])
                q=e['vectors'][0]; qn=math.sqrt(sum(x*x for x in q)) or 1
                candidates=rows('''SELECT c.id,c.file_id,c.collection_id,c.locator,c.text,c.vector,c.model,f.path,f.sha,co.name AS collection_name FROM chunks c JOIN files f ON f.id=c.file_id JOIN collections co ON co.id=c.collection_id WHERE c.collection_id=? AND c.vector IS NOT NULL AND c.model=?''',(col['id'],e['model']))
                for r in candidates:
                    v=json.loads(r.pop('vector')); r.pop('model',None)
                    if len(v)!=len(q): continue
                    r['similarity']=sum(a*b for a,b in zip(q,v))/(qn*(math.sqrt(sum(x*x for x in v)) or 1))
                    semantic.append(r)
            except ValueError as exc: warnings.append(str(exc))
        semantic.sort(key=lambda r:r['similarity'],reverse=True); semantic=semantic[:80]
    combined={}; scores={}
    for listing in (lexical,semantic):
        for rank,r in enumerate(listing):
            combined[r['id']]=r; scores[r['id']]=scores.get(r['id'],0)+1/(60+rank)
    result=sorted(combined.values(),key=lambda r:scores[r['id']],reverse=True)[:limit]
    for r in result: r['score']=round(scores[r['id']],5)
    return result
