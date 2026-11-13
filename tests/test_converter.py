import pathlib
import shlex

import nbformat
import pytest

from repo2nb.converter import convert


def _make_repo(tmp_path):
    repo_path = tmp_path / "my_project"
    repo_path.mkdir()
    (repo_path / "test.py").write_text("print('hello')")
    return repo_path


def test_converter_no_git(tmp_path):
    repo_path = _make_repo(tmp_path)
    output_path = tmp_path / "out.ipynb"

    convert(repo_path, output_path)

    assert output_path.exists()
    nb = nbformat.read(str(output_path), as_version=4)
    cells = nb.cells

    writefile_cells = [c for c in cells if "repo2nb" in c.metadata]
    assert [c.metadata["repo2nb"]["path"] for c in writefile_cells] == [".gitignore", "test.py"]
    assert "/kaggle/working/test.py" in writefile_cells[1].source

    for cell in cells:
        assert "SECURITY & PUBLISHING WARNING" not in cell.source


def test_converter_depth(tmp_path):
    repo_path = tmp_path / "my_project"
    repo_path.mkdir()
    (repo_path / "test0.py").touch()

    sub_dir = repo_path / "level1"
    sub_dir.mkdir()
    (sub_dir / "test1.py").touch()

    sub_sub_dir = sub_dir / "level2"
    sub_sub_dir.mkdir()
    (sub_sub_dir / "test2.py").touch()

    output_path = tmp_path / "out.ipynb"
    convert(repo_path, output_path)

    nb = nbformat.read(str(output_path), as_version=4)
    markdown_sources = [c.source for c in nb.cells if c.cell_type == "markdown"]
    assert "# 📁 my_project" in markdown_sources
    assert "## 📁 level1" in markdown_sources
    assert "### 📁 level2" in markdown_sources


def test_converter_writes_manifest_and_gitignore(tmp_path):
    repo_path = _make_repo(tmp_path)

    convert(repo_path, tmp_path / "out.ipynb")

    manifest_path = repo_path / ".repo2nb" / "manifest.json"
    assert manifest_path.exists()
    gitignore = repo_path / ".gitignore"
    assert gitignore.exists()
    content = gitignore.read_text()
    assert ".virtual_documents/" in content
    assert ".repo2nb/" in content
    assert "sample_data" not in content


def test_converter_colab_gitignore_targets_sample_data(tmp_path):
    repo_path = _make_repo(tmp_path)

    convert(repo_path, tmp_path / "out.ipynb", target_name="colab")

    content = (repo_path / ".gitignore").read_text()
    assert "sample_data/" in content
    assert ".repo2nb/" in content
    assert ".virtual_documents" not in content


def test_converter_target_colab(tmp_path):
    repo_path = _make_repo(tmp_path)

    convert(repo_path, tmp_path / "out.ipynb", target_name="colab")

    nb = nbformat.read(str(tmp_path / "out.ipynb"), as_version=4)
    writefile_cells = [c for c in nb.cells if "repo2nb" in c.metadata]
    assert any("/content/test.py" in c.source for c in writefile_cells)
    assert nb.metadata["repo2nb"]["target"] == "colab"


def test_converter_setup_section_collapsed(tmp_path):
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    (repo_path / ".git").mkdir()
    (repo_path / "a.py").write_text("import numpy\nx = 1")

    convert(repo_path, tmp_path / "out.ipynb")

    nb = nbformat.read(str(tmp_path / "out.ipynb"), as_version=4)
    sources = [c.source for c in nb.cells]
    assert any("repo2nb setup (safe to collapse)" in s for s in sources)
    pip_cells = [c for c in nb.cells if c.source.startswith("%pip install")]
    assert len(pip_cells) == 1
    assert "numpy" in pip_cells[0].source
    assert pip_cells[0].metadata.get("jupyter", {}).get("source_hidden") is True


def test_converter_no_deps_flag(tmp_path):
    repo_path = tmp_path / "proj"
    repo_path.mkdir()
    (repo_path / "a.py").write_text("import numpy")

    convert(repo_path, tmp_path / "out.ipynb", deps=False)

    nb = nbformat.read(str(tmp_path / "out.ipynb"), as_version=4)
    assert not [c for c in nb.cells if "%pip install" in c.source]


def test_converter_reconstructs_nested_paths_with_spaces_in_clean_runtime(tmp_path, monkeypatch):
    from repo2nb.targets import kaggle

    repo = _make_repo(tmp_path)
    nested = repo / "source files" / "deep" / "my module.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("value = 'nested'\n")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setattr(kaggle, "WORKDIR_PREFIX", str(runtime) + "/")
    out = tmp_path / "out.ipynb"

    convert(repo, out)

    nb = nbformat.read(str(out), as_version=4)
    for cell in nb.cells:
        if cell.metadata.get("repo2nb_setup") == "directories":
            exec(cell.source, {})
        elif "repo2nb" in cell.metadata:
            magic, content = cell.source.split("\n", 1)
            command, destination = shlex.split(magic)
            assert command == "%%writefile"
            pathlib.Path(destination).write_text(content)
    assert (runtime / "source files" / "deep" / "my module.py").read_text() == nested.read_text()


def test_converter_failed_write_preserves_existing_notebook_and_neighbor(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path)
    out = tmp_path / "out.ipynb"
    out.write_text("existing notebook")
    neighbor = tmp_path / "out.ipynb.tmp"
    neighbor.write_text("user data")

    def failed_write(nb, stream):
        stream.write("partial notebook")
        raise OSError("disk full")

    monkeypatch.setattr("repo2nb.notebook.nbformat.write", failed_write)
    with pytest.raises(OSError, match="disk full"):
        convert(repo, out)

    assert out.read_text() == "existing notebook"
    assert neighbor.read_text() == "user data"
    assert not list(tmp_path.glob(".out.ipynb.*.tmp"))
    assert not (repo / ".repo2nb" / "manifest.json").exists()
