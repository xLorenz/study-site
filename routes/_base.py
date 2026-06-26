"""Shared utilities and state for route modules."""

import colorsys
import email.parser
import email.policy
import json
import os
import re
import shutil
import subprocess
import threading
import unicodedata
import yaml

# Import chat functions after env vars are set
from chat import (
    handle_chat_start,
    handle_chat_stream,
    handle_chat_save,
    handle_chat_load,
    delete_chat_file,
)
from chat.ingest import run_ingest
from chat.types import AVAILABLE_MODELS

# ─── Global state (module-level, mutable) ───

_ingest_running = False
_ingest_result = None
_ingest_total_pending = 0
_ingest_current_subject = None
_ingest_initial_wiki_count = 0
_ingest_initial_total = 0
_ingest_last_created_name = None
_upload_in_progress = False
_ingest_lock = threading.Lock()
_upload_lock = threading.Lock()

# ─── Config/paths loaded by server.py and injected via set_config() ───

STUDY_DIR = ""
VAULT = ""
CACHE_DIR = ""
CFG = {}
NIM_API_KEY = ""
OPENCODE_ZEN_API_KEY = ""
NIM_BASE_URL = ""
HOST = "0.0.0.0"
PORT = 8081



def set_config(
    study_dir: str,
    vault: str,
    cache_dir: str,
    cfg: dict,
    nim_api_key: str,
    opencode_zen_api_key: str,
    nim_base_url: str,
    host: str,
    port: int,
):
    """Inject configuration from server.py."""
    global STUDY_DIR, VAULT, CACHE_DIR, CFG
    global NIM_API_KEY, OPENCODE_ZEN_API_KEY, NIM_BASE_URL, HOST, PORT

    STUDY_DIR = study_dir
    VAULT = vault
    CACHE_DIR = cache_dir
    CFG = cfg
    NIM_API_KEY = nim_api_key
    OPENCODE_ZEN_API_KEY = opencode_zen_api_key
    NIM_BASE_URL = nim_base_url
    HOST = host
    PORT = port


# ─── Vault-based theme helpers ───

def _parse_theme_md(content: str) -> dict:
    """Parse a _theme.md file's key: value lines into a dict."""
    theme = {}
    for line in content.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            k, _, v = line.partition(":")
            theme[k.strip().lower()] = v.strip()
    return theme


def _read_theme_from_vault(subject: str) -> dict:
    """Read subject theme from vault references/_theme.md. Returns dict or empty."""
    theme_path = os.path.join(VAULT, "subjects", subject, "references", "_theme.md")
    if os.path.isfile(theme_path):
        try:
            with open(theme_path, encoding="utf-8") as f:
                return _parse_theme_md(f.read())
        except OSError:
            pass
    return {}


def _build_themes_dict() -> dict:
    """Scan all vault subjects for _theme.md and build a full themes dict."""
    themes = {"_default": {"primary": "#6366f1", "secondary": "#a78bfa", "accent": "#22d3ee", "icon": "\U0001f4da"}}
    subs_dir = os.path.join(VAULT, "subjects")
    if os.path.isdir(subs_dir):
        for name in sorted(os.listdir(subs_dir)):
            if name.startswith("."):
                continue
            if not os.path.isdir(os.path.join(subs_dir, name)):
                continue
            theme = _read_theme_from_vault(name)
            if theme:
                themes[name] = theme
    return themes


def _get_last_theme_primary() -> str:
    """Get the primary color of the last-created subject for color rotation."""
    subs_dir = os.path.join(VAULT, "subjects")
    if not os.path.isdir(subs_dir):
        return "#6366f1"
    subjects = sorted(s for s in os.listdir(subs_dir) if not s.startswith(".") and os.path.isdir(os.path.join(subs_dir, s)))
    if not subjects:
        return "#6366f1"
    theme = _read_theme_from_vault(subjects[-1])
    return theme.get("primary", "#6366f1")


# ─── Shared utilities ───

def _normalize_name(name: str) -> str:
    """Sanitize a subject name: lowercase, spaces→hyphens, strip special chars."""
    name = name.strip().lower()
    name = re.sub(r'\s+', '-', name)
    name = re.sub(r'[^a-z0-9-]', '', name)
    return name.strip('-')


def _hue_rotate_hex(hex_color: str, degrees: int) -> str:
    """Rotate a hex color's hue by N degrees. Returns new hex color."""
    h = hex_color.lstrip('#')
    r, g, b = [int(h[i:i+2], 16) / 255 for i in (0, 2, 4)]
    hsv = colorsys.rgb_to_hsv(r, g, b)
    hue = (hsv[0] + degrees / 360) % 1.0
    r2, g2, b2 = colorsys.hsv_to_rgb(hue, hsv[1], hsv[2])
    return '#{:02x}{:02x}{:02x}'.format(int(r2 * 255), int(g2 * 255), int(b2 * 255))


# ─── Ingest state accessors (for route modules) ───

def get_ingest_state():
    with _ingest_lock:
        return {
            "ingest_running": _ingest_running,
            "pending_total": _ingest_total_pending,
            "initial_total": _ingest_initial_total,
            "wiki_pages_created": 0,
            "last_created_name": _ingest_last_created_name,
            "queue_length": 0,
            "result": _ingest_result,
        }


def set_ingest_running(val: bool):
    global _ingest_running
    with _ingest_lock:
        _ingest_running = val


def set_ingest_result(val: dict):
    global _ingest_result
    with _ingest_lock:
        _ingest_result = val


def set_ingest_current_subject(val: str):
    global _ingest_current_subject
    with _ingest_lock:
        _ingest_current_subject = val


def set_ingest_total_pending(val: int):
    global _ingest_total_pending
    with _ingest_lock:
        _ingest_total_pending = val


def set_ingest_initial_total(val: int):
    global _ingest_initial_total
    with _ingest_lock:
        _ingest_initial_total = val


def set_ingest_initial_wiki_count(val: int):
    global _ingest_initial_wiki_count
    with _ingest_lock:
        _ingest_initial_wiki_count = val


def set_ingest_last_created_name(val: str):
    global _ingest_last_created_name
    with _ingest_lock:
        _ingest_last_created_name = val


def get_upload_in_progress():
    with _upload_lock:
        return _upload_in_progress


def set_upload_in_progress(val: bool):
    global _upload_in_progress
    with _upload_lock:
        _upload_in_progress = val


def try_acquire_upload_lock():
    """Atomic test-and-set for upload lock. Returns True if acquired."""
    global _upload_in_progress
    with _upload_lock:
        if _upload_in_progress:
            return False
        _upload_in_progress = True
        return True


def release_upload_lock():
    global _upload_in_progress
    with _upload_lock:
        _upload_in_progress = False


# ─── Shared path utilities ───

def _vault_rel(abs_path: str) -> str:
    """Return vault-relative path for an absolute path under VAULT."""
    return os.path.relpath(abs_path, VAULT)


def _resolve_vault_path(rel_path: str) -> str | None:
    """Resolve a vault-relative path, checking for traversal."""
    joined = os.path.realpath(os.path.join(VAULT, rel_path))
    vault_real = os.path.realpath(VAULT)
    if not joined.startswith(vault_real + os.sep) and joined != vault_real:
        return None
    return joined


def slugify(text: str) -> str:
    """Slugify a filename: lowercase, normalize unicode, strip special chars, spaces to hyphens."""
    text = unicodedata.normalize('NFD', text.lower().strip())
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'-+', '-', text)
    return text


def run_markitdown(input_path: str, output_path: str) -> tuple[bool, str]:
    """Convert a file to markdown using MarkItDown. Returns (success, stderr)."""
    md_bin = shutil.which("markitdown")
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


def parse_multipart(handler) -> dict:
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


def _subject_exists(subject: str) -> bool:
    """Check if a subject directory exists under vault subjects/."""
    subj_dir = os.path.join(VAULT, "subjects", subject)
    return os.path.isdir(subj_dir)


def _get_originals_set(subject: str) -> set:
    """Build a set of stem names (no ext) from originals/{subject}/."""
    orig_dir = os.path.join(VAULT, "originals", subject)
    if not os.path.isdir(orig_dir):
        return set()
    stems = set()
    for fname in os.listdir(orig_dir):
        if fname.startswith("."):
            continue
        f_no_ext, _ = os.path.splitext(fname)
        stems.add(f_no_ext)
    return stems


def _find_original(subject: str, basename: str) -> str | None:
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


def _has_original(subject: str, basename: str) -> bool:
    """Check if a file with same basename (no ext) exists in originals/{subject}/."""
    return _find_original(subject, basename) is not None


def _read_node_meta(subject: str, node_id: str) -> dict:
    """Read YAML frontmatter metadata for a node from its first matching file.
    Checks wiki/ first (new SCHEMA structure), then legacy dirs as fallback."""
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
                raw = line.split(":", 1)[1].strip().strip("\"'")
                if "," in raw:
                    raw = raw.split(",")[0].strip()
                meta["source_url"] = raw
        return meta
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
                raw = line.split(":", 1)[1].strip().strip("\"'")
                if "," in raw:
                    raw = raw.split(",")[0].strip()
                meta["source_url"] = raw
        return meta
    return {"type": "note", "created": None, "tags": [], "source_url": None, "title": None}


def tag_color(tag: str) -> str:
    """Deterministic HSL color from tag string. Returns #RRGGBB."""
    h = sum(ord(c) * (i + 1) for i, c in enumerate(tag.lower())) % 360
    s, l = 65, 55
    c = (1 - abs(2 * l / 100 - 1)) * s / 100
    x = c * (1 - abs((h / 60) % 2 - 1))
    m = l / 100 - c / 2
    if h < 60:
        r, g, b = c, x, 0
    elif h < 120:
        r, g, b = x, c, 0
    elif h < 180:
        r, g, b = 0, c, x
    elif h < 240:
        r, g, b = 0, x, c
    elif h < 300:
        r, g, b = x, 0, c
    else:
        r, g, b = c, 0, x
    return '#{:02x}{:02x}{:02x}'.format(
        int((r + m) * 255), int((g + m) * 255), int((b + m) * 255)
    )


def _object_meta_path(subject: str, filename: str) -> str:
    obj_dir = os.path.join(VAULT, "objects", subject)
    return os.path.join(obj_dir, f"{filename}.meta.json")


def _read_object_meta(subject: str, filename: str) -> dict:
    meta_path = _object_meta_path(subject, filename)
    if not os.path.isfile(meta_path):
        return {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_object_meta(subject: str, filename: str, tag: str) -> None:
    meta_path = _object_meta_path(subject, filename)
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    from datetime import datetime, timezone
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "created": datetime.now(timezone.utc).isoformat()}, f)


def _ensure_object_meta(subject: str, filename: str) -> str:
    """Ensure .meta.json exists, creating from legacy inference if needed. Returns tag."""
    meta = _read_object_meta(subject, filename)
    if meta.get("tag"):
        return meta["tag"]
    legacy_type = _infer_object_type(filename)
    tag = legacy_type if legacy_type != "unknown" else "note"
    _write_object_meta(subject, filename, tag)
    return tag


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _log_action(subject, action, detail):
    from datetime import datetime
    log_path = os.path.join(VAULT, "log.md")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"- {ts} | {action} | {subject} | {detail}\n")


def _read_ingested(subject):
    ipath = os.path.join(VAULT, "subjects", subject, "raw", ".ingested.json")
    if not os.path.isfile(ipath):
        return set()
    try:
        with open(ipath, encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("ingested", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _write_ingested(subject, ingested):
    from datetime import datetime
    ipath = os.path.join(VAULT, "subjects", subject, "raw", ".ingested.json")
    os.makedirs(os.path.dirname(ipath), exist_ok=True)
    with open(ipath, "w", encoding="utf-8") as f:
        json.dump({"ingested": sorted(ingested), "last_ingested": datetime.now().isoformat()}, f, indent=1)


def _read_pending_deletes(subject):
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
    ppath = os.path.join(VAULT, "subjects", subject, "raw", "pending.json")
    os.makedirs(os.path.dirname(ppath), exist_ok=True)
    with open(ppath, "w", encoding="utf-8") as f:
        json.dump({"pending_deletes": deletes}, f, indent=1)


def _get_remaining_ingest(subject):
    raw_dir = os.path.join(VAULT, "subjects", subject, "raw")
    if not os.path.isdir(raw_dir):
        return []
    ingested = _read_ingested(subject)
    return [
        f for f in sorted(os.listdir(raw_dir))
        if f.endswith(".md") and f != ".ingested.json" and f not in ingested
    ]


def _extract_sections(content):
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
    defs = []
    for line in text.splitlines():
        stripped = line.strip().lstrip("- ")
        m = re.match(r'\*\*(.+?)\*\*\s*[:：]\s*(.+)', stripped)
        if m:
            defs.append(f"- **{m.group(1)}**: {m.group(2)}")
    return defs


def _extract_code_blocks(content):
    blocks = []
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].startswith("```"):
            lang = lines[i][3:].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("`"):
                code.append(lines[i])
                i += 1
            if code:
                blocks.append((lang, "\n".join(code)))
        i += 1
    return blocks


def _extract_wikilinks_from_body(body):
    seen = set()
    result = []
    for m in re.finditer(r'\[\[([^\]]+)\]\]', body):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _enrich_wikilinks(subject, body):
    wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
    if not os.path.isdir(wiki_dir):
        return body
    node_names = set()
    for fname in os.listdir(wiki_dir):
        if not fname.endswith(".md") or fname in ("index.md", "log.md", ".ingested.json"):
            continue
        node_names.add(fname[:-3])
    if not node_names:
        return body
    sorted_names = sorted(node_names, key=lambda n: (-len(n), n))
    WIKILINK_RE = re.compile(r'\[\[([^\]]+)\]\]')
    FENCED_RE = re.compile(r'`[\s\S]*?`')
    INLINE_RE = re.compile(r'[^\n]+')
    HEADING_RE = re.compile(r'^#{1,6}\s.*$', re.MULTILINE)
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
    for name in sorted_names:
        if len(name) < 3:
            continue
        escaped = re.escape(name)
        pattern = re.compile(r'(?<![\[/\w])' + escaped + r'(?![\]/\w])', re.IGNORECASE)
        masked = pattern.sub(lambda m, n=name: f"[[{n}]]", masked)
    for ph, original in placeholders:
        masked = masked.replace(ph, original)
    return masked


def _auto_create_pages(subject, base_name):
    from datetime import datetime
    raw_path = os.path.join(VAULT, "subjects", subject, "raw", f"{base_name}.md")
    if not os.path.isfile(raw_path):
        return {"created": 0}
    with open(raw_path, encoding="utf-8") as f:
        content = f.read()
    sections = _extract_sections(content)
    today = datetime.now().strftime("%Y-%m-%d")
    created = 0
    parts = []
    intro = sections.get("__intro__", "")
    if intro:
        non_heading = [l for l in intro.splitlines() if not l.startswith("# ")]
        if non_heading:
            parts.append("\n".join(non_heading))
    for sn in ("Concepto", "Concept", "Definición", "Definicion", "Definition"):
        if sn in sections:
            parts.append(f"## {sn}\n\n{sections[sn]}")
    all_defs = []
    for sectext in sections.values():
        all_defs.extend(_extract_definitions_from_text(sectext))
    if all_defs:
        parts.append("## Key Terms\n\n" + "\n".join(all_defs))
    blocks = _extract_code_blocks(content)
    if blocks:
        code_parts = []
        for lang, code in blocks:
            label = f"Ejemplo en {lang}" if lang else "Ejemplo"
            code_parts.append(f"**{label}:**\n\n`{lang}\n{code}\n`")
        parts.append("## Examples / Formulas\n\n" + "\n\n".join(code_parts))
    for sn in ("Ejercicios", "Exercises", "Practice", "Problemas", "Problema"):
        if sn in sections:
            parts.append(f"## {sn}\n\n{sections[sn]}")
            break
    if parts:
        body = "\n\n---\n\n".join(parts)
        body = _enrich_wikilinks(subject, body)
        related = _extract_wikilinks_from_body(body)
        if related:
            body += "\n\n## Related concepts\n" + "".join(f"- [[{c}]]\n" for c in related)
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
    wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
    os.makedirs(wiki_dir, exist_ok=True)
    fpath = os.path.join(wiki_dir, f"{base_name}.md")
    if os.path.isfile(fpath):
        return False
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def _cascade_delete(subject, base_name, delete_raw=True):
    result = {
        "deleted_files": [],
        "deleted_ids": set(),
        "ingested_updated": False,
    }
    subj_dir = os.path.join(VAULT, "subjects", subject)
    source_tag = f"raw/{base_name}.md"
    ingested = _read_ingested(subject)
    raw_path = os.path.join(subj_dir, "raw", f"{base_name}.md")
    if delete_raw and os.path.isfile(raw_path):
        os.remove(raw_path)
        result["deleted_files"].append(f"subjects/{subject}/raw/{base_name}.md")
    for wtype in ("concepts", "definitions", "formulas", "exercises", "wiki"):
        wdir = os.path.join(subj_dir, wtype)
        if not os.path.isdir(wdir):
            continue
        for wf in list(os.listdir(wdir)):
            if not wf.endswith(".md"):
                continue
            if wtype == "wiki" and wf in ("index.md", "log.md"):
                continue
            wf_path = os.path.join(wdir, wf)
            if wf == f"{base_name}.md":
                os.remove(wf_path)
                result["deleted_files"].append(f"{wtype}/{wf}")
                result["deleted_ids"].add(base_name)
                continue
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
                                derived_id = wf[:-3]
                                result["deleted_files"].append(f"{wtype}/{wf}")
                                result["deleted_ids"].add(derived_id)
                                break
            except Exception:
                pass
    orig_dir = os.path.join(VAULT, "originals", subject)
    if os.path.isdir(orig_dir):
        for f in os.listdir(orig_dir):
            if f.startswith(base_name + ".") or f == base_name:
                os.remove(os.path.join(orig_dir, f))
                result["deleted_files"].append(f"originals/{subject}/{f}")
    obj_dir = os.path.join(VAULT, "objects", subject)
    if os.path.isdir(obj_dir):
        for f in os.listdir(obj_dir):
            if f == f"{base_name}.html" or f.startswith(f"{base_name}-"):
                fp = os.path.join(obj_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
                    result["deleted_files"].append(f"objects/{subject}/{f}")
    fname = f"{base_name}.md"
    if fname in ingested:
        ingested.discard(fname)
        _write_ingested(subject, ingested)
        result["ingested_updated"] = True
    return result


def _list_entries(abs_dir, vault_prefix, subject, originals_set=None):
    entries = []
    try:
        names = sorted(os.listdir(abs_dir))
    except OSError:
        return entries
    for name in names:
        if name.startswith("."):
            continue
        abs_path = os.path.join(abs_dir, name)
        rel_path = os.path.join(vault_prefix, name).replace("\\", "/")
        entry = {"name": name, "path": rel_path}
        if os.path.isdir(abs_path):
            entry["type"] = "dir"
            entry["children"] = _list_entries(abs_path, rel_path, subject, originals_set)
        else:
            entry["type"] = "file"
            if originals_set:
                name_no_ext, _ = os.path.splitext(name)
                entry["has_original"] = name_no_ext in originals_set
            else:
                orig_filename = _find_original(subject, name)
                entry["has_original"] = orig_filename is not None
        entries.append(entry)
    return entries


def _count_md_files(subject):
    subj_dir = os.path.join(VAULT, "subjects", subject)
    count = 0
    for root, dirs, files in os.walk(subj_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if fname.startswith("."):
                continue
            if fname.endswith(".md"):
                count += 1
    return count


def _count_objects(subject):
    obj_dir = os.path.join(VAULT, "objects", subject)
    if not os.path.isdir(obj_dir):
        return 0
    return sum(1 for f in os.listdir(obj_dir) if f.endswith(".html") and not f.startswith("."))


def _infer_object_type(filename):
    """Legacy inference for objects without metadata. Returns type string."""
    OBJECT_TYPE_PREFIXES = {
        "mock-": "mock",
        "cheat-": "cheat",
        "mindmap-": "mindmap",
        "formula-": "formula",
        "flash-": "flash",
        "parcial-": "exam",
    }
    OBJECT_TYPE_KEYWORDS = {
        "examen": "mock", "practica": "mock",
        "summary": "cheat", "mapa": "mindmap",
        "concept": "cheat", "calculus": "formula",
        "flashcard": "flash", "card": "flash",
    }
    for prefix, obj_type in OBJECT_TYPE_PREFIXES.items():
        if filename.startswith(prefix):
            return obj_type
    lower = filename.lower()
    for keyword, obj_type in OBJECT_TYPE_KEYWORDS.items():
        if keyword in lower:
            return obj_type
    return "unknown"


def _regenerate_index(subject):
    subj_dir = os.path.join(VAULT, "subjects", subject)
    lines = [f"# {subject.title()} — Index", ""]
    lines.append("## Raw Materials")
    raw_dir = os.path.join(subj_dir, "raw")
    if os.path.isdir(raw_dir):
        for fname in sorted(os.listdir(raw_dir)):
            if not fname.endswith(".md") or fname.startswith("."):
                continue
            lines.append(f"- {fname}")
    lines.append("")
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


def _parse_relationships(subject):
    subj_dir = os.path.join(VAULT, "subjects", subject)
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
    node_map = {}
    raw_dir = os.path.join(subj_dir, "raw")
    wiki_dir2 = os.path.join(subj_dir, "wiki")
    wiki_names = set()
    if os.path.isdir(wiki_dir2):
        for f in os.listdir(wiki_dir2):
            if f.endswith(".md") and f not in ("index.md", "log.md"):
                wiki_names.add(f[:-3])
    if os.path.isdir(raw_dir):
        raw_basenames = set()
        for f in os.listdir(raw_dir):
            if f.endswith(".md") and f not in (".ingested.json",):
                raw_basenames.add(f[:-3])
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
    alias_map = {}
    for node_id in sorted(name_counts):
        meta = node_map[node_id]
        if meta.get("aliases"):
            for alias in meta["aliases"]:
                alias_map[alias.lower()] = node_id
            continue
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
                    pass
            lines2 = text[4:end].splitlines()
            for i, l in enumerate(lines2):
                if l.strip().lower().startswith("aliases:"):
                    j = i + 1
                    while j < len(lines2) and lines2[j].strip().startswith("- "):
                        alias_map[lines2[j].strip()[2:].strip().strip("\"'").lower()] = node_id
                        j += 1
            break
    WIKILINK_RE2 = re.compile(r'\[\[([^\]]+)\]\]')
    FENCED_RE2 = re.compile(r'`[\s\S]*?`')
    COMMENT_RE2 = re.compile(r'%%[\s\S]*?%%')
    FRONTMATTER_RE2 = re.compile(r'^---[ \t]*\r?\n[\s\S]*?\r?\n---[ \t]*(\r?\n|$)')
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
        return None
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
                with open(fpath, encoding="utf-8") as _f:
                    raw = _f.read()
            except OSError:
                continue
            body = FRONTMATTER_RE2.sub("", raw)
            body = FENCED_RE2.sub("", body)
            body = COMMENT_RE2.sub("", body)
            for m in WIKILINK_RE2.finditer(body):
                link_part = m.group(1).split("|")[0]
                target = link_part.split("#")[0].strip()
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
    for node in nodes:
        node["link_count"] = sum(
            1 for e in edges
            if e["target"] == node["id"] or e["source"] == node["id"]
        )
        if node["id"] in backlink_map:
            node["backlinks"] = sorted(backlink_map[node["id"]])
    return nodes, edges
