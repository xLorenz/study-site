# Study Site

A self-contained study companion that ingests course materials, generates wiki
documentation via AI, and provides an interactive chat with a professor persona
grounded in your subject's content. All from a single Python server.

## Features

- **AI chat** over your study material with multi-round tool calling (read files,
  create study aids, render animations, highlight concepts)
- **Document ingest** — upload PDFs, PPTX, DOCX; auto-converted to markdown via
  MarkItDown
- **Wiki generation** — LLM creates curated wiki pages with cross-references and
  [[wikilinks]]
- **Study objects** — HTML exams, cheat-sheets, mind maps, flashcards, formula
  decks (6+ templates)
- **Manim video** — renders animated explanations server-side with embedded HTML
  playback
- **Knowledge graph** — wikilink-based concept graph with search and highlight
- **Tag system** — objects get free-form tags with deterministic HSL colors
- **Skills registry** — loadable domain guidelines (`manim-video`,
  `study-object-templates`) that tailor model behavior

## Requirements

- Python 3.10+
- `pyyaml` (one pip dependency)
- `markitdown` — used via subprocess for document conversion
- Optional: `manim` + `ffmpeg` for server-side video rendering

## Quick start

```bash
pip install pyyaml
python server.py
```

Open http://localhost:8081. Default port is 8081; configurable in `config.yaml`.

## Configuration

| File | Purpose | Committed? |
|------|---------|-----------|
| `config.yaml` | Non-secret tunables (host, port, vault path, model endpoints) | Yes |
| `secrets.yaml` | API keys | No (gitignored) |
| `.env` | Environment variable overrides | No (gitignored) |

Use `secrets.example.yaml` and `.env.example` as templates.

## Vault layout

```
vaults/
├── index.md                    # Vault-wide index
├── log.md                      # Vault-wide changelog
├── chats/                      # Saved chat histories per subject
├── objects/                    # Generated HTML study objects
├── originals/                  # Uploaded source files (PDF, PPTX, etc.)
└── subjects/<subject>/
    ├── index.md                # Auto-generated file index
    ├── raw/                    # Markdown conversions from uploads
    ├── wiki/                   # LLM-generated wiki pages
    ├── references/             # Design notes and internal docs
    └── .ingested.json          # Tracks ingestion state
```

## Project layout

```
.
├── chat/                # Chat package (handler, ingest, llm, prompt, state, tools, types, skills/)
├── routes/              # HTTP route handlers (admin, chat, files, ingest, system)
├── static/              # Front-end assets (chat-ui.{css,js}, study-ui.{css,js})
├── scripts/             # One-off maintenance scripts
├── vaults/              # User data (gitignored)
├── .cache/              # Cache artifacts (gitignored)
├── index.html           # SPA entry point
├── server.py            # HTTP server
├── config.yaml          # Non-secret configuration
├── subject_themes.json  # Per-subject color theming
```

## API overview

All endpoints under `/api/`.

### File system
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/subjects` | List subjects |
| GET | `/api/files` | List directory entries |
| GET | `/api/file-content` | Read markdown file |
| GET | `/api/objects` | List generated objects (with tags) |
| GET | `/api/object-content` | Serve HTML object |
| GET | `/api/original` | Serve uploaded file |
| POST | `/api/upload` | Upload a file |
| POST | `/api/delete-file` | Cascade-delete raw file |
| POST | `/api/regenerate-index` | Rebuild subject index |

### Chat
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/model` | Available AI models |
| POST | `/api/chat-start` | Start background chat task |
| POST | `/api/chat-stream` | SSE stream from task |
| POST | `/api/chat-save` | Save chat history |
| POST | `/api/chat-delete` | Delete saved chat |
| GET | `/api/chat-load` | Load saved chat |

### System
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/graph` | Wikilink graph (nodes + edges) |
| GET | `/api/lint` | Orphaned files, missing frontmatter |
| GET | `/api/themes` | Subject theme colors |
| GET | `/api/search` | Full-text search |
| POST | `/api/create-subject` | Create new subject |
| POST | `/api/delete-subject` | Delete subject and data |

## Chat tools

The AI model can invoke these tools during a conversation:

| Tool | Purpose |
|------|---------|
| `read_vault_file` | Read wiki, raw, or reference files |
| `write_study_object` | Create HTML study aids (exams, mind maps, flashcards, etc.) |
| `write_study_video` | Render animated manim explanations |
| `write_wiki_page` | Create or update wiki documentation |
| `write_design_notes` | Write internal design docs to references/ |
| `mark_file_ingested` | Mark raw file as fully processed |
| `highlight_node` | Highlight concepts in the knowledge graph |
| `read_skill` | Load skill guidelines for specialized tasks |

## Skills

Skills are markdown documents in `chat/skills/` that provide domain-specific
guidelines to the LLM. Built-in:

- **`study-professor`** — base persona (always loaded)
- **`study-object-templates`** — HTML template reference for 6+ study object
  formats
- **`manim-video`** — manim scripting conventions, patterns, and best practices

## Tags

Objects created via `write_study_object` and `write_study_video` accept an
optional `tag` parameter (max 7 lowercase letters). Tags are free-form and
receive a deterministic HSL color derived from the tag string. They display as
uppercase badges in the object tree UI.
