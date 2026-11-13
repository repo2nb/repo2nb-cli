import pathlib

from pathspec import GitIgnoreSpec
from pathspec.patterns.gitwildmatch import GitWildMatchPatternError

DEFAULT_IGNORE = [
    "__pycache__", "*.pyc", "node_modules", ".DS_Store", "venv", ".venv", ".env", "*.egg-info", "dist", "build", ".git", ".pytest_cache", ".hypothesis", ".coverage",
    "uv.lock", ".python-version", "pyproject.toml",
    ".repo2nb", ".repo2nbignore"
]

IGNORE_FILENAME = ".repo2nbignore"


def is_binary(file_path: pathlib.Path, include: set = None) -> bool:
    binary_extensions = {
        '.pkl', '.pt', '.h5', '.png', '.jpg', '.jpeg', '.gif', '.zip', '.tar', '.gz',
        '.csv', '.tsv', '.xlsx', '.xls', '.parquet', '.db', '.sqlite', '.pdf', '.ipynb',
    }
    include_exts = {'.' + ext.lower().lstrip('.') for ext in include or []}
    return file_path.suffix.lower() in binary_extensions - include_exts


def read_text_files(repo_path: pathlib.Path, tree: list, include: set = None) -> dict:
    contents = {}
    for _, files in tree:
        for path in files:
            if is_binary(path, include):
                continue
            try:
                contents[path.relative_to(repo_path).as_posix()] = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
    return contents


def _parse_lines(lines, source):
    """Yield valid gitignore-pattern lines; warn and skip malformed ones."""
    for line in lines:
        stripped = line.rstrip("\n")
        if not stripped.strip() or stripped.lstrip().startswith("#"):
            continue
        try:
            GitIgnoreSpec.from_lines([stripped])
        except GitWildMatchPatternError as e:
            print(f"[repo2nb] WARNING: skipping malformed line in {source}: {stripped!r} ({e})")
            continue
        yield stripped


def load_ignore_spec(repo_path: pathlib.Path, extra_ignore=None) -> GitIgnoreSpec:
    lines = list(DEFAULT_IGNORE)
    for ext in sorted(extra_ignore or []):
        ext = ext.lower()
        lines.append("*" + ext if ext.startswith(".") else "*" + ext)
    ignore_file = repo_path / IGNORE_FILENAME
    if ignore_file.is_file():
        raw = ignore_file.read_text(encoding="utf-8", errors="replace").splitlines()
        lines.extend(_parse_lines(raw, IGNORE_FILENAME))
    return GitIgnoreSpec.from_lines(lines)


def traverse(root_path: pathlib.Path, extra_ignore=None) -> tuple[list, bool]:
    has_git = (root_path / ".git").is_dir()
    spec = load_ignore_spec(root_path, extra_ignore)

    def ignored(rel: str) -> bool:
        return spec.match_file(rel) or spec.match_file(rel + "/")

    tree = []

    def _walk(current_path: pathlib.Path):
        files = []
        dirs = []
        for child in sorted(current_path.iterdir()):
            rel = child.relative_to(root_path).as_posix()
            if ignored(rel):
                continue
            if child.is_symlink():
                print(f"[repo2nb] WARNING: skipping symlink '{rel}' to keep traversal inside the repository.")
                continue
            if child.is_dir():
                dirs.append(child)
            else:
                files.append(child)

        tree.append((current_path, files))
        for d in dirs:
            _walk(d)

    _walk(root_path)
    return tree, has_git
