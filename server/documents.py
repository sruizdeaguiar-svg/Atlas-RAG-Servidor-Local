import csv, io, json, subprocess, hashlib, zipfile, tempfile, sys, os, time, signal, site
from pathlib import Path
from pypdf import PdfReader
from openpyxl import load_workbook
from docx import Document
ROOT=Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'build' / 'DocumentTools'
TEXT_EXT={'.txt','.md','.csv','.tsv','.json','.log','.r','.py','.html','.xml','.yaml','.yml'}
SUPPORTED=TEXT_EXT|{'.pdf','.xlsx','.docx'}
MAX_FILE=40*1024*1024

def file_hash(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def text_read(path):
    data=path.read_bytes()
    for enc in ('utf-8-sig','utf-16','cp1252'):
        try: return data.decode(enc)
        except UnicodeError: pass
    raise ValueError('Unsupported text encoding')

def archive_check(path):
    if path.stat().st_size>MAX_FILE:raise ValueError('File exceeds 40 MiB')
    if path.suffix.lower() not in {'.xlsx','.docx'}:return
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        if len(entries)>2048 or sum(i.file_size for i in entries)>128*1024*1024 or any(i.file_size>32*1024*1024 for i in entries):
            raise ValueError('Office document exceeds safe expanded size limits')
        if any(i.flag_bits&1 for i in entries):raise ValueError('Encrypted Office archives are not supported')

def _tables(path):
    archive_check(path)
    if path.suffix.lower()=='.xlsx':
        wb=load_workbook(path,read_only=True,data_only=True)
        out={}
        try:
            cells=0
            if len(wb.worksheets)>32:raise ValueError('Workbook exceeds 32 sheets')
            for sheet in wb:
                if sheet.max_column and sheet.max_column>256:raise ValueError('Table exceeds 256 columns')
                values=[]
                for i,r in enumerate(sheet.iter_rows(values_only=True)):
                    if i>200000: raise ValueError('Sheet exceeds 200000 rows')
                    cells+=len(r)
                    if len(r)>256 or cells>2000000:raise ValueError('Workbook exceeds safe cell limits')
                    values.append(list(r))
                out[sheet.title]=values
        finally: wb.close()
        return out
    if path.suffix.lower() in {'.csv','.tsv'}:
        t=text_read(path)
        try: dialect=csv.Sniffer().sniff(t[:8192],delimiters=',;\t')
        except csv.Error: dialect=csv.excel_tab if path.suffix.lower()=='.tsv' else csv.excel
        values=[];cells=0
        for row in csv.reader(io.StringIO(t),dialect):
            cells+=len(row)
            if len(row)>256 or len(values)>=200001 or cells>2000000:raise ValueError('Table exceeds safe row, column or cell limits')
            values.append(row)
        return {'Data':values}
    raise ValueError('Select CSV, TSV or XLSX')

def _extract(path):
    ext=path.suffix.lower()
    archive_check(path)
    if ext=='.pdf':
        reader=PdfReader(path)
        if len(reader.pages)>500: raise ValueError('PDF exceeds 500 pages')
        pages=[(f'page {i+1}',p.extract_text() or '') for i,p in enumerate(reader.pages)]
        if any(len(t.strip())<20 for _,t in pages):
            p=subprocess.run([str(TOOLS),'--ocr',str(path)],capture_output=True,text=True,timeout=180)
            if p.returncode: raise ValueError('OCR failed')
            pages=[(f"page {p['page']}"+(' (OCR)' if p['ocr'] else ''),p['text']) for p in json.loads(p.stdout)]
        return pages
    if ext in {'.csv','.tsv','.xlsx'}:
        out=[]
        for name,values in _tables(path).items():
            if not values: continue
            headers=[str(x) if x is not None else '' for x in values[0]]
            for i in range(1,len(values),12):
                text='Columns: '+ ' | '.join(headers)+'\n'+'\n'.join(' | '.join('' if x is None else str(x) for x in r) for r in values[i:i+12])
                out.append((f'sheet {name}, rows {i+1}-{min(i+12,len(values))}',text))
            if len(values)==1: out.append((f'sheet {name}, row 1',' | '.join(headers)))
        return out
    if ext=='.docx':
        d=Document(path)
        return [('document','\n'.join([p.text for p in d.paragraphs]+[' | '.join(c.text for c in r.cells) for t in d.tables for r in t.rows]))]
    if ext in TEXT_EXT: return [('text',text_read(path))]
    raise ValueError('Unsupported format')

def isolated_parse(path,mode):
    """Untrusted document parsers cannot read the library or contact the network."""
    import psutil
    path=Path(path).resolve();archive_check(path)
    with tempfile.TemporaryDirectory(prefix='atlas-document-') as tmp:
        work=Path(tmp)
        # Permit the selected file, parser code/runtime and native OCR helper only.
        readable=[path,ROOT/'server',ROOT/'build',Path(sys.prefix),Path(sys.base_prefix)]
        rules='(allow file-read* (literal '+json.dumps(str(ROOT))+'))\n'+'\n'.join('(allow file-read* ('+('literal' if p.is_file() else 'subpath')+' '+json.dumps(str(p))+'))' for p in readable)
        profile='(version 1)\n(allow default)\n(deny network*)\n(deny file-read* (subpath "/Users") (subpath "/Volumes") (subpath "/private/tmp") (subpath "/private/var/folders"))\n(allow file-read-metadata)\n'+rules+'\n(allow file-read* (subpath '+json.dumps(tmp)+'))\n(deny file-write*)\n(allow file-write* (subpath '+json.dumps(tmp)+') (literal "/dev/null"))\n(deny signal)\n(allow signal (target self))\n'
        (work/'sandbox.sb').write_text(profile)
        env={'PATH':'/usr/bin:/bin:/opt/homebrew/bin','HOME':tmp,'TMPDIR':tmp,'PYTHONDONTWRITEBYTECODE':'1','OPENPYXL_DEFUSEDXML':'True','OPENPYXL_LXML':'False','LANG':'en_US.UTF-8'}
        output=work/'result.json'
        with output.open('wb') as stream,(work/'stderr.txt').open('wb') as errors:
            process=subprocess.Popen([sys.executable,'-B',str(ROOT/'server/document_worker.py'),tmp,mode,str(path)],stdout=stream,stderr=errors,env=env,start_new_session=True)
            deadline=time.monotonic()+180
            try:
                while process.poll() is None:
                    if time.monotonic()>deadline:raise ValueError('Document parsing exceeded 180 seconds')
                    try:
                        family=[psutil.Process(process.pid)]+psutil.Process(process.pid).children(recursive=True)
                        if sum(p.memory_info().rss for p in family if p.is_running())>512*1024*1024:raise ValueError('Document parsing exceeded 512 MiB')
                    except psutil.Error:pass
                    time.sleep(.05)
            finally:
                if process.poll() is None:os.killpg(process.pid,signal.SIGKILL)
                process.wait()
        if process.returncode:raise ValueError('Document parser stopped at its safety limit: '+(work/'stderr.txt').read_text(errors='replace')[-500:])
        if output.stat().st_size>32*1024*1024:raise ValueError('Document output exceeds safe size limit')
        try:result=json.loads(output.read_text())
        except (ValueError,OSError):raise ValueError('Document parser returned invalid output')
        if not result['ok']:raise ValueError(result['error'])
        return result['data']

def tables(path):return isolated_parse(path,'tables')
def extract(path):return isolated_parse(path,'extract')

def chunks(sections):
    out=[]
    for locator,text in sections:
        for i in range(0,len(text),1000):
            part=text[max(0,i-120):i+1000].strip()
            if part: out.append((locator+f', fragment {i//1000+1}',part))
    if len(out)>10000: raise ValueError('Document exceeds 10000 chunks')
    return out

def apple_embed(texts,language):
    p=subprocess.run([str(TOOLS)],input=json.dumps({'language':language,'texts':texts}),capture_output=True,text=True,timeout=120)
    if p.returncode: raise ValueError('Apple sentence embedding unavailable for '+language)
    return json.loads(p.stdout)
