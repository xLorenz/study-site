#!/usr/bin/env python3
"""Study server — zero external dependencies. Port 8081."""

import email.parser
import email.policy
import http.server
import json
import os
import re
import socketserver
import subprocess
import threading
import time
import unicodedata
import urllib.parse
import yaml
from chat import handle_chat_start, handle_chat_stream, handle_chat_save, handle_chat_load, delete_chat_file
VAULT = os.path.expanduser("~/study-vault")
STUDY_DIR = os.path.expanduser("~/study")
PORT = 8081
HOST = "0.0.0.0"
NIM_API_KEY = ""
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Load config.yaml if present
_CFG_PATH = os.path.join(STUDY_DIR, "config.yaml")
if os.path.isfile(_CFG_PATH):
    try:
        with open(_CFG_PATH) as _f:
            _cfg = yaml.safe_load(_f) or {}
        VAULT = os.path.expanduser(_cfg.get("vault_path", VAULT))
        PORT = _cfg.get("port", PORT)
        HOST = _cfg.get("host", HOST)
        NIM_API_KEY = _cfg.get("nim_api_key", NIM_API_KEY)
        NIM_BASE_URL = _cfg.get("nim_base_url", NIM_BASE_URL)
    except Exception as e:
        print(f"Warning: config.yaml load failed: {e}")
# Ingest state (single-threaded server, so no threading lock needed)
_ingest_running = False
_ingest_result = None # last result: {pages_created, files_deleted, tokens_used, model, message, finished_at}
_ingest_total_pending = 0  # total files queued for ingest (set at ingest start)
_ingest_current_subject = None # subject currently being ingested (used for live progress)
_ingest_initial_wiki_count = 0 # wiki/ .md file count BEFORE ingest started (for progress tracking)
_ingest_initial_total = 0 # initial count of files to ingest (saved so frontend can compute fraction)
_ingest_last_created_name = None # name of most recently created wiki page (for live progress text)
_upload_in_progress = False # separate lock for upload (sync, fast — not LLM ingest)

with open(os.path.join(STUDY_DIR, "subject_themes.json")) as f:
    SUBJECT_THEMES = json.load(f)


def _vault_rel(abs_path):
    """Return vault-relative path for an absolute path under VAULT."""
    return os.path.relpath(abs_path, VAULT)


def _resolve_vault_path(rel_path):
    """Resolve a vault-relative path, checking for traversal."""
    joined = os.path.realpath(os.path.join(VAULT, rel_path))
    vault_real = os.path.realpath(VAULT)
    if not joined.startswith(vault_real + os.sep) and joined != vault_real:
        return None
    return joined


def slugify(text):
    """Slugify a filename: lowercase, normalize unicode, strip special chars, spaces to hyphens."""
    text = unicodedata.normalize('NFD', text.lower().strip())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def run_markitdown(input_path, output_path):
    """Convert a file to markdown using MarkItDown. Returns (success, stderr)."""
    # markitdown lives in the Hermes venv
    md_bin = os.path.expanduser("~/.hermes/hermes-agent/venv/bin/markitdown")
    try:
        result = subprocess.run(
            [md_bin, input_path, "-o", output_path],
            capture_output=True, text=True, timeout=60
        )
        return result.returncode == 0, result.stderr
    except subprocess.TimeoutExpired:
        return False, "MarkItDown timed out after 60s"
    except FileNotFoundError:
        return False, "markitdown command not found"
    except Exception as e:
        return False, str(e)


def parse_multipart(handler):
    """Parse multipart/form-data body using stdlib only. Returns dict."""
    content_type = handler.headers['Content-Type']
    content_length = int(handler.headers.get('Content-Length', 0))
    body = handler.rfile.read(content_length)
    msg = email.parser.BytesParser(policy=email.policy.default).parsebytes(
        f'Content-Type: {content_type}\r\n\r\n'.encode() + body
    )
    result = {}
    for part in msg.iter_parts():
        cd = part.get('Content-Disposition', '')
        name_match = re.search(r'name="([^"]+)"', cd)
        fname_match = re.search(r'filename="([^"]+)"', cd)
        if not name_match:
            continue
        field = name_match.group(1)
        if fname_match:
            result[field] = {
                'filename': fname_match.group(1),
                'data': part.get_payload(decode=True)
            }
        else:
            result[field] = part.get_payload(decode=True).decode('utf-8').strip()
    return result


def _subject_exists(subject):
    """Check if a subject directory exists under vault subjects/."""
    subj_dir = os.path.join(VAULT, "subjects", subject)
    return os.path.isdir(subj_dir)


def _find_original(subject, basename):
    """Find a file with same basename (no ext) in originals/{subject}/. Returns filename or None."""
    name_no_ext, _ = os.path.splitext(basename)
    orig_dir = os.path.join(VAULT, "originals", subject)
    if not os.path.isdir(orig_dir):
        return None
    for fname in os.listdir(orig_dir):
        if fname.startswith("."):
            continue
        f_no_ext, _ = os.path.splitext(fname)
        if f_no_ext == name_no_ext:
            return fname
    return None


def _has_original(subject, basename):
    """Check if a file with same basename (no ext) exists in originals/{subject}/."""
    return _find_original(subject, basename) is not None


def _read_node_meta(subject, node_id):
    """Read YAML frontmatter metadata for a node from its first matching file.
    Checks wiki/ first (new SCHEMA structure), then legacy dirs as fallback."""
    # Search order: wiki/ first, then legacy concept/definition/formula/exercise dirs
    search_dirs = [("wiki", "wiki_page")]
    for d, default_type in search_dirs:
        fpath = os.path.join(VAULT, "subjects", subject, d, f"{node_id}.md")
        if not os.path.isfile(fpath):
            continue
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        meta = {"type": default_type, "created": None, "tags": [], "source_url": None, "title": None}
        if not content.startswith("---\n"):
            return meta
        end = content.find("\n---\n", 4)
        if end == -1:
            return meta
        for line in content[4:end].splitlines():
            if line.startswith("type:"):
                meta["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("created:"):
                meta["created"] = line.split(":", 1)[1].strip()
            elif line.startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                if raw.startswith("[") and raw.endswith("]"):
                    meta["tags"] = [t.strip(" \"'") for t in raw[1:-1].split(",") if t.strip()]
                elif raw:
                    meta["tags"] = [raw]
            elif line.startswith("title:"):
                meta["title"] = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("source_url:"):
                meta["source_url"] = line.split(":", 1)[1].strip().strip("\"'")
        return meta
    # Fallback to legacy dirs
    legacy_dirs = [("concepts", "concept"), ("definitions", "definition"),
                   ("formulas", "formula"), ("exercises", "exercise")]
    for d, default_type in legacy_dirs:
        dpath = os.path.join(VAULT, "subjects", subject, d, f"{node_id}.md")
        if not os.path.isfile(dpath):
            continue
        with open(dpath, encoding="utf-8") as f:
            content = f.read()
        meta = {"type": default_type, "created": None, "tags": [], "source_url": None, "title": None}
        if not content.startswith("---\n"):
            return meta
        end = content.find("\n---\n", 4)
        if end == -1:
            return meta
        for line in content[4:end].splitlines():
            if line.startswith("type:"):
                meta["type"] = line.split(":", 1)[1].strip()
            elif line.startswith("created:"):
                meta["created"] = line.split(":", 1)[1].strip()
            elif line.startswith("tags:"):
                raw = line.split(":", 1)[1].strip()
                if raw.startswith("[") and raw.endswith("]"):
                    meta["tags"] = [t.strip(" \"'") for t in raw[1:-1].split(",") if t.strip()]
                elif raw:
                    meta["tags"] = [raw]
            elif line.startswith("title:"):
                meta["title"] = line.split(":", 1)[1].strip().strip("\"'")
            elif line.startswith("source_url:"):
                meta["source_url"] = line.split(":", 1)[1].strip().strip("\"'")
        return meta
    return {"type": "note", "created": None, "tags": [], "source_url": None, "title": None}


def _parse_relationships(subject):
    """Build graph nodes + edges from vault files.

    Auto-derives edges from [[wikilinks]] in wiki/ files (port of vaultParser.js
    two-pass architecture). Edges come exclusively from wikilinks in page bodies.
    """
    subj_dir = os.path.join(VAULT, "subjects", subject)

    # ── 1. Auto-derive nodes from vault wiki directories ──
    wiki_dirs = ["wiki", "concepts", "definitions", "formulas", "exercises"]
    name_counts = {}
    for d in wiki_dirs:
        dpath = os.path.join(subj_dir, d)
        if not os.path.isdir(dpath):
            continue
        for fname in sorted(os.listdir(dpath)):
            if not fname.endswith(".md") or fname.startswith("."):
                continue
            if d == "wiki" and fname in ("index.md", "log.md"):
                continue
            node_id = fname[:-3]
            name_counts[node_id] = name_counts.get(node_id, 0) + 1

    nodes = []
    node_map = {}  # id → node dict for quick lookup

    # ── 1b. Exclude raw-only files (exist in raw/ but NOT as wiki pages) ──
    raw_dir = os.path.join(subj_dir, "raw")
    wiki_dir = os.path.join(subj_dir, "wiki")
    # Collect wiki page names so we don't exclude pages that share a name with a raw file
    wiki_names = set()
    if os.path.isdir(wiki_dir):
        for f in os.listdir(wiki_dir):
            if f.endswith(".md") and f not in ("index.md", "log.md"):
                wiki_names.add(f[:-3])
    if os.path.isdir(raw_dir):
        raw_basenames = set()
        for f in os.listdir(raw_dir):
            if f.endswith(".md") and f not in (".ingested.json",):
                raw_basenames.add(f[:-3])
        # Keep wiki nodes even if they share a name with a raw file
        name_counts = {k: v for k, v in name_counts.items() if k not in raw_basenames or k in wiki_names}

    for node_id in sorted(name_counts):
        meta = _read_node_meta(subject, node_id)
        obj = {
            "id": node_id,
            "label": node_id,
            "title": meta.get("title") or node_id,
            "subject": subject,
            "link_count": 0,
            "type": meta["type"],
            "created": meta["created"],
            "tags": meta["tags"],
            "source_url": meta.get("source_url"),
            "file_count": name_counts[node_id],
        }
        nodes.append(obj)
        node_map[node_id] = obj

    # ── 2. Build alias map from frontmatter (port of vaultParser.js) ──
    alias_map = {}  # lowercase alias → node id
    for node_id in sorted(name_counts):
        meta = node_map[node_id]
        if meta.get("aliases"):
            for alias in meta["aliases"]:
                alias_map[alias.lower()] = node_id
            continue
        # Read frontmatter from wiki/ files for aliases
        for d in wiki_dirs:
            dpath = os.path.join(subj_dir, d)
            fpath = os.path.join(dpath, f"{node_id}.md")
            if not os.path.isfile(fpath):
                continue
            try:
                text = open(fpath, encoding="utf-8").read()
            except OSError:
                continue
            if not text.startswith("---\n"):
                continue
            end = text.find("\n---\n", 4)
            if end == -1:
                continue
            for line in text[4:end].splitlines():
                if line.strip().lower().startswith("aliases:"):
                    raw = line.split(":", 1)[1].strip()
                    if raw.startswith("[") and raw.endswith("]"):
                        for a in raw[1:-1].split(","):
                            alias_map[a.strip().strip("\"'").lower()] = node_id
                    elif raw:
                        alias_map[raw.strip().strip("\"'").lower()] = node_id
                elif line.strip().startswith("- "):
                    pass  # block-format aliases handled below
            # Block-format aliases
            lines = text[4:end].splitlines()
            for i, l in enumerate(lines):
                if l.strip().lower().startswith("aliases:"):
                    j = i + 1
                    while j < len(lines) and lines[j].strip().startswith("- "):
                        alias_map[lines[j].strip()[2:].strip().strip("\"'").lower()] = node_id
                        j += 1
            break

    # ── 3. Auto-derive edges from [[wikilinks]] (port of vaultParser.js) ──
    WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
    FENCED_RE = re.compile(r'```[\s\S]*?```')
    INLINE_RE = re.compile(r'`[^`\n]+`')
    COMMENT_RE = re.compile(r'%%[\s\S]*?%%')
    FRONTMATTER_RE = re.compile(r'^---[ \t]*\r?\n[\s\S]*?\r?\n---[ \t]*(\r?\n|$)')

    edges = []
    edge_set = set()
    backlink_map = {}

    def _add_edge(src, tgt):
        key = f"{src}→{tgt}"
        if src == tgt or key in edge_set:
            return
        edge_set.add(key)
        edges.append({"source": src, "target": tgt})
        backlink_map.setdefault(tgt, set()).add(src)

    def _resolve_target(target, source_id):
        """Resolve a [[link]] to a node id (port of vaultParser.js §8.3)."""
        t = target.strip()
        if t in node_map:
            return t
        lower = t.lower().replace(' ', '-')
        for nid in node_map:
            if nid.lower() == lower:
                return nid
        target_base = t.split("/")[-1].lower()
        candidates = [nid for nid in node_map if nid.split("/")[-1].lower() == target_base]
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            source_dir = source_id.rsplit("/", 1)[0] if "/" in source_id else ""
            for c in candidates:
                if source_dir and c.startswith(source_dir + "/"):
                    return c
            return sorted(candidates)[0]
        if lower in alias_map:
            return alias_map[lower]
        return None  # unresolved → ghost node

    # Scan wiki/ files for [[wikilinks]]
    for d in ["wiki"]:
        dpath = os.path.join(subj_dir, d)
        if not os.path.isdir(dpath):
            continue
        for fname in sorted(os.listdir(dpath)):
            if not fname.endswith(".md") or fname.startswith("."):
                continue
            if fname in ("index.md", "log.md"):
                continue
            source_id = fname[:-3]
            if source_id not in node_map:
                continue
            fpath = os.path.join(dpath, fname)
            try:
                raw = open(fpath, encoding="utf-8").read()
            except OSError:
                continue
            # Strip frontmatter, fenced code, inline code, comments
            body = FRONTMATTER_RE.sub("", raw)
            body = FENCED_RE.sub("", body)
            body = INLINE_RE.sub("", body)
            body = COMMENT_RE.sub("", body)
            for m in WIKILINK_RE.finditer(body):
                link_part = m.group(1).split("|")[0]  # discard display alias
                target = link_part.split("#")[0].strip()  # discard heading
                resolved = _resolve_target(target, source_id)
                if resolved:
                    _add_edge(source_id, resolved)
                else:
                    ghost_id = "__ghost__/" + re.sub(r"\s+", "-", target.lower().strip())
                    if ghost_id not in node_map:
                        ghost = {
                            "id": ghost_id,
                            "label": target.strip(),
                            "subject": subject,
                            "link_count": 0,
                            "type": "ghost",
                            "created": None,
                            "tags": [],
                            "file_count": 1,
                            "exists": False,
                        }
                        node_map[ghost_id] = ghost
                        nodes.append(ghost)
                    _add_edge(source_id, ghost_id)

    # ── 4. Compute link_count + backlinks ──
    for node in nodes:
        node["link_count"] = sum(
            1 for e in edges
            if e["target"] == node["id"] or e["source"] == node["id"]
        )
        if node["id"] in backlink_map:
            node["backlinks"] = sorted(backlink_map[node["id"]])

    return nodes, edges


def _list_entries(abs_dir, vault_prefix, subject):
    """Recursively list entries in a directory, building tree structure for dirs."""
    entries = []
    try:
        names = sorted(os.listdir(abs_dir))
    except OSError:
        return entries

    for name in names:
        if name.startswith("."):
            continue
        abs_path = os.path.join(abs_dir, name)
        rel_path = os.path.join(vault_prefix, name)
        entry = {"name": name, "path": rel_path}

        if os.path.isdir(abs_path):
            entry["type"] = "dir"
            entry["children"] = _list_entries(abs_path, rel_path, subject)
        else:
            entry["type"] = "file"
            orig_filename = _find_original(subject, name)
            entry["has_original"] = orig_filename is not None
            if orig_filename:
                entry["original_path"] = f"originals/{subject}/{orig_filename}"

        entries.append(entry)

    return entries


def _count_md_files(subject):
    """Count .md files recursively under subjects/{subject}/ (excluding hidden)."""
    subj_dir = os.path.join(VAULT, "subjects", subject)
    count = 0
    for root, dirs, files in os.walk(subj_dir):
        # Skip hidden dirs
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.startswith("."):
                continue
            if fname.endswith(".md"):
                count += 1
    return count


def _count_objects(subject):
    """Count .html files under objects/{subject}/."""
    obj_dir = os.path.join(VAULT, "objects", subject)
    if not os.path.isdir(obj_dir):
        return 0
    return sum(1 for f in os.listdir(obj_dir) if f.endswith(".html") and not f.startswith("."))


# Object type detection
OBJECT_TYPE_PREFIXES = {
 "mock-": "mock",
 "cheat-": "cheat",
 "mindmap-": "mindmap",
 "formula-": "formula",
 "flash-": "flash",
}

OBJECT_TYPE_KEYWORDS = {
 "examen": "mock", "practica": "mock",
 "summary": "cheat", "mapa": "mindmap",
 "concept": "cheat", "calculus": "formula",
 "flashcard": "flash", "card": "flash",
}

TITLE_SUFFIX_RE = re.compile(r'-v\d+\.html$')


def _infer_object_type(filename):
    for prefix, obj_type in OBJECT_TYPE_PREFIXES.items():
        if filename.startswith(prefix):
            return obj_type
    # Content-based fallback
    lower = filename.lower()
    for keyword, obj_type in OBJECT_TYPE_KEYWORDS.items():
        if keyword in lower:
            return obj_type
    return "unknown"


def _infer_object_title(filename):
    """Infer display title from filename like mock-parcial-1-v1.html → 'Parcial 1'."""
    stem = TITLE_SUFFIX_RE.sub("", filename)  # remove -vN.html
    # Remove type prefix
    for prefix in OBJECT_TYPE_PREFIXES:
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    # Replace hyphens with spaces, title-case
    return stem.replace("-", " ").strip().title()


# ── Deterministic auto-ingest from raw files ──

def _extract_sections(content):
    """Split markdown content into sections by ## headers."""
    sections = {}
    current_section = "__intro__"
    current_lines = []
    for line in content.splitlines():
        if line.startswith("## "):
            sections[current_section] = "\n".join(current_lines).strip()
            current_section = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    sections[current_section] = "\n".join(current_lines).strip()
    return sections


def _extract_definitions_from_text(text):
    """Extract definitions (lines with **bold**: description) from text."""
    defs = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ")
        m = re.match(r'\*\*(.+?)\*\*\s*[:：]\s*(.+)', stripped)
        if m:
            defs.append(f"- **{m.group(1)}**: {m.group(2)}")
    return defs


def _extract_code_blocks(content):
    """Extract code blocks with their language. Returns list of (lang, code)."""
    blocks = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("```"):
            lang = lines[i][3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            if code:
                blocks.append((lang, "\n".join(code)))
        i += 1
    return blocks


def _extract_wikilinks_from_body(body):
    """Extract unique [[wikilinked]] concept names from a body of text, ordered by first appearance."""
    seen = set()
    result = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', body):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _enrich_wikilinks(subject, body):
    """Automatically wrap mentions of other wiki page names in [[wikilinks]].

    Scans existing wiki/ files for node names (excluding index.md, log.md),
    then finds case-insensitive matches in the body and wraps them.
    Skips text inside code blocks, inline code, existing wikilinks, and headings.
    """
    wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
    if not os.path.isdir(wiki_dir):
        return body

    # Collect node names from existing wiki files (excluding structural ones)
    node_names = set()
    for fname in os.listdir(wiki_dir):
        if not fname.endswith(".md") or fname in ("index.md", "log.md", ".ingested.json"):
            continue
        # Use the file's title (without .md) as the canonical name
        node_names.add(fname[:-3])

    if not node_names:
        return body

    # Sort by length (longest first) to avoid partial matches
    # e.g. "Encapsulación" before "Clase" to not match inside unrelated words
    sorted_names = sorted(node_names, key=lambda n: (-len(n), n))

    # Split body into zones: code / existing wikilink / heading / plain text
    WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
    FENCED_RE = re.compile(r'```[\s\S]*?```')
    INLINE_RE = re.compile(r'`[^`\n]+`')
    HEADING_RE = re.compile(r'^#{1,6}\s.*$', re.MULTILINE)

    # Mask protected zones with placeholders
    masked = body
    placeholders = []

    def _mask(zone, rep):
        ph = f"\x00MASK_{len(placeholders)}\x00"
        placeholders.append((ph, zone.group(0)))
        return ph

    masked = FENCED_RE.sub(lambda m: _mask(m, 'fenced'), masked)
    masked = INLINE_RE.sub(lambda m: _mask(m, 'inline'), masked)
    masked = WIKILINK_RE.sub(lambda m: _mask(m, 'wikilink'), masked)
    masked = HEADING_RE.sub(lambda m: _mask(m, 'heading'), masked)

    # In plain text zones, replace mentions with [[wikilinks]]
    # Only match whole-word boundaries (not inside other words)
    for name in sorted_names:
        # Skip if name is too generic (single word < 3 chars could cause noise)
        if len(name) < 3:
            continue
        # Build a pattern that matches the name as a standalone word
        escaped = re.escape(name)
        # Case-insensitive, word-boundary match, not inside existing wikilink brackets
        pattern = re.compile(
            r'(?<![\[/\w])' + escaped + r'(?![\]/\w])',
            re.IGNORECASE
        )
        masked = pattern.sub(lambda m: f"[[{name}]]", masked)

    # Restore placeholders
    for ph, original in placeholders:
        masked = masked.replace(ph, original)

    return masked


def _auto_create_pages(subject, base_name):
    """Deterministically create a single wiki page from a raw markdown file.
    Writes to wiki/ (new SCHEMA structure). Skips pages that already exist.
    Returns dict with counts of pages created.
    """
    raw_path = os.path.join(VAULT, "subjects", subject, "raw", f"{base_name}.md")
    if not os.path.isfile(raw_path):
        return {"created": 0}

    with open(raw_path, encoding="utf-8") as f:
        content = f.read()

    sections = _extract_sections(content)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    created = 0

    # Build a single wiki page combining all relevant content
    parts = []

    # 1. Intro paragraph
    intro = sections.get("__intro__", "")
    if intro:
        non_heading = [l for l in intro.splitlines() if not l.startswith("# ")]
        if non_heading:
            parts.append("\n".join(non_heading))

    # 2. Concept/Definition sections
    for sn in ("Concepto", "Concept", "Definición", "Definicion", "Definition"):
        if sn in sections:
            parts.append(f"## {sn}\n\n{sections[sn]}")

    # 3. Definitions (bold-term lines from all sections)
    all_defs = []
    for sectext in sections.values():
        all_defs.extend(_extract_definitions_from_text(sectext))
    if all_defs:
        parts.append("## Key Terms\n\n" + "\n".join(all_defs))

    # 4. Formulas / Code blocks
    blocks = _extract_code_blocks(content)
    if blocks:
        code_parts = []
        for lang, code in blocks:
            label = f"Ejemplo en {lang}" if lang else "Ejemplo"
            code_parts.append(f"**{label}:**\n\n```{lang}\n{code}\n```")
        parts.append("## Examples / Formulas\n\n" + "\n\n".join(code_parts))

    # 5. Exercises
    for sn in ("Ejercicios", "Exercises", "Practice", "Problemas", "Problema"):
        if sn in sections:
            parts.append(f"## {sn}\n\n{sections[sn]}")
            break

    if parts:
        body = "\n\n---\n\n".join(parts)
        # Enrich body with [[wikilinks]]: find mentions of other wiki pages in the text
        body = _enrich_wikilinks(subject, body)
        # Append Related concepts section with wikilinked concepts found in body
        related = _extract_wikilinks_from_body(body)
        if related:
            body += "\n\n## Related concepts\n" + "".join(f"- [[{c}]]\n" for c in related)
        # Use more descriptive frontmatter matching SCHEMA style
        text = (
            f"---\n"
            f"title: {base_name.replace('-', ' ').title()}\n"
            f"type: concept\n"
            f"tags: []\n"
            f"created: {today}\n"
            f"source_url: raw/{base_name}.md\n"
            f"---\n\n"
            f"**Summary**: Notes from {base_name}.\n"
            f"**Sources**: raw/{base_name}.md\n"
            f"**Last updated**: {today}\n\n"
            f"---\n\n"
            f"{body}"
        )
        if _write_wiki_page_if_missing(subject, base_name, text):
            created += 1

    return {"created": created}


def _write_wiki_page_if_missing(subject, base_name, content):
    """Write a wiki page only if it doesn't already exist."""
    wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
    os.makedirs(wiki_dir, exist_ok=True)
    fpath = os.path.join(wiki_dir, f"{base_name}.md")
    if os.path.isfile(fpath):
        return False
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return True


# ── Wiki State Tracking ──

def _read_ingested(subject):
    """Read .ingested.json for a subject. Returns set of ingested filenames."""
    ipath = os.path.join(VAULT, "subjects", subject, "raw", ".ingested.json")
    if not os.path.isfile(ipath):
        return set()
    try:
        with open(ipath, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("ingested", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _get_remaining_ingest(subject):
    """Return list of raw .md files NOT yet ingested (excluding .ingested.json itself)."""
    raw_dir = os.path.join(VAULT, "subjects", subject, "raw")
    if not os.path.isdir(raw_dir):
        return []
    ingested = _read_ingested(subject)
    return [
        f for f in sorted(os.listdir(raw_dir))
        if f.endswith(".md") and f != ".ingested.json" and f not in ingested
    ]

def _write_ingested(subject, ingested):
    """Write .ingested.json for a subject."""
    from datetime import datetime
    ipath = os.path.join(VAULT, "subjects", subject, "raw", ".ingested.json")
    os.makedirs(os.path.dirname(ipath), exist_ok=True)
    with open(ipath, "w", encoding="utf-8") as f:
        json.dump({"ingested": sorted(ingested), "last_ingested": datetime.now().isoformat()}, f, indent=1)

def _read_pending_deletes(subject):
    """Read pending.json deletes for a subject. Returns list of base_names."""
    ppath = os.path.join(VAULT, "subjects", subject, "raw", "pending.json")
    if not os.path.isfile(ppath):
        return []
    try:
        with open(ppath, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("pending_deletes", [])
    except (json.JSONDecodeError, OSError):
        return []

def _write_pending_deletes(subject, deletes):
    """Write pending.json with a list of base_names marked for deletion."""
    ppath = os.path.join(VAULT, "subjects", subject, "raw", "pending.json")
    os.makedirs(os.path.dirname(ppath), exist_ok=True)
    with open(ppath, "w", encoding="utf-8") as f:
        json.dump({"pending_deletes": deletes}, f, indent=1)


def _log_action(subject, action, detail):
    """Append a line to the vault log.md."""
    from datetime import datetime
    log_path = os.path.join(VAULT, "log.md")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"- {ts} | {action} | {subject} | {detail}\n")


def _run_llm_ingest_thread(subject):
    """Background thread: spawns `hermes chat -q` to run LLM-powered wiki ingest.

    The agent reads un-ingested raw files for `subject`, reads SCHEMA.md to
    determine page format and conventions, runs the ingest
    (creates wiki pages, updates .ingested.json, writes wikilinks for edges), then
    writes a result file. This thread waits for the agent to finish, then loads
    the result into `_ingest_result` and clears `_ingest_running`.
    """
    global _ingest_running, _ingest_result, _ingest_current_subject, _ingest_last_created_name
    result_path = "/tmp/study_ingest_result.json"
    # Clean any prior result
    try:
        os.remove(result_path)
    except FileNotFoundError:
        pass

    # Find un-ingested files
    raw_dir = os.path.join(VAULT, "subjects", subject, "raw")
    ingested = _read_ingested(subject)
    uningested = []
    if os.path.isdir(raw_dir):
        for f in sorted(os.listdir(raw_dir)):
            if f.endswith(".md") and f != ".ingested.json" and f not in ingested:
                uningested.append(f)

    if not uningested:
        # Nothing to ingest — return early
        _ingest_result = {
            "pages_created": 0,
            "files_deleted": 0,
            "tokens_used": 0,
            "model": "no-op",
            "message": "No new files to ingest",
            "finished_at": _now_iso(),
            "status": "complete",
        }
        _ingest_running = False
        _ingest_current_subject = None
        _ingest_total_pending = 0
        _log_action(subject, "UPDATE_WIKI_INGEST", "no files to ingest")
        return

    file_list = "\n".join(f"- {f}" for f in uningested)
    prompt = f"""This is a NON-INTERACTIVE automated wiki ingest for subject '{subject}'. Do NOT ask the user questions or wait for discussion — just do the work.

Un-ingested raw files in ~/study-vault/subjects/{subject}/raw/:
{file_list}

STEP 1 — Read SCHEMA.md at ~/study-vault/subjects/{subject}/SCHEMA.md if it exists.
Follow its page format, frontmatter, and interlinking rules. If SCHEMA.md says to "discuss" or "ask the user", SKIP that step — this is automated.

If SCHEMA.md does NOT exist, use these defaults:
- Page format: markdown with YAML frontmatter (title, created, type, tags, source_url)
- Frontmatter type: one of source_summary, concept, formula, definition, exercise
- `tags`: exactly ONE topic tag per page (e.g., `tags: [arrays]`). Pick the single most specific topic.
- `source_url`: path to the raw file this page derives from (e.g., `source_url: raw/2026-cd-tp6.md`)
- Source summaries: name them `src-{{base-name}}` (e.g., `src-2026-cd-tp6.md`) — never reuse raw/ filenames
- Create BOTH a source summary page per raw file AND concept pages for each distinct concept
- Use [[wikilinks]] with exact lowercase-hyphen filenames (e.g., `[[cable-coaxial]]`, not `[[Cable Coaxial]]`)
- Every concept wikilinked MUST have its own page — no orphan wikilinks
- End each concept page with a "## Related concepts" section
- Page names: lowercase-with-hyphens.md

STEP 2 — Follow the Ingest Workflow defined in SCHEMA.md:
- For each un-ingested raw .md file, do exactly what SCHEMA.md says (source pages + concept pages)
- After processing each file, **immediately** add its filename to the `ingested` array in raw/.ingested.json

STEP 3 — After all files are processed:
1. Update wiki/index.md with new pages and one-line descriptions
2. Append an entry to wiki/log.md with the date, source name, and what changed

RULES:
- Preserve any existing wiki pages — never overwrite or delete files you did not create
- Never modify anything in raw/
- This is non-interactive — never ask the user questions or wait for input

WHEN COMPLETE, write the result file at {result_path} with EXACTLY this JSON (no other text in the file):
{{"pages_created": N, "tokens_used": N, "model": "<provider>/<model>", "status": "complete"}}

- pages_created: total number of new wiki pages you created across all files
- tokens_used: total tokens consumed (input + output) for the ingest
- model: the model identifier (e.g., opencode-zen/minimax-m3-free)
- status: "complete" on success, "error" on failure

Use the terminal and file tools to read/write files. Be thorough — the wiki pages should be high quality with proper structure, examples, and cross-links."""

    # Spawn hermes subprocess (one-shot, quiet, yolo for non-interactive tool use).
    # No skills loaded — the agent follows SCHEMA.md for page format and conventions.
    # No --provider/-m flags → Hermes uses the default model and falls through
    # fallback_providers automatically if the default is unavailable.
    # NOTE: No timeout — process only stops when the LLM completes or errors.
    try:
        proc = subprocess.run(
            ["hermes", "chat", "-q", prompt,
             "-Q", # quiet mode (no banner)
             "--yolo", # auto-approve tool use
             "--accept-hooks"],
            cwd=os.path.expanduser("~"),
            capture_output=True,
            text=True,
        )
        agent_output = proc.stdout + "\n" + proc.stderr
    except Exception as e:
        agent_output = f"[error] {e}"

    # Read result file written by agent
    pages_created = 0
    tokens_used = 0
    model = "opencode-zen/minimax-m3-free"
    status = "error"
    if os.path.isfile(result_path):
        try:
            with open(result_path) as f:
                data = json.load(f)
            pages_created = int(data.get("pages_created", 0))
            tokens_used = int(data.get("tokens_used", 0))
            model = data.get("model", model)
            status = data.get("status", "complete")
        except (json.JSONDecodeError, ValueError) as e:
            status = "error"

    # If result file missing or tokens are zero, try fallback methods
    if status != "complete" or (pages_created == 0 and tokens_used == 0):
        # Fallback 1: parse agent output for token lines
        for line in agent_output.splitlines():
            if "API call #" in line and "total=" in line:
                m = re.search(r"total=(\d+)", line)
                if m:
                    tokens_used += int(m.group(1))

        # Fallback 2: read token counts from Hermes sessions DB
        if tokens_used == 0:
            try:
                import sqlite3 as _sq3
                _db = os.path.expanduser("~/.hermes/sessions.db")
                if os.path.isfile(_db):
                    _conn = _sq3.connect(_db)
                    _cur = _conn.execute(
                        "SELECT input_tokens + output_tokens + COALESCE(cache_read_tokens,0) + COALESCE(cache_write_tokens,0) + COALESCE(reasoning_tokens,0) "
                        "FROM sessions WHERE started_at > ? ORDER BY started_at DESC LIMIT 1",
                        (time.time() - 14400,)  # within last 4 hours (ingest can run long)
                    )
                    _row = _cur.fetchone()
                    _conn.close()
                    if _row and _row[0]:
                        tokens_used = int(_row[0])
            except Exception:
                pass  # non-critical, keep tokens_used=0

    _ingest_result = {
        "pages_created": pages_created,
        "files_deleted": 0,
        "tokens_used": tokens_used,
        "model": model,
        "message": (f"LLM ingest complete: {pages_created} pages created, "
                   f"{tokens_used} tokens used"),
        "finished_at": _now_iso(),
        "status": status,
    }
    _ingest_running = False
    _ingest_current_subject = None
    _ingest_total_pending = 0
    _log_action(subject, "UPDATE_WIKI_INGEST",
                f"{pages_created} pages, {tokens_used} tokens, model={model}")


def _now_iso():
    """ISO 8601 timestamp for logging and result records."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _cascade_delete(subject, base_name, delete_raw=True):
    """Delete a raw file + all derived wiki pages + originals + objects.
    
    Returns dict with:
      - deleted_files: list of relative paths deleted
      - deleted_ids: set of node ids
      - ingested_updated: bool — whether .ingested.json was modified
    """
    result = {
        "deleted_files": [],
        "deleted_ids": set(),
        "ingested_updated": False,
    }
    subj_dir = os.path.join(VAULT, "subjects", subject)
    source_tag = f"raw/{base_name}.md"
    ingested = _read_ingested(subject)

    # — 1. Delete raw file —
    raw_path = os.path.join(subj_dir, "raw", f"{base_name}.md")
    if delete_raw and os.path.isfile(raw_path):
        os.remove(raw_path)
        result["deleted_files"].append(f"subjects/{subject}/raw/{base_name}.md")

    # — 2. Delete wiki pages (exact match + derived via frontmatter) —
    for wtype in ("concepts", "definitions", "formulas", "exercises", "wiki"):
        wdir = os.path.join(subj_dir, wtype)
        if not os.path.isdir(wdir):
            continue
        for wf in list(os.listdir(wdir)):
            if not wf.endswith(".md"):
                continue
            # Skip structural wiki files
            if wtype == "wiki" and wf in ("index.md", "log.md"):
                continue
            wf_path = os.path.join(wdir, wf)

            # Delete exact match
            if wf == f"{base_name}.md":
                os.remove(wf_path)
                result["deleted_files"].append(f"{wtype}/{wf}")
                result["deleted_ids"].add(base_name)
                continue

            # Delete derived pages via frontmatter source_url
            try:
                with open(wf_path, encoding="utf-8") as fh:
                    head = fh.read()
                if head.startswith("---"):
                    end = head.find("\n---", 3)
                    if end > 0:
                        fm = head[3:end]
                        for fmline in fm.splitlines():
                            k, _, v = fmline.partition(":")
                            if k.strip() == "source_url" and v.strip() == source_tag:
                                os.remove(wf_path)
                                derived_id = wf[:-3]  # strip .md
                                result["deleted_files"].append(f"{wtype}/{wf}")
                                result["deleted_ids"].add(derived_id)
                                break
            except Exception:
                pass

    # — 3. Delete original file —
    orig_dir = os.path.join(VAULT, "originals", subject)
    if os.path.isdir(orig_dir):
        for f in os.listdir(orig_dir):
            if f.startswith(base_name + ".") or f == base_name:
                os.remove(os.path.join(orig_dir, f))
                result["deleted_files"].append(f"originals/{subject}/{f}")

    # — 4. Delete objects (prefix match, not substring) —
    obj_dir = os.path.join(VAULT, "objects", subject)
    if os.path.isdir(obj_dir):
        for f in os.listdir(obj_dir):
            if f == f"{base_name}.html" or f.startswith(f"{base_name}-"):
                fp = os.path.join(obj_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
                    result["deleted_files"].append(f"objects/{subject}/{f}")

    # — 5. Remove from ingested set —
    fname = f"{base_name}.md"
    if fname in ingested:
        ingested.discard(fname)
        _write_ingested(subject, ingested)
        result["ingested_updated"] = True

    # — 6. Remove edges from relationships.md — REMOVED — edges come exclusively from [[wikilinks]] in wiki/ pages
    
    return result


class StudyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the study server."""

    def log_message(self, format, *args):
        pass  # suppress default access logs

    def _set_cors(self):
        origin = self.headers.get("Origin", "")
        allowed = [
            "https://study.example.com",
            "http://localhost:8081",
            "http://localhost:8080",
            "http://127.0.0.1:8081",
            "http://127.0.0.1:8080",
        ]
        if origin in allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self._set_cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, abs_path, content_type, cache_control=None):
        if not os.path.isfile(abs_path):
            self._send_json(404, {"error": "not_found", "detail": "File not found"})
            return
        with open(abs_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self._set_cors()
        if cache_control:
            self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ── API Handlers ──

    def _api_subjects(self):
        """GET /api/subjects"""
        subs_dir = os.path.join(VAULT, "subjects")
        subjects = []

        if os.path.isdir(subs_dir):
            for name in sorted(os.listdir(subs_dir)):
                if name.startswith("."):
                    continue
                if not os.path.isdir(os.path.join(subs_dir, name)):
                    continue
                theme = SUBJECT_THEMES.get(name, SUBJECT_THEMES.get("_default", {}))
                subjects.append({
                    "name": name,
                    "theme": theme,
                    "file_count": _count_md_files(name),
                    "object_count": _count_objects(name),
                })

        self._send_json(200, {"subjects": subjects})

    def _api_files(self, params):
        """GET /api/files?subject=X&path=Y"""
        subject = params.get("subject", [None])[0]
        if not subject:
            self._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
            return

        if not _subject_exists(subject):
            self._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
            return

        rel_path = params.get("path", [f"subjects/{subject}"])[0]
        abs_path = _resolve_vault_path(rel_path)
        if abs_path is None:
            self._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
            return

        # Ensure the resolved path is within this subject's directory
        subj_prefix = f"subjects/{subject}"
        if not os.path.abspath(abs_path).startswith(os.path.join(VAULT, subj_prefix) + os.sep) and abs_path != os.path.join(VAULT, subj_prefix):
            self._send_json(403, {"error": "path_traversal", "detail": "Path is outside the requested subject"})
            return

        if not os.path.exists(abs_path):
            self._send_json(404, {"error": "path_not_found", "detail": f"Path not found: {rel_path}"})
            return

        if not os.path.isdir(abs_path):
            self._send_json(400, {"error": "not_a_directory", "detail": "Path is not a directory"})
            return

        entries = _list_entries(abs_path, rel_path, subject)
        self._send_json(200, {"path": rel_path, "entries": entries})

    def _api_file_content(self, params):
        """GET /api/file-content?path=X"""
        rel_path = params.get("path", [None])[0]
        if not rel_path:
            self._send_json(400, {"error": "missing_path", "detail": "path parameter is required"})
            return

        # Security check first — traversal is a security concern, overrides extension validation
        abs_path = _resolve_vault_path(rel_path)
        if abs_path is None:
            self._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
            return

        if not rel_path.endswith(".md"):
            self._send_json(400, {"error": "not_a_markdown_file", "detail": "Only .md files can be served"})
            return

        if not os.path.isfile(abs_path):
            self._send_json(404, {"error": "file_not_found", "detail": f"File not found: {rel_path}"})
            return

        with open(abs_path, encoding="utf-8") as f:
            content = f.read()

        # Determine subject from path (e.g., "subjects/poo/concepts/herencia.md" -> "poo")
        parts = rel_path.split("/")
        subject = parts[1] if len(parts) >= 2 and parts[0] == "subjects" else None

        # Check for original file
        basename = os.path.basename(rel_path)
        has_original = False
        original_path = None
        if subject:
            name_no_ext, _ = os.path.splitext(basename)
            orig_dir = os.path.join(VAULT, "originals", subject)
            if os.path.isdir(orig_dir):
                for fname in os.listdir(orig_dir):
                    if fname.startswith("."):
                        continue
                    f_no_ext, _ = os.path.splitext(fname)
                    if f_no_ext == name_no_ext:
                        has_original = True
                        original_path = f"originals/{subject}/{fname}"
                        break

        self._send_json(200, {
            "path": rel_path,
            "content": content,
            "has_original": has_original,
            "original_path": original_path,
        })

    def _api_objects(self, params):
        """GET /api/objects?subject=X"""
        subject = params.get("subject", [None])[0]
        if not subject:
            self._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
            return

        obj_dir = os.path.join(VAULT, "objects", subject)
        objects = []
        if os.path.isdir(obj_dir):
            for fname in os.listdir(obj_dir):
                if fname.startswith(".") or not fname.endswith(".html"):
                    continue
                fpath = os.path.join(obj_dir, fname)
                size = os.path.getsize(fpath)
                mtime = os.path.getmtime(fpath)
                objects.append({
                    "name": fname,
                    "path": f"objects/{subject}/{fname}",
                    "type": _infer_object_type(fname),
                    "title": _infer_object_title(fname),
                    "size_bytes": size,
                    "mtime": mtime,
                })
            objects.sort(key=lambda o: o["mtime"], reverse=True)
            for o in objects:
                del o["mtime"]

        self._send_json(200, {"subject": subject, "objects": objects})

    def _api_object_content(self, params):
        """GET /api/object-content?path=X"""
        rel_path = params.get("path", [None])[0]
        if not rel_path:
            self._send_json(400, {"error": "missing_path", "detail": "path parameter is required"})
            return

        # Security check first
        abs_path = _resolve_vault_path(rel_path)
        if abs_path is None:
            self._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
            return

        if not rel_path.endswith(".html"):
            self._send_json(400, {"error": "not_an_html_file", "detail": "Only .html files can be served as objects"})
            return

        if not os.path.isfile(abs_path):
            self._send_json(404, {"error": "file_not_found", "detail": f"File not found: {rel_path}"})
            return

        self._send_file(abs_path, "text/html; charset=utf-8")

    def _api_graph(self, params):
        """GET /api/graph?subject=X"""
        subject = params.get("subject", [None])[0]
        if not subject:
            self._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
            return
        if not _subject_exists(subject):
            self._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
            return
        nodes, edges = _parse_relationships(subject)
        self._send_json(200, {"subject_filter": subject, "nodes": nodes, "edges": edges})

    def _api_lint(self, params):
        """GET /api/lint?subject=X — orphan, missing frontmatter, stale checks."""
        subject = params.get("subject", [None])[0]
        if not subject:
            self._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
            return
        if not _subject_exists(subject):
            self._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
            return

        nodes, edges = _parse_relationships(subject)
        issues = []

        # ── Orphan pages (link_count == 0) ──
        for n in nodes:
            if n["link_count"] == 0:
                issues.append({
                    "type": "orphan",
                    "severity": "warning",
                    "node": n["id"],
                    "detail": f"No edges connect to or from '{n['id']}'"
                })

        # ── Missing frontmatter ──
        scan_dirs = []
        # New SCHEMA structure: wiki/
        wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
        if os.path.isdir(wiki_dir):
            scan_dirs.append(("wiki", wiki_dir))
        # Legacy dirs
        for d in ["concepts", "definitions", "formulas", "exercises"]:
            dpath = os.path.join(VAULT, "subjects", subject, d)
            if os.path.isdir(dpath):
                scan_dirs.append((d, dpath))
        for dir_label, dpath in scan_dirs:
            for fname in sorted(os.listdir(dpath)):
                if not fname.endswith(".md") or fname.startswith("."):
                    continue
                # Skip structural wiki files
                if dir_label == "wiki" and fname in ("index.md", "log.md"):
                    continue
                fpath = os.path.join(dpath, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                if not content.startswith("---\n"):
                    issues.append({
                        "type": "missing_frontmatter",
                        "severity": "warning",
                        "node": fname[:-3],
                        "detail": f"{dir_label}/{fname} has no YAML frontmatter"
                    })

        # ── Stale files (created > 90 days ago) ──
        from datetime import datetime, date as _date
        today = _date.today()
        for n in nodes:
            if n.get("created"):
                try:
                    created = datetime.strptime(str(n["created"]), "%Y-%m-%d").date()
                    delta = (today - created).days
                    if delta > 365:
                        issues.append({
                            "type": "stale",
                            "severity": "info",
                            "node": n["id"],
                            "detail": f"Created {delta} days ago ({n['created']}). Lint never deletes content — study when ready."
                        })
                except ValueError:
                    pass

        issues.sort(key=lambda x: {"error": 0, "warning": 1, "info": 2}.get(x["severity"], 3))
        self._send_json(200, {
            "subject": subject,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "issue_count": len(issues),
            "issues": issues,
        })

    def _regenerate_index(self, subject):
        """Rewrite index.md for a subject from the actual filesystem."""
        subj_dir = os.path.join(VAULT, "subjects", subject)
        lines = [f"# {subject.title()} — Index", ""]

        # Raw materials section
        lines.append("## Raw Materials")
        raw_dir = os.path.join(subj_dir, "raw")
        if os.path.isdir(raw_dir):
            for fname in sorted(os.listdir(raw_dir)):
                if not fname.endswith(".md") or fname.startswith("."):
                    continue
                lines.append(f"- {fname}")
        lines.append("")

        # Wiki pages section (new SCHEMA structure)
        wiki_dir = os.path.join(subj_dir, "wiki")
        if os.path.isdir(wiki_dir):
            wiki_pages = [f for f in sorted(os.listdir(wiki_dir))
                          if f.endswith(".md") and not f.startswith(".")
                          and f not in ("index.md", "log.md")]
            if wiki_pages:
                lines.append("## Wiki Pages")
                for fname in wiki_pages:
                    lines.append(f"- [[{fname[:-3]}]]")
                lines.append("")

        # Legacy sections (fallback for subjects created before SCHEMA migration)
        for section, dir_name in [("Concepts", "concepts"), ("Definitions", "definitions"),
                                    ("Formulas", "formulas"), ("Exercises", "exercises")]:
            dpath = os.path.join(subj_dir, dir_name)
            if os.path.isdir(dpath):
                has_files = any(f.endswith(".md") and not f.startswith(".")
                                for f in os.listdir(dpath))
                if has_files:
                    lines.append(f"## {section}")
                    for fname in sorted(os.listdir(dpath)):
                        if not fname.endswith(".md") or fname.startswith("."):
                            continue
                        lines.append(f"- [[{fname[:-3]}]]")
                    lines.append("")

        lines.append("## Relationships\nSee [[relationships]]\n")
        lines.append("<!-- auto-generated by /api/regenerate-index -->\n")
        index_path = os.path.join(subj_dir, "index.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _api_regenerate_index(self, params):
        """POST /api/regenerate-index — rewrite index.md from filesystem (or GET with ?subject=X)."""
        subject = params.get("subject", [None])[0] if params else None
        if not subject:
            try:
                cl = int(self.headers.get("Content-Length", 0))
                if cl > 1_000_000:
                    self._send_json(413, {"error": "body_too_large",
                                          "detail": "JSON body exceeds 1 MB limit"})
                    return
                if cl > 0:
                    body = json.loads(self.rfile.read(cl).decode("utf-8"))
                    subject = body.get("subject", "")
            except (ValueError, json.JSONDecodeError):
                pass
        if not subject:
            self._send_json(400, {"error": "missing_subject", "detail": "subject is required"})
            return
        if not _subject_exists(subject):
            self._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
            return
        self._regenerate_index(subject)
        self._send_json(200, {"subject": subject, "path": f"subjects/{subject}/index.md", "updated": True})

    def _api_upload(self):
        """POST /api/upload — multipart upload with MarkItDown conversion + auto-ingest."""
        global _upload_in_progress
        if _upload_in_progress or _ingest_running:
            self._send_json(503, {"error": "busy",
                                  "detail": "Another operation in progress, try again shortly"})
            return
        _upload_in_progress = True

        try:
            self._do_upload()
        finally:
            _upload_in_progress = False

    def _do_upload(self):
        """POST /api/upload — multipart upload with MarkItDown conversion."""
        # 1. Check Content-Length ≤ 50MB
        cl_str = self.headers.get("Content-Length", "0")
        content_length = int(cl_str) if cl_str.isdigit() else 0
        if content_length > 52428800:
            self._send_json(413, {"error": "file_too_large",
                                  "detail": "File exceeds 50 MB limit"})
            return

        # 2. Check Content-Type is multipart
        ct = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ct:
            self._send_json(400, {"error": "invalid_content_type",
                                  "detail": "Expected multipart/form-data"})
            return

        parts = parse_multipart(self)

        # 3. Validate subject
        subject = parts.get("subject", "")
        if not subject:
            self._send_json(400, {"error": "missing_subject",
                                  "detail": "subject field is required"})
            return

        # 4. Validate subject exists
        if not _subject_exists(subject):
            self._send_json(404, {"error": "subject_not_found",
                                  "detail": f"Subject '{subject}' does not exist"})
            return

        # 5. Validate file
        file_part = parts.get("file")
        if not file_part:
            self._send_json(400, {"error": "missing_file",
                                  "detail": "file field is required"})
            return

        filename = file_part["filename"]
        data = file_part["data"]

        # 6. Validate extension
        _, ext = os.path.splitext(filename)
        allowed = [".pdf", ".pptx", ".docx", ".xlsx", ".jpg", ".png"]
        if ext.lower() not in allowed:
            self._send_json(400, {"error": "unsupported_format",
                                  "detail": f"Format '{ext}' not supported. Allowed: {', '.join(allowed)}"})
            return

        # 7. Save original file
        name_no_ext, _ = os.path.splitext(filename)
        slug = slugify(name_no_ext)
        orig_filename = f"{slug}{ext}"
        orig_dir = os.path.join(VAULT, "originals", subject)
        os.makedirs(orig_dir, exist_ok=True)
        orig_path = os.path.join(orig_dir, orig_filename)
        with open(orig_path, "wb") as f:
            f.write(data)

        # 8. Convert via MarkItDown
        raw_dir = os.path.join(VAULT, "subjects", subject, "raw")
        os.makedirs(raw_dir, exist_ok=True)
        md_filename = f"{slug}.md"
        md_path = os.path.join(raw_dir, md_filename)

        success, stderr = run_markitdown(orig_path, md_path)
        if not success:
            # Remove original on conversion failure
            os.remove(orig_path)
            self._send_json(500, {"error": "conversion_failed",
                                  "detail": stderr})
            return

        # 9. Log the upload
        log_path = os.path.join(VAULT, "log.md")
        try:
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            safe_name = filename.replace('\n', ' ').replace('\r', ' ').replace('|', ' ')
            with open(log_path, "a") as logf:
                logf.write(f"- {ts} | UPLOAD | {subject} | {safe_name} → raw/{md_filename}\n")
        except OSError:
            pass  # non-critical

        # 10. Skip auto-ingest: raw files in raw/ only. Wiki pages are created
        # by the "Update Wiki" button instead, using SCHEMA.md naming conventions.

        # 11. Auto-regenerate index to reflect the new file
        try:
            self._regenerate_index(subject)
        except OSError:
            pass  # non-critical

        self._send_json(200, {
            "markdown_path": f"subjects/{subject}/raw/{md_filename}",
            "original_path": f"originals/{subject}/{orig_filename}",
            "filename": filename,
            "conversion": "success",
        })

    def _api_delete_file(self):
        """POST /api/delete-file — cascade-delete a file and all its wiki pages/objects/edges."""
        global _ingest_running
        if _ingest_running:
            self._send_json(503, {"error": "ingest_in_progress",
                                  "detail": "Ingest in progress, try again shortly"})
            return
        _ingest_running = True
        try:
            self._do_delete_file()
        finally:
            _ingest_running = False

    def _do_delete_file(self):
        """Internal delete — called with _ingest_running lock held."""
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > 1_000_000:
                self._send_json(413, {"error": "body_too_large",
                                      "detail": "JSON body exceeds 1 MB limit"})
                return
            body = json.loads(self.rfile.read(cl).decode("utf-8"))
        except (ValueError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_body", "detail": "Expected JSON body"})
            return

        rel_path = body.get("path", "")
        if not rel_path:
            self._send_json(400, {"error": "missing_path", "detail": "path is required"})
            return

        abs_path = _resolve_vault_path(rel_path)
        if abs_path is None:
            self._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
            return

        # Only allow deletions inside subjects/{subject}/raw/
        parts = rel_path.split("/")
        if len(parts) < 3 or parts[0] != "subjects" or parts[2] != "raw":
            self._send_json(403, {"error": "forbidden", "detail": "Only raw/ files can be deleted from the UI"})
            return

        subject = parts[1]
        base_name = os.path.splitext(os.path.basename(rel_path))[0]
        removed_edges = 0

        if not os.path.exists(abs_path):
            self._send_json(404, {"error": "not_found", "detail": "File not found"})
            return
        if not os.path.isfile(abs_path):
            self._send_json(400, {"error": "not_a_file", "detail": "Path is not a file"})
            return

        # Cascade delete via shared function (raw, wiki, derived, originals, objects, edges, ingested)
        cascade_result = _cascade_delete(subject, base_name, delete_raw=True)
        removed = [rel_path] + cascade_result["deleted_files"]
        removed_edges = len(cascade_result["deleted_ids"])

        # — Log —
        log_path = os.path.join(VAULT, "log.md")
        try:
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(log_path, "a") as logf:
                logf.write(f"- {ts} | DELETE | {subject} | {base_name} ({len(removed)} files, {removed_edges} edges removed)\n")
        except OSError:
            pass

        # — Regenerate index —
        try:
            self._regenerate_index(subject)
        except OSError:
            pass

        self._send_json(200, {
            "subject": subject,
            "base_name": base_name,
            "removed": removed,
            "edges_removed": removed_edges,
            "index_updated": True,
        })

    def _api_search(self, params):
        """GET /api/search?q=X&subject=Y"""
        q = params.get("q", [""])[0]
        subject_filter = params.get("subject", [""])[0]

        if len(q) < 2:
            self._send_json(400, {"error": "query_too_short",
                                  "detail": "Query must be at least 2 characters"})
            return

        root = os.path.join(VAULT, "subjects", subject_filter) if subject_filter else os.path.join(VAULT, "subjects")
        if not os.path.isdir(root):
            self._send_json(200, {"query": q, "subject_filter": subject_filter, "results": []})
            return

        results = []
        q_lower = q.lower()
        # Strip accents for accent-insensitive matching
        q_plain = ''.join(c for c in unicodedata.normalize('NFD', q_lower)
                          if not unicodedata.combining(c))
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if not fn.endswith(".md") or fn.startswith("."):
                    continue
                if fn in ("index.md", "log.md"):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except OSError:
                    continue

                content_plain = ''.join(
                    c for c in unicodedata.normalize('NFD', content.lower())
                    if not unicodedata.combining(c))

                count = content_plain.count(q_plain)
                if count == 0:
                    continue

                # Find all match positions (line numbers) using accent-insensitive check
                lines = content.splitlines(keepends=True)
                match_positions = []
                for line_no, line in enumerate(lines, 1):
                    line_plain = ''.join(
                        c for c in unicodedata.normalize('NFD', line.lower())
                        if not unicodedata.combining(c))
                    if q_plain in line_plain:
                        match_positions.append(line_no)

                # Find first match position in original content for snippet
                idx = -1
                for i in range(len(content)):
                    chunk = content[i:i + len(q)]
                    chunk_plain = ''.join(
                        c for c in unicodedata.normalize('NFD', chunk.lower())
                        if not unicodedata.combining(c))
                    if chunk_plain == q_plain:
                        idx = i
                        break

                if idx < 0:
                    continue  # safety: shouldn't happen after count>0

                start = max(0, idx - 75)
                end = min(len(content), idx + len(q) + 75)
                snippet = content[start:end]

                # Highlight the query term in the snippet using §§§ (safe, no md conflict)
                actual_match = content[idx:idx + len(q)]
                snippet = snippet.replace(actual_match, f"§§§{actual_match}§§§", 1)

                rel = os.path.relpath(path, VAULT)
                subj = rel.split(os.sep)[1] if rel.startswith("subjects") else ""

                results.append({
                    "path": rel.replace(os.sep, "/"),
                    "subject": subj,
                    "snippet": snippet,
                    "match_count": count,
                    "match_positions": match_positions,
                })

        results.sort(key=lambda r: r["match_count"], reverse=False)
        self._send_json(200, {
            "query": q,
            "subject_filter": subject_filter,
            "results": results[:20],
        })

    def _api_status(self):
        """GET /api/status — current server state (ingest lock, queue, last result)."""
        global _ingest_running, _ingest_result, _ingest_current_subject, _ingest_total_pending
        global _ingest_initial_wiki_count, _ingest_initial_total, _ingest_last_created_name
        # If ingest is running, compute live progress from filesystem
        wiki_pages_created = 0
        if _ingest_running and _ingest_current_subject:
            remaining = len(_get_remaining_ingest(_ingest_current_subject))
            _ingest_total_pending = remaining
            # Count current wiki/ .md files — gives progress even if .ingested.json is not updated per-file
            wiki_dir = os.path.join(VAULT, "subjects", _ingest_current_subject, "wiki")
            if os.path.isdir(wiki_dir):
                current_wiki_count = sum(
                    1 for f in os.listdir(wiki_dir)
                    if f.endswith(".md") and f not in ("index.md", "log.md")
                )
                wiki_pages_created = max(0, current_wiki_count - _ingest_initial_wiki_count)
        self._send_json(200, {
            "ingest_running": _ingest_running,
            "pending_total": _ingest_total_pending,
            "initial_total": _ingest_initial_total,
            "wiki_pages_created": wiki_pages_created,
            "last_created_name": _ingest_last_created_name,
            "queue_length": 0,
            "result": _ingest_result,
        })
    def _api_original(self, params):
        """GET /api/original?path=X — serve original uploaded file."""
        rel_path = params.get("path", [None])[0]
        if not rel_path:
            self._send_json(400, {"error": "missing_path", "detail": "path parameter is required"})
            return

        abs_path = _resolve_vault_path(rel_path)
        if abs_path is None:
            self._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
            return

        if not os.path.isfile(abs_path):
            self._send_json(404, {"error": "file_not_found", "detail": f"File not found: {rel_path}"})
            return

        _, ext = os.path.splitext(abs_path)
        allowed_exts = {".pdf", ".pptx", ".docx", ".xlsx", ".jpg", ".jpeg", ".png"}
        if ext.lower() not in allowed_exts:
            self._send_json(403, {"error": "forbidden_format",
                                  "detail": f"Format '{ext}' not allowed for download"})
            return
        mime_map = {
            ".pdf": "application/pdf",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }
        content_type = mime_map.get(ext.lower(), "application/octet-stream")

        with open(abs_path, "rb") as f:
            body = f.read()

        basename = os.path.basename(abs_path)
        self.send_response(200)
        self._set_cors()
        self.send_header("Content-Type", content_type)
        safe_basename = basename.replace('"', '').replace('\n', '').replace('\r', '')
        self.send_header("Content-Disposition", f'attachment; filename="{safe_basename}"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _api_pending_state(self, params):
        """GET /api/pending-state?subject=X — return ingested + pending delete state."""
        subject = params.get("subject", [None])[0]
        if not subject:
            self._send_json(400, {"error": "missing_subject", "detail": "subject parameter required"})
            return
        ingested = _read_ingested(subject)
        pending = _read_pending_deletes(subject)
        raw_dir = os.path.join(VAULT, "subjects", subject, "raw")
        raw_files = []
        if os.path.isdir(raw_dir):
            for f in sorted(os.listdir(raw_dir)):
                if f.endswith(".md") and f != ".ingested.json":
                    raw_files.append(f)
        self._send_json(200, {
            "ingested": sorted(ingested),
            "pending_deletes": pending,
            "raw_files": raw_files,
        })

    def _api_mark_file(self):
        """POST /api/mark-file — mark/unmark a raw file for deletion."""
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > 1_000_000:
                self._send_json(413, {"error": "body_too_large",
                                      "detail": "JSON body exceeds 1 MB limit"})
                return
            body = json.loads(self.rfile.read(cl)) if cl else {}
            rel_path = body.get("path", "")
            action = body.get("action", "")
            subject = body.get("subject", "")
            if not subject or not rel_path or action not in ("delete", "undo"):
                self._send_json(400, {"error": "missing_fields", "detail": "path, subject, and action (delete/undo) are required"})
                return
            if not _subject_exists(subject):
                self._send_json(404, {"error": "subject_not_found",
                                      "detail": f"Subject '{subject}' not found"})
                return
            base_name = os.path.splitext(os.path.basename(rel_path))[0]
            pending = _read_pending_deletes(subject)
            if action == "delete":
                if base_name not in pending:
                    pending.append(base_name)
                    _write_pending_deletes(subject, pending)
                self._send_json(200, {"marked": True, "action": "delete", "base_name": base_name})
            elif action == "undo":
                pending = [p for p in pending if p != base_name]
                _write_pending_deletes(subject, pending)
                self._send_json(200, {"marked": False, "action": "undo", "base_name": base_name})
            else:
                self._send_json(400, {"error": "invalid_action", "detail": "action must be 'delete' or 'undo'"})
        except json.JSONDecodeError:
            self._send_json(400, {"error": "invalid_json"})

    def _api_update_wiki(self):
        """POST /api/update-wiki — cascade delete sync, LLM ingest async."""
        global _ingest_running, _ingest_result, _ingest_current_subject, _ingest_last_created_name
        if _ingest_running:
            self._send_json(503, {"error": "ingest_in_progress", "detail": "Wait for current operation to finish"})
            return
        try:
            cl = int(self.headers.get("Content-Length", 0))
            if cl > 1_000_000:
                self._send_json(413, {"error": "body_too_large",
                                      "detail": "JSON body exceeds 1 MB limit"})
                return
            body = json.loads(self.rfile.read(cl)) if cl else {}
            subject = body.get("subject", "")
            if not subject:
                self._send_json(400, {"error": "missing_subject"})
                return

            vault_subject = os.path.join(VAULT, "subjects", subject)
            raw_dir = os.path.join(vault_subject, "raw")
            ingested = _read_ingested(subject)
            pending = _read_pending_deletes(subject)
            results = {"files_deleted": 0, "deleted_files": []}

            # Step 1: Cascade delete (sync, fast) via shared function
            all_deleted_ids = set()  # node ids (filename without .md)

            for base_name in pending:
                cascade_result = _cascade_delete(subject, base_name, delete_raw=True)
                results["deleted_files"].extend(cascade_result["deleted_files"])
                all_deleted_ids.update(cascade_result["deleted_ids"])
                results["files_deleted"] += 1

            # Step 2: Clear pending, regenerate index (ingested already saved by _cascade_delete)
            _write_pending_deletes(subject, [])
            self._regenerate_index(subject)
            _log_action(subject, "UPDATE_WIKI_DELETE",
                        f"{results['files_deleted']} deleted, starting LLM ingest")

            # Step 3: Count files pending ingest and spawn LLM thread (async)
            # Re-read ingested state (cascade_delete may have modified it)
            ingested = _read_ingested(subject)
            if os.path.isdir(raw_dir):
                uningested = [f for f in os.listdir(raw_dir)
                              if f.endswith(".md") and f != ".ingested.json" and f not in ingested]
            else:
                uningested = []
            global _ingest_total_pending, _ingest_current_subject, _ingest_initial_wiki_count, _ingest_initial_total
            _ingest_total_pending = len(uningested)
            _ingest_initial_total = len(uningested) # save initial total so frontend can compute fraction
            _ingest_current_subject = subject
            # Count existing wiki/ .md files BEFORE ingest — used for live progress tracking
            wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
            if os.path.isdir(wiki_dir):
                _ingest_initial_wiki_count = sum(
                    1 for f in os.listdir(wiki_dir)
                    if f.endswith(".md") and f not in ("index.md", "log.md")
                )
            else:
                _ingest_initial_wiki_count = 0
            _ingest_running = True
            _ingest_result = None
            t = threading.Thread(target=_run_llm_ingest_thread,
                                 args=(subject,), daemon=True)
            t.start()

            self._send_json(202, {
                **results,
                "ingest_started": True,
                "pending_total": len(uningested),
                "message": (f"Deleted {results['files_deleted']} files. LLM ingest running in background...")
            })
        except Exception as e:
            _ingest_running = False
            _ingest_total_pending = 0
            import logging
            logging.exception("_api_update_wiki unhandled error")
            self._send_json(500, {"error": "internal", "detail": "Internal server error"})

    # ── Routing ──

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            params = urllib.parse.parse_qs(parsed.query)

            if path == "/":
                self._send_file(os.path.join(STUDY_DIR, "index.html"), "text/html; charset=utf-8", cache_control="no-cache, no-store, must-revalidate")
            elif path == "/api/health":
                self._send_json(200, {"status": "ok", "vault": VAULT})
            elif path == "/api/subjects":
                self._api_subjects()
            elif path == "/api/files":
                self._api_files(params)
            elif path == "/api/file-content":
                self._api_file_content(params)
            elif path == "/api/objects":
                self._api_objects(params)
            elif path == "/api/object-content":
                self._api_object_content(params)
            elif path == "/api/graph":
                self._api_graph(params)
            elif path == "/api/lint":
                self._api_lint(params)
            elif path == "/api/regenerate-index":
                self._api_regenerate_index(params)
            elif path == "/api/search":
                self._api_search(params)
            elif path == "/api/status":
                self._api_status()
            elif path == "/api/original":
                self._api_original(params)
            elif path == "/api/pending-state":
                self._api_pending_state(params)
            elif path == "/api/chat-load":
                handle_chat_load(self, params)
            elif path == "/api/model":
                self._send_json(200, {"available_models": AVAILABLE_MODELS, "model": AVAILABLE_MODELS[0]})
            elif path.startswith("/static/"):
                static_path = os.path.join(STUDY_DIR, path.lstrip("/"))
                if path.endswith(".css"):
                    self._send_file(static_path, "text/css; charset=utf-8", cache_control="no-cache, no-store, must-revalidate")
                elif path.endswith(".js"):
                    self._send_file(static_path, "application/javascript; charset=utf-8", cache_control="no-cache, no-store, must-revalidate")
                else:
                    self._send_json(404, {"error": "not_found"})
            else:
                self._send_json(404, {"error": "not_found", "detail": f"Route not found: {path}"})
        except Exception as e:
            import logging
            logging.exception("do_GET unhandled error")
            self._send_json(500, {"error": "internal", "detail": "Internal server error"})

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/api/upload":
                self._api_upload()
            elif path == "/api/delete-file":
                self._api_delete_file()
            elif path == "/api/mark-file":
                self._api_mark_file()
            elif path == "/api/update-wiki":
                self._api_update_wiki()
            elif path == "/api/regenerate-index":
                self._api_regenerate_index(params=None)
            elif path == "/api/chat-start":
                handle_chat_start(self)
            elif path == "/api/chat-stream":
                handle_chat_stream(self)
            elif path == "/api/chat-save":
                handle_chat_save(self)
            elif path == "/api/chat-delete":
                length = int(self.headers.get("Content-Length", 0))
                if length > 0:
                    raw = self.rfile.read(length)
                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError:
                        self._send_json(400, {"error": "Invalid JSON body"})
                        return
                else:
                    self._send_json(400, {"error": "subject is required"})
                    return
                subject = data.get("subject", "")
                if not subject:
                    self._send_json(400, {"error": "subject is required"})
                    return
                deleted = delete_chat_file(subject)
                self._send_json(200, {"deleted": deleted, "subject": subject})
            else:
                self._send_json(405, {"error": "method_not_allowed", "detail": f"POST not allowed on {path}"})
        except Exception as e:
            import logging
            logging.exception("do_POST unhandled error")
            self._send_json(500, {"error": "internal", "detail": "Internal server error"})


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer((HOST, PORT), StudyHandler) as httpd:
        print(f"Study server on {HOST}:{PORT}")
        httpd.serve_forever()
