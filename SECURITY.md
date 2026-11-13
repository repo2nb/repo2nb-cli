# Security Policy

repo2nb does not embed authentication credentials itself. Review the source files and outputs you include before sharing a notebook.

## How repo2nb handles secrets

- Kaggle notebooks contain no GitHub authentication cells. The bundled Kaggle CLI authenticates locally using its own OAuth or Kaggle API credentials; keep those credentials outside your source repository.
- Colab notebooks fetch `GITHUB_TOKEN` at runtime with `google.colab.userdata.get`. The generated source contains the secret name, not its value. The running session stores the token in the Git remote URL; do not publish that runtime Git configuration or credential-bearing output.
- Setup cells carry best-effort *collapse* metadata, but this is cosmetic only — hiding is never part of the security model.

## What repo2nb writes to your machine

- `.gitignore` entries: its own state dir (`.repo2nb/`) and the target platform's system dirs (`.virtual_documents/`, `sample_data/`). Every write is logged to the terminal; nothing is duplicated.
- `.repo2nb/manifest.json`: file paths + SHA-256 content hashes used by `sync`. Contains no secrets and no file contents.
- Generated notebooks: your source files (that's the point) plus per-cell metadata (`path`, content hash, generator version). Nothing else.

If you keep secrets in files inside your repo, they will be embedded in the notebook like any other included file — exclude them with `.repo2nbignore`. Note that repo2nb deliberately does not read your real `.gitignore` for filtering.

## Path safety

`reverse` treats notebook cell metadata as untrusted input: every extracted path is validated to stay inside the output directory before anything is written, so a corrupted or hand-edited notebook cannot traverse outside `--output`.

## Supported versions

| Version | Supported |
|---|---|
| 0.3.x | yes |
| 0.2.x | yes |
| < 0.2 | no |

## Reporting a vulnerability

Please do **not** open a public issue for security reports. Use GitHub's private vulnerability reporting: **Security → Report a vulnerability** on the [repository](https://github.com/David-Magdy/repo2nb/security), or contact the maintainer directly if you prefer.

Include a description, reproduction steps, and the affected version (`python -m repo2nb --version`). You'll get an acknowledgment as soon as the report is triaged.
