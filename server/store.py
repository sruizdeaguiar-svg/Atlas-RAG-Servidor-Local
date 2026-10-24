from pathlib import Path
import os, sqlite3, json, time, secrets, hashlib, contextlib
ROOT = Path(__file__).resolve().parents[1]
STATE = Path(os.environ.get('RAG_STATE_DIR', ROOT / 'datos')).resolve()
STATE.mkdir(parents=True, exist_ok=True)
os.chmod(STATE, 0o700)
SECRET_STATE=Path(os.environ.get('RAG_SECRET_DIR', STATE if os.environ.get('RAG_STATE_DIR') else Path.home()/'Library/Application Support/Atlas RAG Credentials')).resolve()
DB = STATE / 'rag.sqlite3'
@contextlib.contextmanager
def db():
    c = sqlite3.connect(DB, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    try:
        yield c
        c.commit()
    except BaseException:
        c.rollback(); raise
    finally: c.close()
def init():
    with db() as c:
        c.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL, active INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, expires REAL);
        CREATE TABLE IF NOT EXISTS collections(id INTEGER PRIMARY KEY, name TEXT NOT NULL, path TEXT UNIQUE NOT NULL, language TEXT DEFAULT 'es', exclusions TEXT DEFAULT '[]', autoscan INTEGER DEFAULT 0, indexed REAL, embedding TEXT DEFAULT 'apple', model TEXT DEFAULT '', status TEXT DEFAULT 'idle');
        CREATE TABLE IF NOT EXISTS grants(user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, permission TEXT, PRIMARY KEY(user_id,collection_id));
        CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, path TEXT NOT NULL, sha TEXT, size INTEGER, mtime REAL, status TEXT, error TEXT, UNIQUE(collection_id,path));
        CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, file_id INTEGER REFERENCES files(id) ON DELETE CASCADE, collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, locator TEXT, text TEXT, vector TEXT, model TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS search_fts USING fts5(text, content='chunks', content_rowid='id', tokenize='unicode61 remove_diacritics 2');
        CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN INSERT INTO search_fts(rowid,text) VALUES(new.id,new.text); END;
        CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN INSERT INTO search_fts(search_fts,rowid,text) VALUES('delete',old.id,old.text); END;
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, collection_id INTEGER REFERENCES collections(id) ON DELETE CASCADE, state TEXT, done INTEGER DEFAULT 0, total INTEGER DEFAULT 0, errors INTEGER DEFAULT 0, message TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),collection_id INTEGER REFERENCES collections(id), file_id INTEGER, question TEXT, code TEXT, plan TEXT, result TEXT, state TEXT, created REAL, source_sha TEXT);
        CREATE TABLE IF NOT EXISTS conversations(id INTEGER PRIMARY KEY,user_id INTEGER REFERENCES users(id),question TEXT,response TEXT,sources TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,user_id INTEGER,action TEXT,target TEXT,created REAL);
        ''')
        c.execute("UPDATE jobs SET state='interrupted',message='Server restarted' WHERE state IN ('queued','running')")
        c.execute("UPDATE collections SET status='idle' WHERE status='indexing'")
    SECRET_STATE.mkdir(parents=True,exist_ok=True); SECRET_STATE.chmod(0o700)
    p = SECRET_STATE / 'setup.token'
    if not p.exists():
        p.write_text(secrets.token_urlsafe(32)); p.chmod(0o600)
def setting(key, default=None):
    with db() as c: r=c.execute('SELECT value FROM settings WHERE key=?',(key,)).fetchone()
    return json.loads(r[0]) if r else default
def set_setting(key,value):
    with db() as c: c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(key,json.dumps(value)))
def audit(uid,action,target=''):
    with db() as c: c.execute('INSERT INTO audit(user_id,action,target,created) VALUES(?,?,?,?)',(uid,action,str(target),time.time()))
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def password_hash(password):
    salt=secrets.token_hex(16)
    return salt+':'+hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()
def password_ok(password, stored):
    salt, expected=stored.split(':')
    return secrets.compare_digest(hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex(),expected)
def rows(sql,args=()):
    with db() as c: return [dict(r) for r in c.execute(sql,args)]
