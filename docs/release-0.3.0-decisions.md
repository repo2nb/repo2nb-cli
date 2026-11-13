# 0.3.0 release decisions

The published version is 0.2.1. Local Kaggle publishing adds a feature, so the
next minor release is 0.3.0; 2.1.0 would skip two major versions.

## Inventory and fixes

- Keep Kaggle execution and local publishing together in the Kaggle target and
  the bundled official `kaggle` CLI; retain Colab's current Git workflow.
  - Kaggle currently injects GitHub authentication and Git commands even though
    local editing and publishing no longer require Git inside Kaggle.
  - Colab imports a private remote parser from Kaggle despite owning the only
    remaining notebook Git workflow. Move that parser into Colab.
  - Converter prose names Kaggle for Colab output, and workspace generation is
    coupled to the presence of a local `.git` directory.
- Classify project imports and resolve dependencies in `deps.py`.
  - The AST fallback only recognizes root-level modules and the first directory
    component, so `src` layouts and nested source roots become pip packages.
  - Dependency exporters run in the caller's working directory instead of the
    repository whose lockfile selected them.
  - Declared PEP 621 dependencies are ignored without a lockfile.
  - Raw requirement joining in a pip cell misinterprets bounds and markers as
    shell syntax. Quote each requirement at the notebook boundary.
- Share file filtering/reading between conversion and sync in `traversal.py`.
  - Sync imports a private converter filter and independently reads the same
    files with different options, dropping `--include` selections.
  - Re-reading content separately from hashes can produce inconsistent state.
  - Symlink traversal can recurse forever or embed files outside the repository.
- Make generated setup cells identifiable and maintain them during sync.
  - Sync changes source files but leaves dependency installs stale.
  - Nested `%%writefile` paths have no directory creation step, so reconstructed
    projects fail when executed in a clean runtime.
  - Setup behavior must use the same content snapshot as file cells.
- Reconcile sync against notebook file-cell metadata and insert using the live
  cell list, preserving user cells and outputs.
  - A deleted tagged cell causes `KeyError` when its source file changes.
  - Insertion uses indices from before deleted cells were removed.
  - Relative manifest notebook paths depend on the caller's working directory.
  - Persist include/dependency options and the resolved notebook path, with
    defaults for older manifests.
- Keep filesystem writes and untrusted metadata validation at their boundaries.
  - Full conversion writes directly to the destination while sync already uses
    atomic replacement. Share an atomic notebook writer.
  - Appending to a `.gitignore` without its final newline joins two entries.
  - Reverse's path validation assumes metadata paths are strings.
- Clean comments and tests after behavior changes.
  - Remove comments that only describe the adjacent implementation, including
    the inaccurate claim that UTF-8 replacement reads Latin-1.
  - Replace tests tied to removed Kaggle Git cells with local-publishing and
    Colab preservation checks; keep actual safety and behavior regressions.

## Retained special cases

- Import-to-distribution aliases are necessary because Python module names and
  package index names differ; unknown names remain an explicitly unpinned
  inference rather than a promise of index availability.
- Poetry/uv export failures, malformed ignore patterns, non-UTF8 source files,
  and unsafe reverse paths need their existing fallbacks or clear warnings.
- Kaggle and Colab use different working directories and collapse metadata.
- Kaggle 2.2.5 imports `six` without declaring it; `python-dateutil` 4 no longer
  installs it transitively. Include `six` explicitly until the Kaggle minimum
  can be raised to a release fixing that dependency declaration.
- Manual CLI dispatch retains the existing positional repository invocation;
  directories named `sync` or `reverse` still need a `./` prefix.
- Atomic file replacement prevents partial writes; notebook and manifest remain
  separate files, so sync must tolerate a notebook newer than its manifest.

## Completed review and checks

- Shared text snapshots now live in `traversal.py`; neither `sync.py` nor the
  dependency resolver imports converter internals. Colab owns its Git remote
  parser. The package import graph was rechecked after the refactor.
- Generated dependency/directory cells use `repo2nb_setup` metadata, keeping
  file-cell metadata compatible. Sync reconciles actual notebook file cells,
  restores missing cells and preserves manual cells and outputs.
- Old untagged setup cells remain untouched. Regenerate notebooks from releases
  before 0.3.0 once to adopt the current setup and Kaggle execution workflow.
- Comment cleanup removed implementation narration and the inaccurate Latin-1
  note. Test cleanup removed duplicate assertions and an already-covered JSON
  shape check; the hash test now checks a known SHA-256 vector.
- Full suite: 91 tests passed. `ruff check .` and `git diff --check` passed.
  Regression coverage includes a clean nested/spaced-path reconstruction,
  requirements quoting, failed atomic writes, symlink traversal, malformed
  reverse metadata, sync from another working directory, preserved include and
  no-dependency options, legacy manifests, setup refresh and retained user cells.
- A second agent reviewed the final runtime changes for hidden links, needless
  links, surplus and special cases and found no remaining issues worth fixing
  for this release. A separate subprocess smoke checked generation, local sync,
  reverse extraction and preserved Colab authentication.
- Authenticated Kaggle publishing and hosted Kaggle/Colab execution were not
  exercised. Kaggle authentication stays local and requires the user's account.

## Package and workflow verification

- Bundle official `kaggle>=2.2.5`, with Python >=3.11 matching its supported
  interpreter floor. OAuth login, notebook push/pull, and `push --no-run` use
  native Kaggle commands; repo2nb adds no command wrappers.
- Refreshed the lockfile and installed the dependencies. Actual CLI smoke checks
  caught the missing `six` dependency above, and passed after its inclusion.
- Offline Kaggle top-level/push/pull help and version succeed with an isolated
  configuration directory. An invalid push option exits 2. These checks do not
  authenticate, upload, download, or execute a remote notebook.
- repo2nb help and version succeed. Target/golden tests pass (6 tests).
- Wheel and source distribution build successfully; wheel metadata declares
  version 0.3.0, Python >=3.11, `kaggle>=2.2.5`, and `six`.
- Golden output and both sample notebooks now show a small nested project
  and dependency installation without Kaggle Git setup. Examples include a
  runnable entry point in the workspace cell.
- Live OAuth, authenticated push/pull, and execution on Kaggle/Colab remain
  environment-level checks. Nothing was published or tagged.

Official references verified for this release:

- [Kaggle CLI installation/authentication](https://github.com/Kaggle/kaggle-cli/blob/main/docs/README.md)
- [Notebook commands](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels.md)
- [Notebook metadata](https://github.com/Kaggle/kaggle-cli/blob/main/docs/kernels_metadata.md)
- [Kaggle changelog and upstream dependency fix](https://github.com/Kaggle/kaggle-cli/blob/main/CHANGELOG.md)
