import json
from pathlib import Path

import nbformat
import nbformat.v4 as nbf
import pytest

from repo2nb.converter import convert
from repo2nb.sync import sync


def _make_repo(tmp_path):
    repo = tmp_path / "proj"
    (repo / "src").mkdir(parents=True)
    (repo / "main.py").write_text("print('v1')\n")
    (repo / "src" / "util.py").write_text("util = 1\n")
    return repo


def _generate(repo, tmp_path):
    nb_path = tmp_path / "out.ipynb"
    convert(repo, nb_path)
    return nb_path


def _tagged_paths(nb_path):
    nb = nbformat.read(str(nb_path), as_version=4)
    return [c.metadata["repo2nb"]["path"] for c in nb.cells if "repo2nb" in c.metadata]


def _find_cell(nb, rel):
    return next(c for c in nb.cells if c.get("metadata", {}).get("repo2nb", {}).get("path") == rel)


def test_sync_no_changes(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)

    sync(repo, notebook_path=nb_path)

    assert "no changes" in capsys.readouterr().out
    assert _tagged_paths(nb_path) == [".gitignore", "main.py", "src/util.py"]


def test_sync_added_file_appended_after_last_tagged_cell(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)
    (repo / "new_mod.py").write_text("new = 1\n")

    sync(repo, notebook_path=nb_path)

    paths = _tagged_paths(nb_path)
    assert paths == [".gitignore", "main.py", "src/util.py", "new_mod.py"]
    nb = nbformat.read(str(nb_path), as_version=4)
    new_cell = _find_cell(nb, "new_mod.py")
    assert "%%writefile" in new_cell.source and "new = 1" in new_cell.source


def test_sync_modified_file_keeps_position_and_id(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)
    nb_before = nbformat.read(str(nb_path), as_version=4)
    target_idx = next(i for i, c in enumerate(nb_before.cells) if "repo2nb" in c.metadata and c.metadata["repo2nb"]["path"] == "main.py")
    cell_id = nb_before.cells[target_idx].get("id")
    old_source = nb_before.cells[target_idx].source

    (repo / "main.py").write_text("print('v2 — changed')\n")
    sync(repo, notebook_path=nb_path)

    nb_after = nbformat.read(str(nb_path), as_version=4)
    assert nb_after.cells[target_idx].source != old_source
    assert "v2 — changed" in nb_after.cells[target_idx].source
    assert nb_after.cells[target_idx].metadata["repo2nb"]["path"] == "main.py"
    if cell_id:
        assert nb_after.cells[target_idx].get("id") == cell_id


def test_sync_deleted_file_removes_cell(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)
    (repo / "src" / "util.py").unlink()

    sync(repo, notebook_path=nb_path)

    paths = _tagged_paths(nb_path)
    assert "src/util.py" not in paths


def test_sync_dry_run_touches_nothing(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)
    before = nbformat.read(str(nb_path), as_version=4)
    manifest_before = (repo / ".repo2nb" / "manifest.json").read_text()

    (repo / "main.py").write_text("print('edited')\n")
    (repo / "extra.py").write_text("x\n")

    sync(repo, notebook_path=nb_path, dry_run=True)

    after = nbformat.read(str(nb_path), as_version=4)
    assert [c.source for c in after.cells] == [c.source for c in before.cells]
    assert (repo / ".repo2nb" / "manifest.json").read_text() == manifest_before
    assert not list(tmp_path.glob("*.tmp"))


def test_sync_leaves_manual_cells_untouched(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)

    nb = nbformat.read(str(nb_path), as_version=4)
    manual = nbf.new_code_cell("# my precious manual analysis\nplot_stuff()")
    nb.cells.append(manual)
    nbformat.write(nb, str(nb_path))

    (repo / "main.py").write_text("print('v2')\n")
    (repo / "brand_new.py").write_text("n=1\n")
    sync(repo, notebook_path=nb_path)

    nb_after = nbformat.read(str(nb_path), as_version=4)
    manual_cells = [c for c in nb_after.cells if "precious manual analysis" in c.source]
    assert len(manual_cells) == 1
    assert manual_cells[0].source == manual.source


def test_sync_missing_manifest_errors_clearly(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    with pytest.raises(FileNotFoundError) as e:
        sync(repo, notebook_path=tmp_path / "out.ipynb")
    assert "run a full generation first" in str(e.value)


def test_sync_corrupted_manifest_errors_clearly(tmp_path):
    repo = _make_repo(tmp_path)
    _generate(repo, tmp_path)
    (repo / ".repo2nb" / "manifest.json").write_text("{not json!!")

    with pytest.raises(ValueError) as e:
        sync(repo, notebook_path=tmp_path / "out.ipynb")
    assert "corrupted" in str(e.value)


def test_sync_missing_notebook_errors(tmp_path):
    repo = _make_repo(tmp_path)
    _generate(repo, tmp_path)
    (tmp_path / "out.ipynb").unlink()

    with pytest.raises(SystemExit) as e:
        sync(repo)
    assert "--notebook" in str(e.value)


def test_sync_updates_manifest(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)
    (repo / "new_mod.py").write_text("new = 1\n")
    (repo / "src" / "util.py").unlink()

    sync(repo, notebook_path=nb_path)

    manifest = json.loads((repo / ".repo2nb" / "manifest.json").read_text())
    assert set(manifest["files"]) == {".gitignore", "main.py", "new_mod.py"}


def test_sync_recovers_missing_cells_and_inserts_before_manual_workspace(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)
    nb = nbformat.read(str(nb_path), as_version=4)
    nb.cells.remove(_find_cell(nb, "main.py"))
    manual = nbf.new_code_cell("print('keep my results')", metadata={"repo2nb_setup": {"custom": True}})
    manual.outputs = [nbf.new_output("stream", name="stdout", text="keep my results\n")]
    nb.cells.append(manual)
    nbformat.write(nb, str(nb_path))
    (repo / "src" / "util.py").unlink()
    (repo / "new.py").write_text("value = 2\n")

    sync(repo)

    nb = nbformat.read(str(nb_path), as_version=4)
    assert set(_tagged_paths(nb_path)) == {".gitignore", "main.py", "new.py"}
    assert nb.cells.index(_find_cell(nb, "new.py")) < next(i for i, cell in enumerate(nb.cells) if cell.id == manual.id)
    assert nb.cells[-1] == manual


def test_sync_refreshes_dependencies_and_keeps_no_deps_selection(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / "requirements.txt").write_text("numpy>=2\n")
    nb_path = _generate(repo, tmp_path)
    (repo / "requirements.txt").write_text("numpy>=2\npandas; python_version >= '3.11'\n")

    sync(repo)

    nb = nbformat.read(str(nb_path), as_version=4)
    pip_cells = [cell for cell in nb.cells if cell.metadata.get("repo2nb_setup") == "dependencies"]
    assert len(pip_cells) == 1
    assert "pandas" in pip_cells[0].source

    convert(repo, nb_path, deps=False)
    (repo / "requirements.txt").write_text("scipy\n")
    sync(repo)
    nb = nbformat.read(str(nb_path), as_version=4)
    assert not any(cell.source.startswith("%pip install") for cell in nb.cells)


def test_sync_preserves_included_files_and_resolved_notebook_path(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    (repo / "values.csv").write_text("a,b\n1,2\n")
    monkeypatch.chdir(tmp_path)
    convert(repo, Path("out.ipynb"), include={".csv"})
    (repo / "values.csv").write_text("a,b\n3,4\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    sync(repo)

    nb = nbformat.read(str(tmp_path / "out.ipynb"), as_version=4)
    assert "3,4" in _find_cell(nb, "values.csv").source


def test_sync_legacy_manifest_preserves_untagged_setup(tmp_path):
    repo = _make_repo(tmp_path)
    nb_path = _generate(repo, tmp_path)
    manifest_path = repo / ".repo2nb" / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest.pop("include")
    manifest.pop("deps")
    manifest_path.write_text(json.dumps(manifest))
    nb = nbformat.read(str(nb_path), as_version=4)
    legacy = nbf.new_code_cell("%pip install old-manual-choice")
    nb.cells.insert(0, legacy)
    nbformat.write(nb, str(nb_path))
    (repo / "main.py").write_text("import numpy\n")

    sync(repo)

    nb = nbformat.read(str(nb_path), as_version=4)
    assert nb.cells[0] == legacy
    assert any(cell.metadata.get("repo2nb_setup") == "dependencies" and "numpy" in cell.source for cell in nb.cells)
