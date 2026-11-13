import hashlib
import pathlib
import shlex
import tempfile
from datetime import datetime, timezone

import nbformat
import nbformat.v4 as nbf

from . import __version__

SETUP_HEADER = "## 🔧 repo2nb setup (safe to collapse)\n\nDependency installation and platform setup. Collapsed where the viewer supports it — expand if you need to debug."


def content_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_markdown_cell(text: str) -> nbformat.NotebookNode:
    return nbf.new_markdown_cell(text)


def make_code_cell(code: str) -> nbformat.NotebookNode:
    return nbf.new_code_cell(code)


def make_writefile_cell(filepath: str, content: str, prefix: str = "/kaggle/working/") -> nbformat.NotebookNode:
    code = f"%%writefile {shlex.quote(prefix + filepath)}\n{content}"
    cell = make_code_cell(code)
    cell.metadata["repo2nb"] = {
        "path": filepath,
        "hash": content_hash(content),
        "generated_by": __version__,
    }
    return cell


def make_pip_cell(requirements: list) -> nbformat.NotebookNode:
    cell = make_code_cell("%pip install -q " + shlex.join(requirements))
    cell.metadata["repo2nb_setup"] = "dependencies"
    return cell


def make_directory_cell(paths, prefix: str) -> nbformat.NotebookNode | None:
    directories = sorted({str(pathlib.PurePosixPath(prefix) / pathlib.PurePosixPath(path).parent)
                          for path in paths if pathlib.PurePosixPath(path).parent != pathlib.PurePosixPath(".")})
    if not directories:
        return None
    cell = make_code_cell(
        "from pathlib import Path\n"
        f"for directory in {directories!r}:\n"
        "    Path(directory).mkdir(parents=True, exist_ok=True)"
    )
    cell.metadata["repo2nb_setup"] = "directories"
    return cell


def write_notebook(notebook: nbformat.NotebookNode, path: pathlib.Path):
    stream = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent,
        prefix=f".{path.name}.", suffix=".tmp", delete=False,
    )
    tmp = pathlib.Path(stream.name)
    try:
        with stream:
            nbformat.write(notebook, stream)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)


def assemble_notebook(cells: list, target: str = "kaggle") -> nbformat.NotebookNode:
    nb = nbf.new_notebook()
    nb.cells = cells
    nb.metadata["repo2nb"] = {
        "version": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
    }
    return nb
