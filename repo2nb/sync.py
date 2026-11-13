import pathlib
import sys

import nbformat

from .deps import resolve_dependencies
from .notebook import (
    SETUP_HEADER,
    content_hash,
    make_directory_cell,
    make_markdown_cell,
    make_pip_cell,
    make_writefile_cell,
    write_notebook,
)
from .state import load_manifest, save_manifest
from .targets import get_target
from .traversal import read_text_files, traverse


def _file_path(cell):
    tag = cell.get("metadata", {}).get("repo2nb")
    return tag.get("path") if isinstance(tag, dict) and isinstance(tag.get("path"), str) else None


def _replace_source(cell, replacement):
    cell.source = replacement.source
    cell.metadata.update(replacement.metadata)
    cell.outputs = []
    cell.execution_count = None


def _sync_setup(nb, requirements, contents, target) -> bool:
    desired = {}
    if requirements:
        desired["dependencies"] = make_pip_cell(requirements)
    directory_cell = make_directory_cell(contents, target.WORKDIR_PREFIX)
    if directory_cell is not None:
        desired["directories"] = directory_cell

    changed = False
    for cell in list(nb.cells):
        kind = cell.metadata.get("repo2nb_setup")
        if kind not in ("dependencies", "directories"):
            continue
        replacement = desired.pop(kind, None)
        if replacement is None:
            nb.cells.remove(cell)
            changed = True
        elif cell.source != replacement.source:
            _replace_source(cell, replacement)
            changed = True

    if desired:
        header = next((cell for cell in nb.cells if cell.metadata.get("repo2nb_setup") == "header"), None)
        if header is None:
            insert_at = next((i for i, cell in enumerate(nb.cells)
                              if cell.metadata.get("repo2nb_section") == "files" or _file_path(cell)), len(nb.cells))
            header = make_markdown_cell(SETUP_HEADER)
            header.metadata["repo2nb_setup"] = "header"
            nb.cells.insert(insert_at, header)
        insert_at = nb.cells.index(header) + 1
        for offset, cell in enumerate(desired.values()):
            cell.metadata.update(target.collapse_metadata())
            nb.cells.insert(insert_at + offset, cell)
        changed = True
    return changed


def _diff(current: dict, old: dict) -> tuple[list, list, list]:
    added = sorted(set(current) - set(old))
    deleted = sorted(set(old) - set(current))
    modified = sorted(r for r in set(current) & set(old) if current[r] != old[r])
    return added, modified, deleted


def _report(added, modified, deleted):
    for rel in added:
        print(f"  + added:    {rel}")
    for rel in modified:
        print(f"  ~ modified: {rel}")
    for rel in deleted:
        print(f"  - deleted:  {rel}")
    if not (added or modified or deleted):
        print("  (no changes — notebook already up to date)")


def sync(repo_path: pathlib.Path, notebook_path: pathlib.Path = None, dry_run: bool = False,
         ignore_extra: set = None):
    manifest = load_manifest(repo_path)

    target = get_target(manifest.get("target", "kaggle"))
    nb_path = pathlib.Path(notebook_path or manifest.get("notebook", ""))
    if not nb_path.is_file():
        sys.exit(f"[repo2nb] Target notebook '{nb_path}' not found. Pass --notebook PATH.")

    exclusions = set(manifest.get("ignore_extra") or []) if ignore_extra is None else set(ignore_extra)
    tree, _ = traverse(repo_path, extra_ignore=exclusions)
    contents = read_text_files(repo_path, tree, set(manifest.get("include") or []))
    current = {rel: content_hash(content) for rel, content in contents.items()}
    nb = nbformat.read(str(nb_path), as_version=4)
    index = {}
    for cell in nb.cells:
        rel = _file_path(cell)
        if rel:
            if rel in index:
                sys.exit(f"[repo2nb] Duplicate file cell for '{rel}' — remove the duplicate before syncing.")
            index[rel] = cell
    replacements = {rel: make_writefile_cell(rel, content, prefix=target.WORKDIR_PREFIX)
                    for rel, content in contents.items()}
    added, modified, deleted = _diff(
        {rel: cell.source for rel, cell in replacements.items()},
        {rel: cell.source for rel, cell in index.items()},
    )
    requirements = resolve_dependencies(repo_path, tree)[0] if manifest.get("deps", True) else []
    setup_changed = _sync_setup(nb, requirements, contents, target)

    action = "Would update" if dry_run else "Updating"
    print(f"[repo2nb] {action} {nb_path}:")
    if added or modified or deleted or not setup_changed:
        _report(added, modified, deleted)
    if setup_changed:
        print("  ~ updated:  generated setup cells")
    if dry_run:
        print("[repo2nb] Dry run — no changes written.")
        return
    for rel in modified:
        _replace_source(index[rel], replacements[rel])
    nb.cells = [cell for cell in nb.cells if _file_path(cell) not in deleted]

    insert_at = max((i + 1 for i, cell in enumerate(nb.cells) if _file_path(cell)), default=0)
    if not insert_at:
        insert_at = next((i + 1 for i, cell in enumerate(nb.cells)
                          if cell.metadata.get("repo2nb_section") == "files"), len(nb.cells))
    for offset, rel in enumerate(added):
        nb.cells.insert(insert_at + offset, replacements[rel])

    if added or modified or deleted or setup_changed:
        write_notebook(nb, nb_path)

    manifest["files"] = current
    manifest["notebook"] = str(nb_path.resolve())
    manifest["ignore_extra"] = sorted(exclusions)
    save_manifest(repo_path, manifest)
    print(f"[repo2nb] Synced {len(added) + len(modified) + len(deleted)} change(s).")
