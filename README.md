# repo2nb CLI

![repo2nb](Logo.png)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/David-Magdy/repo2nb?color=brightgreen)](https://github.com/David-Magdy/repo2nb/releases)
[![Made with Python](https://img.shields.io/badge/Made%20with-Python-ffd43b?logo=python&logoColor=306998&labelColor=646464)](https://www.python.org/)
[![PyPI downloads](https://img.shields.io/pypi/dm/repo2nb.svg?color=f1632d)](https://pypi.org/project/repo2nb/)


repo2nb CLI is an open-source Python CLI tool that converts a local code repository into a self-contained Jupyter notebook (`.ipynb`) designed natively to run on Kaggle's free GPU environment... and now Google Colab too.

## Video Tutorial
### [repo2nb Quick Start Guide](https://youtu.be/alpcOEds54c)

This video shows the earlier notebook-side Git workflow. Follow the local Kaggle workflow below for 0.3.0+.

## Motivation
*This is a tool I made for personal use first, then I wanted to publish it.*

My motivation was that I wanted to securely run a training repo on Kaggle, but it was scattered across directories and Python files. It is extremely frustrating copying all of this into a notebook and debugging why it's giving an error. 

I used to do workarounds like uploading the repo as a dataset and starting from there. It was exhausting and wasted a couple of minutes just to realize I missed an indented line! Attempting the same flow manually using git for authenticating myself, pushing, and pulling for simple microscopic changes, which was equally painful. `repo2nb` automates all of this seamlessly.

> [!NOTE]
> This project is intended for personal and academic projects. It is specifically designed for students and hobbyists like myself who want to quickly leverage free GPU compute without friction, rather than managing massive corporate repositories with hundreds of nested files!

## Installation

Requires **Python 3.11+**. Installation also includes the official [`kaggle` CLI](https://github.com/Kaggle/kaggle-cli).

```bash
pip install repo2nb
```

## Usage

```bash
# Convert your local project into a Kaggle-ready notebook
python -m repo2nb ./my_project --output my_project_kaggle.ipynb
```

Upload the resulting `.ipynb` to Kaggle, or use the bundled `kaggle` command to upload and run it from your machine. Authenticate locally with `kaggle auth login`, initialize notebook metadata with `kaggle kernels init`, then push with `kaggle kernels push`. See the [complete local workflow](TUTORIAL.md#kaggle-local-workflow) for the metadata and update steps.

Edit your repository locally, run `repo2nb sync ./my_project`, and push the updated notebook again. Keep Git commits and pushes local; Kaggle runs your code without GitHub credentials. Colab retains its in-notebook Git workflow.

## What you get

- **Instant Rebuild**: Automatically translates your local file tree into correctly ordered `%%writefile` blocks. 
- **Local Kaggle Workflow**: Includes the official Kaggle CLI for notebook uploads, downloads, and runs; no GitHub token or Git cells in Kaggle notebooks. Colab keeps its Git integration.
- **Smart Filtering**: Automatically skips cached data, virtual environments (`.venv`), lock files, heavy binaries (`.pt`, `.pkl`, `.jpg`), and dataset files (`.csv`, `.parquet`) so your final notebook remains incredibly lightweight.
- **Dependency Auto-Detection**: Resolves dependencies from poetry, uv, requirements.txt, pyproject.toml, or your external imports, excluding project modules — and emits one plain `pip install` cell.
- **Reverse Mode**: Reconstruct your local repo from a generated notebook (`repo2nb reverse`), closing the loop on Kaggle-side edits.
- **Incremental Sync**: Update an existing notebook in place after local changes (`repo2nb sync`) instead of regenerating from scratch.
- **Multi-Target**: Generate for Kaggle (default) or Google Colab (`--target colab`).
- **Visual Segregation**: Creates unmissable structural phases isolating where the automatic repo build ends and where your actual coding workspace begins.
- **Colab Git Cheat Sheet**: Gives Colab users interactive Git commands in the notebook.

## Learn more

| Doc | Contents |
|---|---|
| [TUTORIAL.md](TUTORIAL.md) | Every command and flag, dependency detection, `.repo2nbignore`, reverse & sync workflows, Colab setup, conventions |
| [SECURITY.md](SECURITY.md) | How secrets are handled and what the tool writes to your machine |
| [SUPPORT.md](SUPPORT.md) | Getting help and reporting bugs |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Development setup, project layout, PR guidelines |

## Reporting Issues

Found a bug or have a feature request? Head over to [SUPPORT.md](SUPPORT.md) for how to report it well.
