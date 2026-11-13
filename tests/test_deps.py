import subprocess
from types import SimpleNamespace

import pytest

from repo2nb.deps import resolve_dependencies
from repo2nb.traversal import traverse


def test_scan_imports_excludes_project_modules_without_hiding_external_names(tmp_path):
    sources = {
        "main.py": (
            "import os\nimport numpy\nfrom mylib import x\nimport yaml\nimport cv2\n"
            "from acme import model\nfrom namespace.module import value\n"
            "import requests\nimport pandas\n"
        ),
        "mylib/__init__.py": "from . import mod\n",
        "mylib/mod.py": "import PIL\n",
        "src/acme/__init__.py": "",
        "src/acme/model.py": "",
        "src/namespace/module.py": "",
        "tools/run.py": "import helper\nfrom sibling.module import value\n",
        "tools/helper.py": "",
        "tools/sibling/module.py": "",
        "tests/requests.py": "",
        "pandas.txt": "Not a Python module",
    }
    for relative, content in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    requirements, source = resolve_dependencies(tmp_path, traverse(tmp_path)[0])

    assert requirements == ["numpy", "opencv-python", "pandas", "pillow", "pyyaml", "requests"]
    assert source == "AST import scan (unpinned)"


def test_scan_imports_syntax_error_file_skipped(tmp_path):
    (tmp_path / "bad.py").write_text("def broken(:")
    (tmp_path / "app.py").write_text("import requests\n")
    assert resolve_dependencies(tmp_path, traverse(tmp_path)[0])[0] == ["requests"]


def test_resolution_requirements_txt(tmp_path):
    (tmp_path / "requirements.txt").write_text(
        "numpy==1.26\n-e .\n-r other.txt\n--hash=abc\n\n# comment\nscipy\n"
    )
    requirements, source = resolve_dependencies(tmp_path, traverse(tmp_path)[0])
    assert requirements == ["numpy==1.26", "scipy"]
    assert source == "requirements.txt"


@pytest.mark.parametrize("failure", ["missing", "timeout", "nonzero"])
def test_export_failure_falls_back_to_requirements(tmp_path, monkeypatch, failure):
    (tmp_path / "poetry.lock").touch()
    (tmp_path / "pyproject.toml").write_text("[tool.poetry]\nname = 'x'\n")
    (tmp_path / "requirements.txt").write_text("requests\n")

    def fail(command, **kwargs):
        if failure == "missing":
            raise FileNotFoundError("poetry")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 60)
        return SimpleNamespace(returncode=1, stdout="", stderr="export unavailable")

    monkeypatch.setattr("subprocess.run", fail)
    assert resolve_dependencies(tmp_path, traverse(tmp_path)[0]) == (["requests"], "requirements.txt")


@pytest.mark.parametrize("tool", ["poetry", "uv"])
def test_export_runs_in_converted_repository(tmp_path, monkeypatch, tool):
    (tmp_path / f"{tool}.lock").touch()
    (tmp_path / "pyproject.toml").write_text(f"[tool.{tool}]\n")
    calls = []

    def export(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="flask==3.0\n", stderr="")

    monkeypatch.setattr("subprocess.run", export)
    requirements, source = resolve_dependencies(tmp_path, traverse(tmp_path)[0])
    assert requirements == ["flask==3.0"]
    assert source.startswith(f"{tool}.lock")
    assert calls[0][0][0] == tool
    assert calls[0][1]["cwd"] == tmp_path


def test_poetry_lock_without_tool_section_skips_poetry(tmp_path, monkeypatch):
    (tmp_path / "poetry.lock").touch()

    def unexpected_export(command, **kwargs):
        raise AssertionError("poetry should not be called")

    monkeypatch.setattr("subprocess.run", unexpected_export)
    assert resolve_dependencies(tmp_path, traverse(tmp_path)[0]) == ([], "AST import scan (unpinned)")


@pytest.mark.parametrize("declared", [[], ["requests>=2", "pillow; python_version >= '3.11'"]])
def test_declared_project_dependencies_are_authoritative(tmp_path, declared):
    (tmp_path / "pyproject.toml").write_text(f"[project]\ndependencies = {declared!r}\n")
    (tmp_path / "app.py").write_text("import undeclared\n")
    assert resolve_dependencies(tmp_path, traverse(tmp_path)[0]) == (
        declared, "pyproject.toml (project.dependencies)"
    )


def test_requirements_precede_project_metadata(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies = ['requests']\n")
    (tmp_path / "requirements.txt").write_text("requests==2.32\n")
    assert resolve_dependencies(tmp_path, traverse(tmp_path)[0]) == (
        ["requests==2.32"], "requirements.txt"
    )


def test_dynamic_project_dependencies_fall_back_to_import_scan(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\ndynamic = ['dependencies']\n")
    (tmp_path / "app.py").write_text("import sklearn\n")
    assert resolve_dependencies(tmp_path, traverse(tmp_path)[0]) == (
        ["scikit-learn"], "AST import scan (unpinned)"
    )


@pytest.mark.parametrize("metadata", [
    "[project", "[project]\ndependencies = 'requests'", "[project]\ndependencies = [1]",
    "project = false", "tool = 1",
])
def test_invalid_project_metadata_fails_with_its_path(tmp_path, metadata):
    (tmp_path / "pyproject.toml").write_text(metadata)
    with pytest.raises(ValueError, match="pyproject.toml"):
        resolve_dependencies(tmp_path, traverse(tmp_path)[0])


def test_nothing_found_returns_empty(tmp_path):
    assert resolve_dependencies(tmp_path, traverse(tmp_path)[0]) == ([], "AST import scan (unpinned)")
