"""Admin route handlers (create/delete subjects)."""

import json
import os
import shutil

from ._base import (
    _subject_exists, _normalize_name, _generate_muted_theme, _log_action,
    _get_last_theme_primary,
    get_ingest_state,
)


def _vault():
    return os.environ.get("VAULT_DIR", "")


def _study_dir():
    return os.environ.get("STUDY_DIR", "")

SCHEMA_TEMPLATE = """# {display_name} — SCHEMA

## Purpose
This wiki is a structured, interlinked knowledge base for studying **{display_name}**.
Wiki pages are generated from uploaded source materials. The user curates sources and asks questions.

## Directory Structure
```
subjects/{{subject}}/
├── SCHEMA.md          # This file — conventions and rules
├── raw/               # Source markdown (converted from PDF/docx uploads) — IMMUTABLE
└── wiki/              # All wiki pages (source summaries + concept pages)
    ├── index.md       # Table of contents, auto-generated
    └── log.md         # Append-only change log
```

## Page Types

There are two types of pages, both live in `wiki/`:

### 1. Source Summary Pages
One page per raw file. Summarizes the material and links to concept pages.

Naming: `src-{{base-name}}` where base-name is the raw filename without extension
(e.g., `raw/2026-cd-tp6.md` → `wiki/src-2026-cd-tp6.md`)
Do NOT use the same name as the raw file — keep wiki/ separate from raw/.

### 2. Concept Pages
One page per distinct concept/term mentioned across source files. Provides definition, explanation, and examples.

Naming: `lowercase-with-hyphens.md`

## Page Format

Every wiki page MUST start with YAML frontmatter (required by the graph view, lint, and node system):

```yaml
---
title: Page Title
created: YYYY-MM-DD
type: source_summary | concept | formula | definition | exercise
tags: [topic-tag]
source_url: raw/source-filename.md
---
```

**Fields:**
- `title` — Display title (capitalized)
- `created` — Date of creation, format YYYY-MM-DD
- `type` — One of the types above. Determines graph node color/halo.
  - `source_summary` → summarizes a raw file
  - `concept` → explains a specific topic/term
  - `formula` → formula-focused page
  - `definition` → definition-focused page
  - `exercise` → exercise/practice page
- `tags` — **Exactly one** topic tag. Identifies the page's topic for topic-based graph glow coloring. Example: `tags: [arrays]`. Choose the single most specific topic.
- `source_url` — **Exactly one** raw source file path, e.g., `raw/2026-cd-tp6.md`. Do NOT list multiple sources. Required — enables source-based graph glow coloring.

### Source Summary Page body:
- Brief summary of the source material
- Key takeaways
- [[wikilinks]] to concept pages for every important term mentioned
- Optional: "## Raw content" section with key excerpts

### Concept Page body:
- **Definition** — What is this concept?
- **Explanation** — Detailed explanation with context
- **For code subjects** (POO, etc.): include **code examples** in fenced blocks
- **For math subjects** (Algebra, etc.): include **formulas and worked examples**
- **[[wikilinks]]** throughout the text — first mention of each related concept
- **"## Related concepts"** section at the end with wikilinks

### Example concept page:
```markdown
---
title: CRC (Cyclic Redundancy Check)
created: 2026-06-04
type: concept
tags: [error-detection]
source_url: raw/2026-cd-tp6.md
---

## CRC (Cyclic Redundancy Check)

CRC is an error-detecting code used in digital networks and storage devices.
It works by treating data as a polynomial and dividing by a fixed generator polynomial.
The remainder (CRC) is appended to the frame.

The receiver performs the same division — a non-zero remainder indicates corruption.

## Related concepts
- [[Framing]]
- [[Error Detection and Correction]]
- [[Data Link Layer]]
- [[Hamming Distance]]
```

## Wikilink Rules
- Use the **exact filename** (lowercase with hyphens) when creating `[[wikilinks]]`
  - ✅ `[[cable-coaxial]]` — matches the file `cable-coaxial.md`
  - ❌ `[[Cable Coaxial]]` — will NOT match (spaces ≠ hyphens)
- The system does normalize spaces-to-hyphens as fallback, but **always use hyphens** for consistency
- **Every concept you wikilink to MUST have its own page** created during the same ingest run
  - If you write `[[crc]]`, also create `wiki/crc.md` with the full definition
  - This prevents ghost nodes (concepts without files) from appearing in the graph
- Exception: very minor acronyms (AM, FM, ASK, etc.) mentioned in passing — link them only if they get their own page. Otherwise skip the wikilink.
- First mention of a related concept → wrap it in `[[concept-name]]`
- Link where it's **naturally mentioned** — don't force links
- Every page must link to **at least 2-3 other pages** (no orphans)
- Concept pages should be linked FROM at least 1 other page
- Source summary pages link TO concept pages (not to each other or to raw files)

## Ingest Workflow (Triggered by "Update Wiki" Button)

When new raw files are detected:

### Step 1 — Read SCHEMA.md
Read this file. This is the sole authority for page format and conventions.

### Step 2 — Read wiki/index.md
Read `wiki/index.md` to discover which wiki pages already exist. This tells you the available concepts and prevents creating duplicates. Note the filenames (the `[[wikilink]]` slugs) so you can interlink correctly.

### Step 3 — Process each raw file
For each un-ingested `.md` file in `raw/`:
1. Read the raw content
2. Create a **source summary page** in `wiki/` using `src-{{base-name}}` naming (e.g., `wiki/src-2026-cd-tp6.md`)
3. Identify distinct concepts/terms in the material
4. Create **concept pages** in `wiki/` for each concept (e.g., `wiki/crc.md`, `wiki/framing.md`)
5. Add `[[wikilinks]]` between source summary and concept pages using exact lowercase-hyphen filenames
6. Immediately add the filename to the `ingested` array in `raw/.ingested.json`

### Step 4 — Finalize
1. Update `wiki/index.md` with all new pages and one-line descriptions
2. Append to `wiki/log.md`: date, source name, what changed

### Rules
- **Never modify** anything in `raw/`
- **Never overwrite** existing wiki pages — only create new ones
- Be thorough: extract every meaningful concept, not just the obvious ones

## Frontmatter Validation Rules
- `title` is required
- `created` is required (YYYY-MM-DD format)
- `type` is required, must be one of: source_summary, concept, formula, definition, exercise
- `tags` is required, exactly one topic tag per page (string array with one element)
- `source_url` is required, path to the raw source file

## Interlinking Convention
Pages grow more valuable as the wiki grows. When processing a new file:
- Scan existing wiki pages for concepts that overlap
- Add `[[wikilinks]]` BOTH ways: new page → existing, and existing → new (when relevant)
- This creates the compounding knowledge network

## Log Format
```
- YYYY-MM-DD HH:MM | INGEST | subject | source-name.md → N concept pages created
```

## Language
- All wiki pages must be written in the **same language** as the raw source material they reference
- If the raw source is in Spanish → write wiki pages in Spanish (terminology, phrasing, examples)
- If the raw source is in English → write wiki pages in English
- Match the source material's terminology and phrasing — do not translate key terms
- This rule applies to all page types: source summaries, concept pages, formula pages, etc.
"""


def handle_create_subject(handler):
    """POST /api/create-subject — create a new subject directory structure."""
    if get_ingest_state()["ingest_running"]:
        handler._send_json(503, {"error": "busy", "detail": "Operation in progress, try again shortly"})
        return

    try:
        cl = int(handler.headers.get("Content-Length", 0))
        body = json.loads(handler.rfile.read(cl).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        handler._send_json(400, {"error": "invalid_body", "detail": "Expected JSON body"})
        return

    raw_name = body.get("subject", "").strip()
    if not raw_name:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject field is required"})
        return

    normalized = _normalize_name(raw_name)
    if not normalized:
        handler._send_json(400, {"error": "invalid_name", "detail": "Subject name is empty after normalization"})
        return

    if _subject_exists(normalized):
        handler._send_json(409, {"error": "already_exists", "detail": f"Subject '{normalized}' already exists"})
        return

    display_name = normalized.replace("-", " ").title()

    vault = _vault()
    subj_dir = os.path.join(vault, "subjects", normalized)
    raw_dir = os.path.join(subj_dir, "raw")
    wiki_dir = os.path.join(subj_dir, "wiki")
    obj_dir = os.path.join(vault, "objects", normalized)
    orig_dir = os.path.join(vault, "originals", normalized)

    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(wiki_dir, exist_ok=True)
    os.makedirs(obj_dir, exist_ok=True)
    os.makedirs(orig_dir, exist_ok=True)

    with open(os.path.join(subj_dir, "SCHEMA.md"), "w", encoding="utf-8") as f:
        f.write(SCHEMA_TEMPLATE.format(display_name=display_name))

    with open(os.path.join(wiki_dir, "index.md"), "w", encoding="utf-8") as f:
        f.write(f"# {display_name} — Wiki Index\n\n## Pages\n<!-- auto-updated on ingestion -->\n")

    with open(os.path.join(wiki_dir, "log.md"), "w", encoding="utf-8") as f:
        f.write(f"# {display_name} — Operation Log\n\n<!-- append-only -->\n")

    with open(os.path.join(raw_dir, ".ingested.json"), "w", encoding="utf-8") as f:
        json.dump({"ingested": [], "last_ingested": None}, f)

    # Generate muted theme colors from last subject's primary
    theme = _generate_muted_theme(_get_last_theme_primary())

    # Write _theme.md inside the vault (model-readable via read_vault_file)
    theme_md_path = os.path.join(subj_dir, "references", "_theme.md")
    os.makedirs(os.path.dirname(theme_md_path), exist_ok=True)
    with open(theme_md_path, "w", encoding="utf-8") as f:
        f.write(f"# {display_name} — Theme\n\n"
                f"primary: {theme['primary']}\n"
                f"secondary: {theme['secondary']}\n"
                f"accent: {theme['accent']}\n"
                f"icon: {theme['icon']}\n\n"
                f"Use these colors for title gradients, section headings, "
                f"and alert borders in study objects.\n")

    vault_idx = os.path.join(_vault(), "index.md")
    with open(vault_idx, "a", encoding="utf-8") as f:
        f.write(f"\n- [{display_name}](subjects/{normalized}/wiki/index.md)\n")

    _log_action(normalized, "CREATE", "subject directories created")

    handler._send_json(200, {"status": "ok", "subject": normalized, "display_name": display_name})


def handle_delete_subject(handler):
    """POST /api/delete-subject — delete a subject and all its data."""
    if get_ingest_state()["ingest_running"]:
        handler._send_json(503, {"error": "busy", "detail": "Operation in progress, try again shortly"})
        return

    try:
        cl = int(handler.headers.get("Content-Length", 0))
        body = json.loads(handler.rfile.read(cl).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        handler._send_json(400, {"error": "invalid_body", "detail": "Expected JSON body"})
        return

    raw_name = body.get("subject", "").strip()
    if not raw_name:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject field is required"})
        return

    normalized = _normalize_name(raw_name)
    if not normalized:
        handler._send_json(400, {"error": "invalid_name", "detail": "Subject name is empty after normalization"})
        return

    if not _subject_exists(normalized):
        handler._send_json(404, {"error": "not_found", "detail": f"Subject '{normalized}' does not exist"})
        return

    vault = _vault()
    subj_dir = os.path.join(vault, "subjects", normalized)
    obj_dir = os.path.join(vault, "objects", normalized)
    orig_dir = os.path.join(vault, "originals", normalized)
    chat_file = os.path.join(vault, "chats", f"{normalized}.json")

    for d in [subj_dir, obj_dir, orig_dir]:
        if os.path.isdir(d):
            shutil.rmtree(d)
    if os.path.isfile(chat_file):
        os.remove(chat_file)

    # _theme.md is inside subj_dir, already removed by rmtree above

    vault_idx = os.path.join(_vault(), "index.md")
    if os.path.isfile(vault_idx):
        with open(vault_idx, encoding="utf-8") as f:
            lines = f.readlines()
        filtered = [l for l in lines if f"subjects/{normalized}/" not in l and f"({normalized})" not in l]
        with open(vault_idx, "w", encoding="utf-8") as f:
            f.writelines(filtered)

    _log_action(normalized, "DELETE", "subject deleted")

    handler._send_json(200, {"status": "ok", "subject": normalized})
