# Study Site

Local study companion: a single-page UI plus a Python server that ingests study
material into a vault, runs an AI chat over it, and renders visual explanations
(manim/HyperFrames). All assets are served from `static/`; the vault lives
outside the repo.

## Requirements

- Python 3.10+
- One Python dependency: `pyyaml`
- A working `markitdown` installation in the Python used to render manim (used
  via subprocess by `server.py`)
- Optional: `manim` + `ffmpeg` if you want server-side video rendering through
  the chat's `write_study_video` tool

## Install

```bash
pip install pyyaml
```

## Run

```bash
python server.py
```

Default: listens on `0.0.0.0:8081`. Open <http://localhost:8081>.

## Configuration

Configuration is split into two YAML files plus `.env`:

- **`config.yaml`** — non-secret tunables (committed).
  - `host`, `port`, `nim_base_url`, `vault_path`
- **`secrets.yaml`** — API keys (gitignored). Use `secrets.example.yaml` as a
  template.
- **`.env`** — environment-variable fallback. Use `.env.example` as a template.

Path values may be relative to `STUDY_DIR` (e.g. `vault_path: vaults`).

## Vault layout

The default vault is `vaults/`. Per subject:

```
vaults/
└── subjects/<subject-name>/
    ├── concepts/<slug>.md
    ├── definitions/<slug>.md
    ├── formulas/<slug>.md
    ├── exercises/<slug>.md
    ├── images/
    └── videos/
```

Generated content (chat timelines, saved pages) also lives under the vault.

## Project layout

```
.
├── chat/                # Chat package (handler, ingest, llm, prompt, state, tools, types)
├── chats/               # Placeholder for extra chat storage
├── scripts/             # One-off maintenance scripts (add-frontmatter.py)
├── static/              # Front-end assets (chat-ui.{css,js}, study-ui.{css,js})
├── routes/              # Server route handlers (chat, ingest, files, system)
├── .cache/              # Generated/cache artifacts (gitignored)
├── .env.example         # Template for .env
├── config.yaml          # Non-secret config
├── secrets.example.yaml # Template for secrets.yaml (gitignored)
├── index.html           # SPA shell
├── server.py            # HTTP server entry point
└── subject_themes.json  # Per-subject color theming
```

## Generated / cache locations

These are gitignored and safe to delete:

- `.cache/manim/` — manim renders (videos, partial movie files, slide JSON)
- `.cache/ingest.log` — server ingest log

## Security note

API keys for NVIDIA NIM and OpenCode Zen were previously committed to
`config.yaml` and `.env`. They have been split out into `secrets.yaml` and the
committed files have been removed from git history. **You must still rotate
the leaked keys** at the provider — the secrets are no longer in the repo,
but the original key values remain valid until revoked.

## Follow-ups

A few items were flagged during the polish pass but intentionally deferred
because they are code changes, not structural cleanups:

- Split `server.py` into a small `routes/` package.
- Drop the `sys.path.insert` shim in `chat/__init__.py`.
- Add a route/exposure for the HyperFrames/skill documents that
  `chat/prompt.py` references.