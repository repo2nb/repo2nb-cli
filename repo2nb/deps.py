import ast
import pathlib
import subprocess
import sys
import tomllib

_IMPORT_ALIASES = {
    "cv2": "opencv-python",
    "PIL": "pillow",
    "yaml": "pyyaml",
    "sklearn": "scikit-learn",
    "skimage": "scikit-image",
    "bs4": "beautifulsoup4",
    "git": "gitpython",
    "dotenv": "python-dotenv",
}

_SUBPROCESS_TIMEOUT = 60


def _clean_requirements(lines) -> list[str]:
    """Keep plain requirement specifiers; drop comments, blanks, options (-e ., -r, --hash...)."""
    reqs = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        reqs.append(line)
    return reqs


def _export(command: list[str], repo_path: pathlib.Path) -> list[str] | None:
    tool = command[0]
    try:
        result = subprocess.run(
            command, cwd=repo_path, capture_output=True, text=True,
            timeout=_SUBPROCESS_TIMEOUT, check=False
        )
    except FileNotFoundError:
        print(f"[repo2nb] '{tool}' not found on PATH — falling back to next dependency source.")
        return None
    except subprocess.TimeoutExpired:
        print(f"[repo2nb] '{tool}' timed out — falling back to next dependency source.")
        return None
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        msg = detail[-1] if detail else f"exit code {result.returncode}"
        print(f"[repo2nb] '{tool} export' failed ({msg}) — falling back to next dependency source.")
        return None
    return _clean_requirements(result.stdout.splitlines())


def _scan_imports(repo_path: pathlib.Path, py_files: list[pathlib.Path]) -> list[str]:
    local_modules: dict[pathlib.Path, set[str]] = {}
    for path in py_files:
        local_modules.setdefault(path.parent, set()).add(path.stem)
        for directory in path.parents:
            if directory == repo_path:
                break
            local_modules.setdefault(directory.parent, set()).add(directory.name)

    roots = local_modules.get(repo_path, set()) | local_modules.get(repo_path / "src", set())
    third_party = set()
    for path in py_files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        internal = roots | local_modules.get(path.parent, set())
        mods = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mods.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods.add(node.module.split(".")[0])
        third_party.update(
            _IMPORT_ALIASES.get(name, name)
            for name in mods
            if name not in sys.stdlib_module_names and name not in internal
        )
    return sorted(third_party)


def resolve_dependencies(repo_path: pathlib.Path, tree: list) -> tuple[list[str], str]:
    """Return requirements and their source; AST results are unpinned estimates."""
    pyproject = repo_path / "pyproject.toml"
    metadata = {}
    if pyproject.is_file():
        try:
            with pyproject.open("rb") as stream:
                metadata = tomllib.load(stream)
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"Invalid {pyproject}: {error}") from error

    project = metadata.get("project", {})
    tool = metadata.get("tool", {})
    if not isinstance(project, dict) or not isinstance(tool, dict):
        raise ValueError(f"{pyproject}: project and tool must be TOML tables")

    if (repo_path / "poetry.lock").is_file() and "poetry" in tool:
        reqs = _export(
            ["poetry", "export", "--format", "requirements.txt", "--without-hashes"], repo_path
        )
        if reqs is not None:
            return reqs, "poetry.lock (via poetry export)"

    if (repo_path / "uv.lock").is_file():
        reqs = _export(
            ["uv", "export", "--format", "requirements-txt", "--no-hashes", "--no-emit-project"],
            repo_path,
        )
        if reqs is not None:
            return reqs, "uv.lock (via uv export)"

    requirements = repo_path / "requirements.txt"
    if requirements.is_file():
        return _clean_requirements(
            requirements.read_text(encoding="utf-8", errors="replace").splitlines()
        ), "requirements.txt"

    declared = project.get("dependencies")
    if declared is not None:
        if not isinstance(declared, list) or any(
            not isinstance(requirement, str) or not requirement.strip()
            for requirement in declared
        ):
            raise ValueError(f"{pyproject}: project.dependencies must be an array of requirement strings")
        return declared, "pyproject.toml (project.dependencies)"

    py_files = [f for _, files in tree for f in files if f.suffix == ".py"]
    return _scan_imports(repo_path, py_files), "AST import scan (unpinned)"
