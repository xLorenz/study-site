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
import urllib.parse
import yaml

VAULT = os.path.expanduser("~/study-vault")
STUDY_DIR = os.path.expanduser("~/study")
PORT = 8081

# Ingest state (single-threaded server, so no threading lock needed)
_ingest_running = False
_ingest_queue = []  # list of tasks waiting for ingest
_ingest_result = None  # last result: {pages_created, files_deleted, tokens_used, model, message, finished_at}
_ingest_total_pending = 0  # total files queued for ingest (set at ingest start)
_ingest_current_subject = None  # subject currently being ingested (used for live progress)

with open(os.path.join(STUDY_DIR, "subject_themes.json")) as f:
    SUBJECT_THEMES = json.load(f)


def _vault_rel(abs_path):
    """Return vault-relative path for an absolute path under VAULT."""
    return os.path.relpath(abs_path, VAULT)


def _last_fallback_model():
    """Return (provider, model) from the last entry in hermes fallback_providers."""
    try:
        cfg_path = os.path.expanduser("~/.hermes/config.yaml")
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        fb = cfg.get("fallback_providers", [])
        if fb:
            last = fb[-1]
            return last.get("provider", ""), last.get("model", "")
    except Exception:
        pass
    # Hardcoded fallback if config unreadable
    return "opencode-zen", "minimax-m3-free"


def _resolve_vault_path(rel_path):
    """Resolve a vault-relative path, checking for traversal."""
    joined = os.path.normpath(os.path.join(VAULT, rel_path))
    if not joined.startswith(VAULT + os.sep) and joined != VAULT:
        return None
    return joined


def slugify(text):
    """Slugify a filename: lowercase, strip special chars, spaces to hyphens."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def run_markitdown(input_path, output_path):
    """Convert a file to markdown using MarkItDown. Returns (success, stderr)."""
    try:
        result = subprocess.run(
            ["markitdown", input_path, "-o", output_path],
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
    """Read YAML frontmatter metadata for a node from its first matching file."""
    wiki_dirs = [("concepts", "concept"), ("definitions", "definition"),
                 ("formulas", "formula"), ("exercises", "exercise")]
    for d, default_type in wiki_dirs:
        fpath = os.path.join(VAULT, "subjects", subject, d, f"{node_id}.md")
        if not os.path.isfile(fpath):
            continue
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        meta = {"type": default_type, "created": None, "tags": []}
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
        return meta
    return {"type": "note", "created": None, "tags": []}


def _parse_relationships(subject):
    """Build graph nodes from vault files + edges from relationships.md."""
    subj_dir = os.path.join(VAULT, "subjects", subject)

    # ── 1. Auto-derive nodes from vault wiki directories ──
    wiki_dirs = ["concepts", "definitions", "formulas", "exercises"]
    name_counts = {}
    node_dirs = {}
    for d in wiki_dirs:
        dpath = os.path.join(subj_dir, d)
        if not os.path.isdir(dpath):
            continue
        for fname in sorted(os.listdir(dpath)):
            if not fname.endswith(".md") or fname.startswith("."):
                continue
            node_id = fname[:-3]
            name_counts[node_id] = name_counts.get(node_id, 0) + 1
            if node_id not in node_dirs and d in ("concepts", "definitions"):
                node_dirs[node_id] = d

    nodes = []
    for node_id in sorted(name_counts):
        meta = _read_node_meta(subject, node_id)
        nodes.append({
            "id": node_id,
            "label": node_id,
            "subject": subject,
            "link_count": 0,
            "type": meta["type"],
            "created": meta["created"],
            "tags": meta["tags"],
            "file_count": name_counts[node_id],
        })

    # ── 2. Parse edges from relationships.md ──
    rel_path = os.path.join(subj_dir, "relationships.md")
    edges = []
    if os.path.isfile(rel_path):
        edge_re = re.compile(r'^\s*-\s*(.+?)\s*[→➡]\s*(.+?)\s*$')

        def strip_note(s):
            return re.sub(r'\s*\([^)]*\)\s*$', '', s).strip()

        with open(rel_path, encoding="utf-8") as f:
            rel_text = f.read()

        in_edges = False
        for line in rel_text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("## edges"):
                in_edges = True
                continue
            elif stripped.startswith("## ") and not stripped.lower().startswith("## edges"):
                in_edges = False
                continue
            if in_edges:
                m = edge_re.match(stripped)
                if m:
                    src = strip_note(m.group(1))
                    tgt = strip_note(m.group(2))
                    # Only add edge if both nodes exist in the vault
                    if src in name_counts and tgt in name_counts:
                        edges.append({"source": src, "target": tgt})

    # ── 3. Compute link_count ──
    for node in nodes:
        node["link_count"] = sum(
            1 for e in edges
            if e["target"] == node["id"] or e["source"] == node["id"]
        )

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

TITLE_SUFFIX_RE = re.compile(r'-v\d+\.html$')


def _infer_object_type(filename):
    for prefix, obj_type in OBJECT_TYPE_PREFIXES.items():
        if filename.startswith(prefix):
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


def _auto_create_pages(subject, base_name):
    """Deterministically create wiki pages from a raw markdown file.
    Skips pages that already exist (preserves LLM-polished content).
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

    # 1. Concept page — intro paragraph + Concept/Concepto sections
    concept_parts = []
    if sections.get("__intro__"):
        non_heading = [l for l in sections["__intro__"].splitlines()
                       if not l.startswith("# ")]
        if non_heading:
            concept_parts.append("\n".join(non_heading))
    for sn in ("Concepto", "Concept", "Definición", "Definicion"):
        if sn in sections:
            concept_parts.append(f"## {sn}\n\n{sections[sn]}")
    if concept_parts:
        text = f"---\ntitle: {base_name}\ntype: concept\ntags: []\ncreated: {today}\n---\n\n" + "\n\n".join(concept_parts)
        if _write_page_if_missing(subject, "concepts", base_name, text):
            created += 1

    # 2. Definitions page — all bold-term definitions from every section
    all_defs = []
    for sectext in sections.values():
        all_defs.extend(_extract_definitions_from_text(sectext))
    if all_defs:
        text = f"---\ntitle: {base_name}\ntype: definition\ntags: []\ncreated: {today}\n---\n\n" + "\n".join(all_defs)
        if _write_page_if_missing(subject, "definitions", base_name, text):
            created += 1

    # 3. Formulas page — code blocks
    blocks = _extract_code_blocks(content)
    if blocks:
        parts = []
        for lang, code in blocks:
            label = f"Ejemplo en {lang}" if lang else "Ejemplo"
            parts.append(f"**{label}:**\n\n```{lang}\n{code}\n```")
        text = f"---\ntitle: {base_name}\ntype: formula\ntags: []\ncreated: {today}\n---\n\n" + "\n\n".join(parts)
        if _write_page_if_missing(subject, "formulas", base_name, text):
            created += 1

    # 4. Exercises page — first matching exercise/problema section
    for sn in ("Ejercicios", "Exercises", "Practice", "Problemas", "Problema"):
        if sn in sections:
            text = f"---\ntitle: {base_name}\ntype: exercise\ntags: []\ncreated: {today}\n---\n\n## {sn}\n\n{sections[sn]}"
            if _write_page_if_missing(subject, "exercises", base_name, text):
                created += 1
            break

    return {"created": created}


def _write_page_if_missing(subject, wiki_type, base_name, content):
    """Write a wiki page only if it doesn't already exist."""
    dpath = os.path.join(VAULT, "subjects", subject, wiki_type)
    os.makedirs(dpath, exist_ok=True)
    fpath = os.path.join(dpath, f"{base_name}.md")
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
    """Background thread: spawns `hermes chat -q` to run LLM-powered ingest via study-professor skill.

    The agent reads un-ingested raw files for `subject`, runs the LLM Wiki ingest
    (creates wiki pages, updates .ingested.json, updates relationships.md), then
    writes a result file. This thread waits for the agent to finish, then loads
    the result into `_ingest_result` and clears `_ingest_running`.
    """
    global _ingest_running, _ingest_result, _ingest_current_subject
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
        _log_action(subject, "UPDATE_WIKI_INGEST", "no files to ingest")
        return

    file_list = "\n".join(f"- {f}" for f in uningested)
    prompt = f"""You are the study-professor agent. Run the LLM Wiki ingest for subject '{subject}'.

Un-ingested raw files in ~/study-vault/subjects/{subject}/raw/:
{file_list}

For EACH file above:
1. Read the raw markdown content
2. Extract concepts, definitions, formulas, exercises into SEPARATE wiki pages
3. Write pages to: concepts/, definitions/, formulas/, exercises/ (under ~/study-vault/subjects/{subject}/)
4. Add proper frontmatter to each wiki page: `title`, `type`, `tags`, `created`, `source_url`, `ingested`
5. Update relationships.md with new edges between nodes (use `→` arrow syntax, one edge per line, keep existing edges)
6. After processing each file, add its filename to the `ingested` array in raw/.ingested.json

Follow the conventions in the study-professor and llm-wiki skills you have loaded. Preserve any existing wiki pages — never overwrite or delete files you did not create.

WHEN COMPLETE, write the result file at {result_path} with EXACTLY this JSON (no other text in the file):
{{"pages_created": N, "tokens_used": N, "model": "<provider>/<model>", "status": "complete"}}

- pages_created: total number of new wiki pages you created across all files
- tokens_used: total tokens consumed (input + output) for the ingest
- model: the model identifier (e.g., opencode-zen/minimax-m3-free)
- status: "complete" on success, "error" on failure

Use the terminal, file, and any other tools needed. Be thorough — the wiki pages should be high quality with proper structure, examples, and cross-links."""

    # Resolve the last fallback model for ingestion (cheapest/last resort)
    ingest_provider, ingest_model = _last_fallback_model()

    # Spawn hermes subprocess (one-shot, quiet, yolo for non-interactive tool use)
    try:
        proc = subprocess.run(
            ["hermes", "chat", "-q", prompt,
             "-s", "study-professor,llm-wiki",
             "-Q", # quiet mode (no banner)
             "--yolo", # auto-approve tool use
             "--provider", ingest_provider,
             "-m", ingest_model,
             "--accept-hooks"],
            cwd=os.path.expanduser("~"),
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
        )
        agent_output = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired:
        agent_output = "[timeout] hermes subprocess exceeded 600s"
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
                        (time.time() - 660,)  # within last 11 min (ingest timeout)
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
    _log_action(subject, "UPDATE_WIKI_INGEST",
                f"{pages_created} pages, {tokens_used} tokens, model={model}")


def _now_iso():
    """ISO 8601 timestamp for logging and result records."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class StudyHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for the study server."""

    def log_message(self, format, *args):
        pass  # suppress default access logs

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
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

    def _send_file(self, abs_path, content_type):
        if not os.path.isfile(abs_path):
            self._send_json(404, {"error": "not_found", "detail": "File not found"})
            return
        with open(abs_path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self._set_cors()
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
            for fname in sorted(os.listdir(obj_dir)):
                if fname.startswith(".") or not fname.endswith(".html"):
                    continue
                fpath = os.path.join(obj_dir, fname)
                size = os.path.getsize(fpath)
                objects.append({
                    "name": fname,
                    "path": f"objects/{subject}/{fname}",
                    "type": _infer_object_type(fname),
                    "title": _infer_object_title(fname),
                    "size_bytes": size,
                })

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
        for d in ["concepts", "definitions", "formulas", "exercises"]:
            dpath = os.path.join(VAULT, "subjects", subject, d)
            if not os.path.isdir(dpath):
                continue
            for fname in sorted(os.listdir(dpath)):
                if not fname.endswith(".md") or fname.startswith("."):
                    continue
                fpath = os.path.join(dpath, fname)
                with open(fpath, encoding="utf-8") as f:
                    content = f.read()
                if not content.startswith("---\n"):
                    issues.append({
                        "type": "missing_frontmatter",
                        "severity": "warning",
                        "node": fname[:-3],
                        "detail": f"{d}/{fname} has no YAML frontmatter"
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
        for section, dir_name in [("Raw Materials", "raw"), ("Concepts", "concepts"),
                                    ("Definitions", "definitions"), ("Formulas", "formulas"),
                                    ("Exercises", "exercises")]:
            lines.append(f"## {section}")
            dpath = os.path.join(subj_dir, dir_name)
            if os.path.isdir(dpath):
                for fname in sorted(os.listdir(dpath)):
                    if not fname.endswith(".md") or fname.startswith("."):
                        continue
                    lines.append(f"- {fname}" if dir_name == "raw" else f"- [[{fname[:-3]}]]")
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
        global _ingest_running
        if _ingest_running:
            self._send_json(503, {"error": "ingest_in_progress",
                                  "detail": "Ingest in progress, try again shortly"})
            return
        _ingest_running = True

        try:
            self._do_upload()
        finally:
            _ingest_running = False

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
            with open(log_path, "a") as logf:
                logf.write(f"- {ts} | UPLOAD | {subject} | {filename} → raw/{md_filename}\n")
        except OSError:
            pass  # non-critical

        # 10. Auto-ingest: create wiki pages from the new raw file (skip if exist)
        auto_ingested = 0
        try:
            result = _auto_create_pages(subject, slug)
            auto_ingested = result.get("created", 0)
        except OSError:
            pass  # non-critical

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
            "auto_ingested": auto_ingested,
        })

    def _api_delete_file(self):
        """POST /api/delete-file — cascade-delete a file and all its wiki pages/objects/edges."""
        global _ingest_running
        if _ingest_running:
            self._send_json(503, {"error": "ingest_in_progress",
                                  "detail": "Ingest in progress, try again shortly"})
            return

        try:
            cl = int(self.headers.get("Content-Length", 0))
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

        # — 1. Delete raw file —
        os.remove(abs_path)
        removed = [rel_path]

        # — 2. Delete wiki pages with same base name —
        subj_dir = os.path.join(VAULT, "subjects", subject)
        for wiki_dir in ("concepts", "definitions", "formulas", "exercises"):
            fpath = os.path.join(subj_dir, wiki_dir, f"{base_name}.md")
            if os.path.isfile(fpath):
                os.remove(fpath)
                removed.append(f"subjects/{subject}/{wiki_dir}/{base_name}.md")

        # — 3. Delete original file —
        orig_dir = os.path.join(VAULT, "originals", subject)
        for ext in ("pdf", "pptx", "docx", "xlsx", "jpg", "png"):
            opath = os.path.join(orig_dir, f"{base_name}.{ext}")
            if os.path.isfile(opath):
                os.remove(opath)
                removed.append(f"originals/{subject}/{base_name}.{ext}")
                break

        # — 4. Delete any generated objects referencing this name —
        obj_dir = os.path.join(subj_dir, "objects")
        if os.path.isdir(obj_dir):
            for fname in os.listdir(obj_dir):
                if base_name in fname:
                    opath = os.path.join(obj_dir, fname)
                    if os.path.isfile(opath):
                        os.remove(opath)
                        removed.append(f"subjects/{subject}/objects/{fname}")

        # — 5. Remove edges referencing this node from relationships.md —
        rel_path_file = os.path.join(subj_dir, "relationships.md")
        if os.path.isfile(rel_path_file):
            with open(rel_path_file, encoding="utf-8") as f:
                content = f.read()
            lines = content.splitlines()
            kept = []
            removed_edges = 0
            for line in lines:
                stripped = line.strip()
                # Keep section headers and blank lines
                if stripped.startswith("#") or stripped == "":
                    kept.append(line)
                    continue
                # Only remove edges where source OR target exactly match base_name
                edge_parts = stripped.lstrip("- ").split("→")
                if len(edge_parts) == 2:
                    src = edge_parts[0].strip()
                    tgt = edge_parts[1].strip().split(" ")[0]  # drop parentheticals
                    if src == base_name or tgt == base_name:
                        removed_edges += 1
                        continue
                # Fallback for malformed lines — only remove exact match
                if stripped == base_name or stripped == f"- {base_name}":
                    removed_edges += 1
                    continue
                kept.append(line)
            if removed_edges > 0:
                new_content = "\n".join(kept) + "\n"
                with open(rel_path_file, "w", encoding="utf-8") as f:
                    f.write(new_content)

        # — 6. Log —
        log_path = os.path.join(VAULT, "log.md")
        try:
            from datetime import datetime
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            with open(log_path, "a") as logf:
                logf.write(f"- {ts} | DELETE | {subject} | {base_name} ({len(removed)} files, {removed_edges} edges removed)\n")
        except OSError:
            pass

        # — 7. Regenerate index —
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
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if not fn.endswith(".md") or fn.startswith("."):
                    continue
                path = os.path.join(dirpath, fn)
                try:
                    with open(path, encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                except OSError:
                    continue

                count = content.lower().count(q_lower)
                if count == 0:
                    continue

                idx = content.lower().find(q_lower)
                start = max(0, idx - 75)
                end = min(len(content), idx + 75)
                snippet = content[start:end]

                # Bold the query term in the snippet
                # Use the case from content, not q
                actual_match = content[idx:idx + len(q)]
                snippet = snippet.replace(actual_match, f"**{actual_match}**", 1)

                rel = os.path.relpath(path, VAULT)
                subj = rel.split(os.sep)[1] if rel.startswith("subjects") else ""

                results.append({
                    "path": rel.replace(os.sep, "/"),
                    "subject": subj,
                    "snippet": snippet,
                    "match_count": count,
                })

        results.sort(key=lambda r: r["match_count"], reverse=True)
        self._send_json(200, {
            "query": q,
            "subject_filter": subject_filter,
            "results": results[:20],
        })

    def _api_status(self):
        """GET /api/status — current server state (ingest lock, queue, last result)."""
        global _ingest_running, _ingest_result, _ingest_current_subject, _ingest_total_pending
        # If ingest is running, re-count remaining files live from .ingested.json
        # so the progress bar gets real mid-run feedback (not just initial count).
        if _ingest_running and _ingest_current_subject:
            remaining = len(_get_remaining_ingest(_ingest_current_subject))
            _ingest_total_pending = remaining
        self._send_json(200, {
            "ingest_running": _ingest_running,
            "pending_total": _ingest_total_pending,
            "queue_length": len(_ingest_queue),
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
        self.send_header("Content-Disposition", f'attachment; filename="{basename}"')
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
            body = json.loads(self.rfile.read(cl)) if cl else {}
            rel_path = body.get("path", "")
            action = body.get("action", "")
            subject = body.get("subject", "")
            if not subject or not rel_path:
                self._send_json(400, {"error": "missing_fields", "detail": "path, subject, action required"})
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
        global _ingest_running, _ingest_result, _ingest_current_subject
        if _ingest_running:
            self._send_json(503, {"error": "ingest_in_progress", "detail": "Wait for current operation to finish"})
            return
        try:
            cl = int(self.headers.get("Content-Length", 0))
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

            # Step 1: Cascade delete (sync, fast)
            # Collect ALL deleted node IDs across all pending deletions
            all_deleted_ids = set()  # node ids (filename without .md)

            for base_name in pending:
                source_tag = f"raw/{base_name}.md"
                # Delete the raw file
                delete_path = os.path.join(raw_dir, f"{base_name}.md")
                if os.path.isfile(delete_path):
                    os.remove(delete_path)
                # Delete exact-match wiki pages + scan frontmatter for derived pages
                for wtype in ("concepts", "definitions", "formulas", "exercises"):
                    wdir = os.path.join(vault_subject, wtype)
                    if not os.path.isdir(wdir):
                        continue
                    for wf in list(os.listdir(wdir)):
                        if not wf.endswith(".md"):
                            continue
                        wf_path = os.path.join(wdir, wf)
                        # Delete exact match
                        if wf == f"{base_name}.md":
                            os.remove(wf_path)
                            results["deleted_files"].append(f"{wtype}/{wf}")
                            all_deleted_ids.add(base_name)
                            continue
                        # Delete derived pages via frontmatter source_url
                        try:
                            with open(wf_path, encoding="utf-8") as fh:
                                head = fh.read(1024)
                            if head.startswith("---"):
                                end = head.find("---", 3)
                                if end > 0:
                                    fm = head[3:end]
                                    for fmline in fm.splitlines():
                                        k, _, v = fmline.partition(":")
                                        if k.strip() == "source_url" and v.strip() == source_tag:
                                            os.remove(wf_path)
                                            derived_id = wf[:-3]  # strip .md
                                            results["deleted_files"].append(f"{wtype}/{wf}")
                                            all_deleted_ids.add(derived_id)
                                            break
                        except Exception:
                            pass
                # Delete originals
                orig_dir = os.path.join(VAULT, "originals", subject)
                if os.path.isdir(orig_dir):
                    for f in os.listdir(orig_dir):
                        if f.startswith(base_name + ".") or f == base_name:
                            os.remove(os.path.join(orig_dir, f))
                            results["deleted_files"].append(f"originals/{subject}/{f}")
                # Delete objects (substring match)
                obj_dir = os.path.join(VAULT, "objects", subject)
                if os.path.isdir(obj_dir):
                    for f in os.listdir(obj_dir):
                        if base_name in f:
                            fp = os.path.join(obj_dir, f)
                            if os.path.isfile(fp):
                                os.remove(fp)
                                results["deleted_files"].append(f"objects/{subject}/{f}")
                # Remove from ingested set
                fname = f"{base_name}.md"
                if fname in ingested:
                    ingested.discard(fname)
                results["files_deleted"] += 1

            # Clean relationships.md: remove edges involving ANY deleted node
            if all_deleted_ids:
                rel_path = os.path.join(vault_subject, "relationships.md")
                if os.path.isfile(rel_path):
                    with open(rel_path, encoding="utf-8") as f:
                        content = f.read()
                    lines = content.splitlines()
                    kept = []
                    for line in lines:
                        stripped = line.strip()
                        if stripped.startswith("#") or stripped == "":
                            kept.append(line)
                            continue
                        edge_text = stripped.lstrip("- ").strip()
                        if "→" in edge_text:
                            edge_parts = edge_text.split("→")
                            src = edge_parts[0].strip()
                            tgt = edge_parts[1].strip().split(" ")[0].strip()
                            if src in all_deleted_ids or tgt in all_deleted_ids:
                                continue
                        kept.append(line)
                    with open(rel_path, "w", encoding="utf-8") as f:
                        f.write("\n".join(kept))

            # Step 2: Clear pending, mark deleted ingested, save state
            _write_pending_deletes(subject, [])
            _write_ingested(subject, ingested)
            self._regenerate_index(subject)
            _log_action(subject, "UPDATE_WIKI_DELETE",
                        f"{results['files_deleted']} deleted, starting LLM ingest")

            # Step 3: Count files pending ingest and spawn LLM thread (async)
            if os.path.isdir(raw_dir):
                uningested = [f for f in os.listdir(raw_dir)
                              if f.endswith(".md") and f != ".ingested.json" and f not in ingested]
            else:
                uningested = []
            global _ingest_total_pending, _ingest_current_subject
            _ingest_total_pending = len(uningested)
            _ingest_current_subject = subject
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
            self._send_json(500, {"error": "internal", "detail": str(e)})

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
                self._send_file(os.path.join(STUDY_DIR, "index.html"), "text/html; charset=utf-8")
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
            else:
                self._send_json(404, {"error": "not_found", "detail": f"Route not found: {path}"})
        except Exception as e:
            self._send_json(500, {"error": "internal", "detail": str(e)})

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/api/upload":
                self._api_upload()
            elif path == "/api/delete-file":
                self._api_delete_file()
            elif path == "/api/regenerate-index":
                self._api_regenerate_index({})
            elif path == "/api/mark-file":
                self._api_mark_file()
            elif path == "/api/update-wiki":
                self._api_update_wiki()
            else:
                self._send_json(405, {"error": "method_not_allowed", "detail": f"POST not allowed on {path}"})
        except Exception as e:
            self._send_json(500, {"error": "internal", "detail": str(e)})


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), StudyHandler) as httpd:
        print(f"Study server on :{PORT}")
        httpd.serve_forever()
