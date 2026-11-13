# TUTORIAL.md — repo2nb in depth

Everything the [README](README.md) didn't bore you with: every flag, every subcommand, every convention.

## Table of contents

- [Converting a repo (`convert`, the default command)](#converting-a-repo)
- [Dependency auto-detection](#dependency-auto-detection)
- [`.repo2nbignore`](#repo2nbignore)
- [Reverse mode (`reverse`) — nb2repo](#reverse-mode-reverse--nb2repo)
- [Incremental sync (`sync`)](#incremental-sync-sync)
- [Kaggle local workflow](#kaggle-local-workflow)
- [Colab support](#colab-support)
- [Setup cells & collapsing](#setup-cells--collapsing)
- [Conventions & gotchas](#conventions--gotchas)

---

## Converting a repo

```bash
python -m repo2nb ./my_project --output my_project_kaggle.ipynb
```

Then upload the resulting `.ipynb` to Kaggle (File → Import Notebook) or Colab.

### All options

| Option | What it does | Default |
|---|---|---|
| `--output`, `-o` | Output `.ipynb` path | `<folder_name>.ipynb` |
| `--target {kaggle,colab}` | Target platform | `kaggle` |
| `--omit-instructions` | Omits warning cells and instructional cheat sheets | off |
| `--ignore-extra ".ext ..."` | Extra file extensions to ignore completely (comma or space separated) | — |
| `--include ".ext ..."` | Force include extensions usually skipped as binary/data | — |
| `--no-deps` | Skip dependency auto-detection and the `%pip install` cell | off |
| `--version` | Print version | — |

### What the generated notebook looks like

1. **Usage instruction** (unless `--omit-instructions`)
2. **🔧 repo2nb setup** — `%pip install` if dependencies were detected; Colab also includes Git auth when your repo has a `.git` directory
3. **📂 Phase 2: Repository Construction** — your file tree as `%%writefile` cells
4. **🚀 Phase 3: Your Workspace** — a cell for your run command on Kaggle; Git commands and a cheat sheet on Colab for Git repositories

Every file cell carries hidden metadata (`repo2nb.path`, `hash`) — that's what powers [`reverse`](#reverse-mode-reverse----nb2repo) and [`sync`](#incremental-sync-sync).

## Dependency auto-detection

By default, repo2nb figures out your project's dependencies **locally, at generation time**, and writes one plain `%pip install` cell into the notebook. Resolution order (first available wins):

1. `poetry.lock` (+ `[tool.poetry]` in `pyproject.toml`) → runs `poetry export` locally
2. `uv.lock` → runs `uv export` locally
3. `requirements.txt` → read directly (local/editable installs like `-e .` are stripped)
4. `pyproject.toml` → `[project].dependencies` (PEP 621), including an explicitly empty list
5. No declared dependency source → AST scan of your included `.py` files: third-party imports are collected (stdlib, relative imports, and your own project modules/packages excluded) and installed **unpinned**

Poetry and uv never need to exist on Kaggle/Colab — they only run on your machine, and only if the matching lockfile is present. If poetry/uv aren't installed locally, repo2nb falls through the chain automatically and tells you what it did.

Pass `--no-deps` to manage installs yourself.

Common import-name → pip-name mismatches (`cv2` → `opencv-python`, `sklearn` → `scikit-learn`, `yaml` → `pyyaml`, …) are handled in the AST path. Static import scanning cannot establish that an arbitrary import name exists on PyPI, resolve shared namespace providers, or follow dynamic imports/custom runtime search paths; use declared dependencies for authoritative package names and versions.

## `.repo2nbignore`

Create an optional `.repo2nbignore` file at your repo root to exclude files from the generated notebook using gitignore syntax (globs and `!` negation, powered by [`pathspec`](https://github.com/cpburnz/python-pathspec)):

```
# .repo2nbignore
*.yaml
!config.yaml
data/experiment_42.csv
```

**Precedence** (later layers override earlier ones):

1. Built-in smart-filter defaults (`.venv`, lockfiles, heavy binaries, …)
2. `--ignore-extra` CLI flag
3. `.repo2nbignore`, in file order — so `!config.yaml` above can un-ignore a file caught by any earlier rule

Note the difference to the flags: `--ignore-extra` / `--include` work at the *extension* level across the whole repo, while `.repo2nbignore` patterns can target individual paths. Malformed lines are skipped with a terminal warning instead of failing the run.

> repo2nb deliberately does **not** read your real `.gitignore` — files get gitignored for reasons unrelated to what a training run needs at runtime (a local `.env`, machine-specific configs).

## Reverse mode (`reverse`) — nb2repo

Made edits on Kaggle/Colab and want them back on your machine? Every file cell repo2nb generates is tagged with its repo path in cell metadata, so you can reconstruct the tree from any generated notebook:

```bash
python -m repo2nb reverse my_project_kaggle.ipynb --output restored_project
```

Behavior:

- Refuses to write into a non-empty directory unless you pass `--force`
- Paths in metadata are validated against directory traversal before anything is written (a hand-edited/corrupted notebook can't write outside `--output`)
- Cells you deleted on the platform are simply omitted from the reconstruction
- Works regardless of how deeply nested your repo is (depth is encoded in each cell's metadata path, not in markdown structure)
- Default output directory: `<notebook name>` without extension

This is a plain "extract to folder" step — review the result with `git diff` yourself afterwards. Notebooks heavily hand-edited outside repo2nb's own cells may not reconstruct perfectly.

## Incremental sync (`sync`)

Re-running full generation after every small change is wasteful. `sync` updates an existing notebook in place:

```bash
python -m repo2nb sync ./my_project            # uses the notebook recorded at last generation
python -m repo2nb sync ./my_project --dry-run  # preview changes without touching anything
python -m repo2nb sync ./my_project --notebook other.ipynb
```

How changes are applied:

- **Added** files get a new tagged cell appended after the last file cell (no import-order-smart placement — reorder manually if you care)
- **Modified** files are updated in place, keeping their position
- **Deleted** files have their cells removed entirely (a warning nobody reads is worse than removal)
- Cells you added manually are left untouched
- Dependency and directory setup generated by 0.3.0+ is refreshed; generation-time `--include`, `--ignore-extra`, and `--no-deps` settings are retained

> ⚠️ **Sync is strictly one-directional: local repo → notebook.** It is not a merge tool. If you made edits on Kaggle that you want to keep, run `reverse` first to bring them back into your local repo, then `sync`.

**Upgrading notebooks from before 0.3.0:** copy any manually added run cells somewhere safe, then regenerate the notebook and restore those cells. Older setup cells have no management tags, so sync preserves them rather than guessing which cells it can replace. Regeneration enables managed dependency refresh on both platforms and removes the old Git/token setup from Kaggle notebooks.

State lives in `.repo2nb/manifest.json` (auto-created at generation, auto-added to your `.gitignore`). Don't edit it; delete it if it gets corrupted, then re-run a full generation. The manifest is written atomically only after the notebook write succeeds, so a crash never leaves it half-updated.

## Kaggle local workflow

repo2nb includes the official `kaggle` package, which supplies the `kaggle` terminal command. Requires Python 3.11+. Kaggle authentication stays on your machine; no GitHub personal access token is needed for this workflow. The [official CLI guide](https://github.com/Kaggle/kaggle-cli/blob/main/docs/README.md#authentication) documents OAuth and alternative Kaggle API credentials.

### Create and push

```bash
# Authenticate to your Kaggle account in your browser.
kaggle auth login

# Keep notebook artifacts outside the source repository.
mkdir kaggle-notebook
python -m repo2nb ./my_project -o kaggle-notebook/project.ipynb
kaggle kernels init -p kaggle-notebook
```

Edit `kaggle-notebook/kernel-metadata.json` before pushing. For example, replace its contents with the following and substitute your actual Kaggle username:

```json
{
  "id": "YOUR_USERNAME/my-project",
  "title": "My Project",
  "code_file": "project.ipynb",
  "language": "python",
  "kernel_type": "notebook",
  "is_private": true,
  "enable_gpu": false,
  "enable_internet": true,
  "dataset_sources": [],
  "competition_sources": [],
  "kernel_sources": [],
  "model_sources": []
}
```

`code_file` is relative to the metadata directory. Keep `is_private` true unless you intend to publish the embedded source. Internet access allows the generated pip cell to install dependencies; enable GPU or add data sources as your run needs. The title and slug should agree (`My Project` → `my-project`). See [Kaggle's metadata reference](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md).

Open `project.ipynb` locally and put your entry point, such as `!python train.py`, in the final workspace cell. repo2nb reconstructs your source files; it does not guess which script to execute.

```bash
# Upload and run a new notebook, or a new version of the same notebook.
kaggle kernels push -p kaggle-notebook

# Upload without executing (Quick Save).
kaggle kernels push -p kaggle-notebook --no-run
```

### Edit locally and push again

```bash
# Edit source in ./my_project using your usual editor.
python -m repo2nb sync ./my_project --dry-run
python -m repo2nb sync ./my_project
kaggle kernels push -p kaggle-notebook

# Commit and push from your local repository using your normal Git workflow.
git -C my_project add .
git -C my_project commit -m "Update training code"
git -C my_project push
```

Keep the metadata ID unchanged to update the same Kaggle notebook. `sync` preserves your manually added run cells. For older notebooks, follow the upgrade note in the [sync section](#incremental-sync-sync).

### Pull a notebook

Download into a separate directory so existing local notebook edits stay intact:

```bash
kaggle kernels pull YOUR_USERNAME/my-project -p kaggle-download -m
```

`-m` also downloads `kernel-metadata.json`, so you can push that notebook again. Downloading a notebook does not merge source changes into your repository. If you edited tagged file cells on Kaggle, extract into a separate directory and review the files before merging them locally:

```bash
python -m repo2nb reverse kaggle-download/my-project.ipynb -o restored
```

Kaggle may choose the downloaded notebook filename from its slug; use the actual filename shown by the CLI. `reverse` extracts the source stored in file cells, not files changed only during a running session. See the [official notebook command reference](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md).

## Colab support

Pass `--target colab` to generate a notebook for Google Colab instead of Kaggle:

```bash
python -m repo2nb ./my_project --target colab -o my_project_colab.ipynb
```

For Git repositories, the auth cell uses Colab's native secrets API (`google.colab.userdata.get`). To set up your GitHub token in Colab:

1. Click the **key icon (Secrets)** in the left sidebar
2. Click **+ Add new secret**
3. Name it exactly: `GITHUB_TOKEN`
4. Paste your GitHub fine-grained personal access token as the value
5. Toggle **Notebook access** on for this secret

Colab's auto-generated `sample_data/` directory is automatically added to your `.gitignore` (the same way `.virtual_documents/` is for Kaggle), so it never lands in a push from a Colab session.

Drive mounting is intentionally not included — it's not needed for the core convert/run/push loop.

## Setup cells & collapsing

repo2nb-injected setup cells (pip install, plus Git auth on Colab) sit under a clearly labeled `## 🔧 repo2nb setup (safe to collapse)` header and carry best-effort collapse metadata per platform. **Collapse behavior is a viewer feature — no `.ipynb` metadata can guarantee hiding everywhere.** Hidden cells always still run on "Run All".

| Platform | Collapse metadata respected? |
|---|---|
| JupyterLab / VS Code | yes (`jupyter.source_hidden`) |
| Kaggle editor | unverified — label is the fallback |
| Colab | form-style rendering via `cellView: form` |
| GitHub renderer / nbviewer | no — the visible label is the fallback |

Colab fetches GitHub credentials at runtime from its secrets manager; Kaggle notebooks contain no GitHub authentication setup. Collapse metadata is purely cosmetic. Included source files and notebook outputs can still contain secrets. See [SECURITY.md](SECURITY.md).

## Conventions & gotchas

**Run All only once:** when you first start your platform session, use **"Run All"** to bootstrap the directory structure and recreate the files. After the initial setup, run cells individually as needed — re-running everything may overwrite manual code changes made that session!

**Colab branch management:** the notebook's Git commands default to `main`. Swap `"main"` for your target branch name in the `git pull` / `git push` cells if you work on a different branch.

**CLI gotcha:** a local folder literally named `sync` or `reverse` will be parsed as the subcommand in `python -m repo2nb sync`. Use a path prefix (`python -m repo2nb ./sync`) to disambiguate.

**What lands in your `.gitignore`:** repo2nb auto-adds its state dir (`.repo2nb/`), plus the platform's system dirs (`.virtual_documents/` for Kaggle targets, `sample_data/` for Colab). Every change is logged to the terminal; nothing is ever appended twice.
