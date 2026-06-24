# Study Site

Local study companion: a single-page UI plus a Python server that ingests study
material into a vault, runs an AI chat over it, and renders visual explanations
(manim/HyperFrames). All assets are served from `static/`; the vault lives
inside the repo at `vaults/`.

## Requirements

- Python 3.10+
- One Python dependency: `pyyaml`
- A working `markitdown` installation (used via subprocess by `server.py`)
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
- **`.env`** — environment-variable overrides (gitignored). Use `.env.example`
  as a template.

Path values may be relative to `STUDY_DIR` (e.g. `vault_path: vaults`).

## Vault layout

The default vault is `vaults/`. Per subject:

```
vaults/
├── index.md
├── log.md
├── chats/                    # Saved chat timelines per subject
├── objects/                  # Generated .html previews
├── originals/                # Uploaded PDFs, PPTX, etc.
└── subjects/<subject-name>/
    ├── index.md              # Auto-generated file index
    ├── raw/                  # MarkItDown-converted markdown (upload target)
    ├── wiki/                 # LLM-generated wiki pages with [[wikilinks]]
    └── .ingested.json        # Tracks which raw files have been ingested
```

## Project layout

```
.
├── chat/                # Chat package (handler, ingest, llm, prompt, state, tools, types)
├── scripts/             # One-off maintenance scripts (add-frontmatter.py)
├── static/              # Front-end assets (chat-ui.{css,js}, study-ui.{css,js})
├── routes/              # HTTP route handlers (admin, chat, files, ingest, system, _base)
├── vaults/              # Vault directory (user data, gitignored)
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

## API endpoints

All endpoints under `/api/`. Route modules in `routes/`:

| Method | Path                  | Module  | Purpose                          |
|--------|-----------------------|---------|----------------------------------|
| GET    | /api/health           | ingest  | Server health                    |
| GET    | /api/status           | ingest  | Ingest progress / queue state    |
| GET    | /api/subjects         | files   | List subjects                    |
| GET    | /api/files            | files   | List directory entries           |
| GET    | /api/file-content     | files   | Read a markdown file             |
| GET    | /api/objects          | files   | List generated objects           |
| GET    | /api/object-content   | files   | Serve an HTML object             |
| GET    | /api/original         | files   | Serve an uploaded original file  |
| GET    | /api/graph            | system  | Wikilink graph (nodes + edges)   |
| GET    | /api/lint             | system  | Lint: orphans, frontmatter, etc. |
| GET    | /api/themes           | system  | Subject theme colors             |
| GET    | /api/search           | system  | Full-text search across subjects |
| GET    | /api/pending-state    | files   | Pending deletion state           |
| GET    | /api/model            | chat    | Available AI models              |
| POST   | /api/upload           | files   | Upload a file (PDF, PPTX, etc.)  |
| POST   | /api/regenerate-index | files   | Rebuild subject index.md         |
| POST   | /api/update-wiki      | ingest  | Cascade-delete + LLM ingest      |
| POST   | /api/delete-file      | files   | Cascade-delete a raw file        |
| POST   | /api/mark-file        | files   | Mark/unmark file for deletion    |
| POST   | /api/create-subject   | admin   | Create a new subject             |
| POST   | /api/delete-subject   | admin   | Delete a subject and all data    |
| POST   | /api/chat-start       | chat    | Start a new chat session         |
| POST   | /api/chat-stream      | chat    | Stream a chat response           |
| POST   | /api/chat-save        | chat    | Save current chat                |
| POST   | /api/chat-delete      | chat    | Delete saved chat                |
| GET    | /api/chat-load        | chat    | Load saved chat                  |
| GET    | /skill/:name          | system  | Serve skill prompt documents     |

Bash scripts from `study-scripts/` have been replaced by the admin API
(`create-subject`, `delete-subject`).

## Security note

Personal identifiers (`xlorenz`) and API keys were previously committed to the
repo. They have been scrubbed from all 60 commits via `git filter-branch`.
The NVIDIA API key from an old `.env` file was only present in a dangling
commit that was never pushed. **There are no known secrets in the git history
reachable from master.**

## Troubleshooting

- The vault directory (`vaults/`) and its subdirectories (`subjects/`,
  `objects/`, `originals/`, `chats/`) are created automatically by the server
  on first use. If you see 404 errors on a new subject, create it via
  `POST /api/create-subject` or the web UI.
- The server will fail to start if `config.yaml` cannot be read. Check the
  terminal output for YAML parse errors.
