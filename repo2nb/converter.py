import pathlib

from . import __version__
from .deps import resolve_dependencies
from .notebook import (
    SETUP_HEADER,
    assemble_notebook,
    content_hash,
    make_directory_cell,
    make_markdown_cell,
    make_pip_cell,
    make_writefile_cell,
    write_notebook,
)
from .state import STATE_DIR, ensure_gitignore_entries, save_manifest
from .targets import get_target
from .traversal import is_binary, read_text_files, traverse
from .warnings import get_warning_cells


def convert(repo_path: pathlib.Path, output_path: pathlib.Path, omit_instructions: bool = False,
            ignore_extra: set = None, include: set = None, target_name: str = "kaggle",
            deps: bool = True):
    target = get_target(target_name)
    ignore_extra = ignore_extra or set()

    # State files must exist before traversal so hashes are stable across runs.
    ensure_gitignore_entries(repo_path, [*target.GITIGNORE_ENTRIES, f"{STATE_DIR}/"])

    tree, has_git = traverse(repo_path, extra_ignore=ignore_extra)
    contents = read_text_files(repo_path, tree, include)

    cells = []

    if not omit_instructions:
        cells.extend(get_warning_cells())

    setup_cells = []
    push_cells = []
    if has_git:
        setup_cells.extend(target.auth_cells(repo_path, omit_instructions))
    if has_git or target_name == "kaggle":
        push_cells = target.workspace_cells(omit_instructions)

    file_hashes = {}
    if deps:
        requirements, source = resolve_dependencies(repo_path, tree)
        if requirements:
            setup_cells.append(make_pip_cell(requirements))
            print(f"[repo2nb] Dependencies resolved from {source}: {len(requirements)} package(s)")
        elif source.startswith(("poetry", "uv", "requirements")):
            print(f"[repo2nb] WARNING: dependency source '{source}' produced no installable requirements.")

    directory_cell = make_directory_cell(contents, target.WORKDIR_PREFIX)
    if directory_cell is not None:
        setup_cells.append(directory_cell)

    if setup_cells:
        header = make_markdown_cell(SETUP_HEADER)
        header.metadata["repo2nb_setup"] = "header"
        cells.append(header)
        collapse = target.collapse_metadata()
        for cell in setup_cells:
            if cell.cell_type == "code":
                cell.metadata.update(collapse)
            cells.append(cell)

    if omit_instructions:
        phase2_text = "# 📂 Phase 2: Repository Construction"
    else:
        phase2_text = (
            "# 📂 Phase 2: Repository Construction\n"
            "---\n"
            f"The following cells will recreate your project files within {target.NAME.title()}'s environment."
        )
    construction_header = make_markdown_cell(phase2_text)
    construction_header.metadata["repo2nb_section"] = "files"
    cells.append(construction_header)

    repo_name = repo_path.name

    for dir_path, files in tree:
        if not files:
            continue

        if dir_path == repo_path:
            depth = 0
            folder_name = repo_name
        else:
            try:
                rel_dir = dir_path.relative_to(repo_path)
                depth = len(rel_dir.parts)
            except ValueError:
                depth = 0
            folder_name = dir_path.name

        if depth == 0:
            header_level = "#"
        elif depth == 1:
            header_level = "##"
        elif depth == 2:
            header_level = "###"
        else:
            header_level = "####"

        cells.append(make_markdown_cell(f"{header_level} 📁 {folder_name}"))

        for file_path in files:
            try:
                rel_file_path = file_path.relative_to(repo_path)
            except ValueError:
                continue

            rel_path = rel_file_path.as_posix()

            if is_binary(file_path, include):
                cells.append(make_markdown_cell(f"**Skipped data/binary file**: `{rel_path}`\n*(Upload manually if needed)*"))
                continue

            cells.append(make_markdown_cell(f"**📄 {rel_file_path.name}**"))
            if rel_path in contents:
                content = contents[rel_path]
                cells.append(make_writefile_cell(rel_path, content, prefix=target.WORKDIR_PREFIX))
                file_hashes[rel_path] = content_hash(content)
            else:
                cells.append(make_markdown_cell(f"**Skipped non-UTF8 file**: `{rel_path}`\n*(Upload manually if needed)*"))

    cells.extend(push_cells)

    nb = assemble_notebook(cells, target=target_name)

    write_notebook(nb, output_path)

    manifest = {
        "version": __version__,
        "generated_at": nb.metadata["repo2nb"]["generated_at"],
        "target": target_name,
        "notebook": str(output_path.resolve()),
        "ignore_extra": sorted(ignore_extra),
        "include": sorted(include or []),
        "deps": deps,
        "files": file_hashes,
    }
    save_manifest(repo_path, manifest)
