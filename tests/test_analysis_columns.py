import os
os.environ.setdefault("RAG_STATE_DIR","/private/tmp/atlas-rag-boundary-state")
import pytest
from server.analysis import Plan,compile_r

def test_correlation_accepts_all_256_importable_columns():
    columns=[f'x{i}' for i in range(256)]
    plan=Plan(method='correlation',columns=columns)
    code=compile_r(plan,{'columns':[{'name':c,'type':'number'} for c in columns]})
    assert '"x255"' in code
    with pytest.raises(ValueError):Plan(method='correlation',columns=columns+['x256'])

def test_real_r_runs_25_selected_variables():
    import uuid,math
    from server import analysis
    from server.store import STATE
    columns=[f'x{i}' for i in range(25)]
    work=STATE/'analyses'/uuid.uuid4().hex;work.mkdir(parents=True)
    (work/'input.csv').write_text(','.join(columns)+'\n'+'\n'.join(','.join(str(round(math.sin(row+i)+row/20,6)) for i in range(25)) for row in range(60))+'\n')
    (work/'analysis.R').write_text(compile_r(Plan(method='correlation',columns=columns),{'columns':[{'name':c,'type':'number'} for c in columns]}))
    r=analysis.run(work.name)
    assert r['state']=='complete' and 'x24' in r['result']

def test_real_r_preserves_output_above_old_200000_character_limit():
    import uuid
    from server import analysis
    from server.store import STATE
    work=STATE/'analyses'/uuid.uuid4().hex;work.mkdir(parents=True)
    (work/'input.csv').write_text('x\n1\n')
    (work/'analysis.R').write_text('cat(strrep("FICTITIOUS OUTPUT ", 40000)); cat("\\nFINAL_SENTINEL_FULL_OUTPUT\\n")')
    r=analysis.run(work.name)
    assert r['state']=='complete' and len(r['result'])>600000
    assert r['result'].endswith('FINAL_SENTINEL_FULL_OUTPUT\n')
    assert (work/'result.txt').read_text()==r['result']
