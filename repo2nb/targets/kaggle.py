import nbformat.v4 as nbf

NAME = "kaggle"
WORKDIR_PREFIX = "/kaggle/working/"
GITIGNORE_ENTRIES = [".virtual_documents/"]


def collapse_metadata() -> dict:
    # shortcut: viewers may ignore source_hidden; keep the visible setup label.
    return {"jupyter": {"source_hidden": True}}


def auth_cells(repo_path, omit_instructions: bool = False) -> list:
    return []


def workspace_cells(omit_instructions: bool = False) -> list:
    text = "# 🚀 Phase 3: Your Workspace"
    if not omit_instructions:
        text += (
            "\n\nRun your project from here. Make source changes locally, update this notebook "
            "with `repo2nb sync`, then upload the next version with `kaggle kernels push`. "
            "Commit and push your repository with Git on your local machine."
        )
    return [nbf.new_markdown_cell(text), nbf.new_code_cell()]
