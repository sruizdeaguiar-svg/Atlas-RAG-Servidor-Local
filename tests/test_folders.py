from pathlib import Path
import pytest
from server import folders

@pytest.fixture
def tree(tmp_path,monkeypatch):
    root=tmp_path/'documents';root.mkdir()
    private=root/'private';private.mkdir()
    vault=root/'vault';vault.mkdir()
    monkeypatch.setattr(folders,'roots',lambda:[root])
    monkeypatch.setattr(folders,'STATE',private)
    monkeypatch.setattr(folders,'SECRET_STATE',vault)
    return root

def test_browser_only_lists_visible_directories(tree):
    (tree/'Research').mkdir();(tree/'notes.txt').write_text('example')
    (tree/'.hidden').mkdir();(tree/'alias').symlink_to(tree/'Research',target_is_directory=True)
    result=folders.browse(str(tree))
    assert [d['name'] for d in result['directories']]==['Research']
    assert result['selectable']

def test_browser_rejects_outside_and_private_paths(tree):
    for p in [tree.parent,tree/'private',tree/'vault']:
        with pytest.raises(ValueError):folders.browse(str(p))
    (tree/'escape').symlink_to(tree.parent,target_is_directory=True)
    with pytest.raises(ValueError):folders.browse(str(tree/'escape'))

def test_browser_filter_name_and_parent(tree):
    (tree/'Research').mkdir();(tree/'Other').mkdir()
    assert [d['name'] for d in folders.browse(str(tree),'SEARCH')['directories']]==['Research']
    child=folders.browse(str(tree/'Research'))
    assert child['name']=='Research' and child['parent']==str(tree)
    assert folders.browse()['directories'][0]['path']==str(tree)
