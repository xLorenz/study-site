"""Files route handlers."""

import json
import os

from ._base import (
    VAULT, STUDY_DIR, THEME_PALETTE,
    _subject_exists, _resolve_vault_path, _find_original, _has_original,
    _list_entries, _get_originals_set, _count_md_files, _count_objects, _infer_object_type,
    _ensure_object_meta, slugify, run_markitdown, parse_multipart,
    _read_ingested, _read_pending_deletes, _write_pending_deletes,
    _cascade_delete, _regenerate_index, _log_action,
    _read_theme_from_vault,
    try_acquire_upload_lock, release_upload_lock,
    get_ingest_state, set_ingest_running,
)


# ─── Handlers ───

def handle_subjects(handler):
    """GET /api/subjects"""
    subs_dir = os.path.join(VAULT, "subjects")
    subjects = []

    if os.path.isdir(subs_dir):
        for name in sorted(os.listdir(subs_dir)):
            if name.startswith("."):
                continue
            if not os.path.isdir(os.path.join(subs_dir, name)):
                continue
            theme = _read_theme_from_vault(name) or (dict(THEME_PALETTE[0]) if THEME_PALETTE else {"primary": "#6b7db3", "secondary": "#8fa4cc", "accent": "#aec0de", "icon": "\U0001f4da"})
            subjects.append({
                "name": name,
                "theme": theme,
                "file_count": _count_md_files(name),
                "object_count": _count_objects(name),
            })

    handler._send_json(200, {"subjects": subjects})


def handle_files(handler, params):
    """GET /api/files?subject=X&path=Y"""
    subject = params.get("subject", [None])[0]
    if not subject:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
        return

    if not _subject_exists(subject):
        handler._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
        return

    rel_path = params.get("path", [f"subjects/{subject}"])[0]
    abs_path = _resolve_vault_path(rel_path)
    if abs_path is None:
        handler._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
        return

    subj_prefix = os.path.join("subjects", subject)
    subj_abs = os.path.normpath(os.path.join(VAULT, subj_prefix))
    if not os.path.abspath(abs_path).startswith(subj_abs + os.sep) and abs_path != subj_abs:
        handler._send_json(403, {"error": "path_traversal", "detail": "Path is outside the requested subject"})
        return

    if not os.path.exists(abs_path):
        handler._send_json(404, {"error": "path_not_found", "detail": f"Path not found: {rel_path}"})
        return

    if not os.path.isdir(abs_path):
        handler._send_json(400, {"error": "not_a_directory", "detail": "Path is not a directory"})
        return

    originals_set = _get_originals_set(subject)
    entries = _list_entries(abs_path, rel_path, subject, originals_set)
    handler._send_json(200, {"path": rel_path, "entries": entries})


def handle_file_content(handler, params):
    """GET /api/file-content?path=X"""
    rel_path = params.get("path", [None])[0]
    if not rel_path:
        handler._send_json(400, {"error": "missing_path", "detail": "path parameter is required"})
        return

    abs_path = _resolve_vault_path(rel_path)
    if abs_path is None:
        handler._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
        return

    if not rel_path.endswith(".md"):
        handler._send_json(400, {"error": "not_a_markdown_file", "detail": "Only .md files can be served"})
        return

    if not os.path.isfile(abs_path):
        handler._send_json(404, {"error": "file_not_found", "detail": f"File not found: {rel_path}"})
        return

    with open(abs_path, encoding="utf-8") as f:
        content = f.read()

    parts = rel_path.split("/")
    subject = parts[1] if len(parts) >= 2 and parts[0] == "subjects" else None

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

    handler._send_json(200, {
        "path": rel_path,
        "content": content,
        "has_original": has_original,
        "original_path": original_path,
    })


def handle_objects(handler, params):
    """GET /api/objects?subject=X"""
    subject = params.get("subject", [None])[0]
    if not subject:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
        return

    obj_dir = os.path.join(VAULT, "objects", subject)
    objects = []
    if os.path.isdir(obj_dir):
        for fname in os.listdir(obj_dir):
            if fname.startswith(".") or not fname.endswith(".html"):
                continue
            if fname.endswith(".meta.json"):
                continue
            fpath = os.path.join(obj_dir, fname)
            size = os.path.getsize(fpath)
            mtime = os.path.getmtime(fpath)
            tag = _ensure_object_meta(subject, fname)
            objects.append({
                "name": fname,
                "tag": tag,
                "path": f"objects/{subject}/{fname}",
                "size_bytes": size,
                "mtime": mtime,
            })
        objects.sort(key=lambda o: o["mtime"], reverse=True)
        for o in objects:
            del o["mtime"]

    handler._send_json(200, {"subject": subject, "objects": objects})


def handle_object_content(handler, params):
    """GET /api/object-content?path=X"""
    rel_path = params.get("path", [None])[0]
    if not rel_path:
        handler._send_json(400, {"error": "missing_path", "detail": "path parameter is required"})
        return

    abs_path = _resolve_vault_path(rel_path)
    if abs_path is None:
        handler._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
        return

    if not rel_path.endswith(".html"):
        handler._send_json(400, {"error": "not_an_html_file", "detail": "Only .html files can be served as objects"})
        return

    if not os.path.isfile(abs_path):
        handler._send_json(404, {"error": "file_not_found", "detail": f"File not found: {rel_path}"})
        return

    handler._send_file(abs_path, "text/html; charset=utf-8")


def handle_delete_object(handler):
    """POST /api/delete-object — delete a study object (.html + .meta.json)."""
    try:
        cl = int(handler.headers.get("Content-Length", 0))
        if cl > 1_000_000:
            handler._send_json(413, {"error": "body_too_large", "detail": "JSON body exceeds 1 MB limit"})
            return
        body = json.loads(handler.rfile.read(cl).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        handler._send_json(400, {"error": "invalid_body", "detail": "Expected JSON body"})
        return

    rel_path = body.get("path", "")
    if not rel_path:
        handler._send_json(400, {"error": "missing_path", "detail": "path is required"})
        return

    abs_path = _resolve_vault_path(rel_path)
    if abs_path is None:
        handler._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
        return

    parts = rel_path.split("/")
    if len(parts) < 3 or parts[0] != "objects":
        handler._send_json(403, {"error": "forbidden", "detail": "Only objects/ paths can be deleted"})
        return

    if not rel_path.endswith(".html"):
        handler._send_json(400, {"error": "not_an_html_file", "detail": "Only .html files can be deleted"})
        return

    if not os.path.isfile(abs_path):
        handler._send_json(404, {"error": "not_found", "detail": "Object file not found"})
        return

    subject = parts[1]
    filename = os.path.basename(rel_path)

    os.remove(abs_path)
    deleted = [f"objects/{subject}/{filename}"]

    meta_path = abs_path + ".meta.json"
    if os.path.isfile(meta_path):
        os.remove(meta_path)
        deleted.append(f"objects/{subject}/{filename}.meta.json")

    _log_action(subject, "DELETE_OBJECT", filename)

    handler._send_json(200, {"subject": subject, "filename": filename, "deleted": deleted})


def handle_upload(handler):
    """POST /api/upload — multipart upload with MarkItDown conversion + auto-ingest."""
    if not try_acquire_upload_lock():
        handler._send_json(503, {"error": "busy", "detail": "Another operation in progress, try again shortly"})
        return

    try:
        _do_upload(handler)
    finally:
        release_upload_lock()


def _do_upload(handler):
    """POST /api/upload — multipart upload with MarkItDown conversion."""
    cl_str = handler.headers.get("Content-Length", "0")
    content_length = int(cl_str) if cl_str.isdigit() else 0
    if content_length > 52428800:
        handler._send_json(413, {"error": "file_too_large", "detail": "File exceeds 50 MB limit"})
        return

    ct = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in ct:
        handler._send_json(400, {"error": "invalid_content_type", "detail": "Expected multipart/form-data"})
        return

    parts = parse_multipart(handler)

    subject = parts.get("subject", "")
    if not subject:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject field is required"})
        return

    if not _subject_exists(subject):
        handler._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' does not exist"})
        return

    file_part = parts.get("file")
    if not file_part:
        handler._send_json(400, {"error": "missing_file", "detail": "file field is required"})
        return

    filename = file_part["filename"]
    data = file_part["data"]

    _, ext = os.path.splitext(filename)
    allowed = [".pdf", ".pptx", ".docx", ".xlsx", ".jpg", ".png"]
    if ext.lower() not in allowed:
        handler._send_json(400, {"error": "unsupported_format", "detail": f"Format '{ext}' not supported. Allowed: {', '.join(allowed)}"})
        return

    name_no_ext, _ = os.path.splitext(filename)
    slug_name = slugify(name_no_ext)
    orig_filename = f"{slug_name}{ext}"
    orig_dir = os.path.join(VAULT, "originals", subject)
    os.makedirs(orig_dir, exist_ok=True)
    orig_path = os.path.join(orig_dir, orig_filename)
    with open(orig_path, "wb") as f:
        f.write(data)

    raw_dir = os.path.join(VAULT, "subjects", subject, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    md_filename = f"{slug_name}.md"
    md_path = os.path.join(raw_dir, md_filename)

    success, stderr = run_markitdown(orig_path, md_path)
    if not success:
        os.remove(orig_path)
        handler._send_json(500, {"error": "conversion_failed", "detail": stderr})
        return

    log_path = os.path.join(VAULT, "log.md")
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        safe_name = filename.replace('\n', ' ').replace('\r', ' ').replace('|', ' ')
        with open(log_path, "a", encoding="utf-8") as logf:
            logf.write(f"- {ts} | UPLOAD | {subject} | {safe_name} \u2192 raw/{md_filename}\n")
    except OSError:
        pass

    try:
        _regenerate_index(subject)
    except OSError:
        pass

    handler._send_json(200, {
        "markdown_path": f"subjects/{subject}/raw/{md_filename}",
        "original_path": f"originals/{subject}/{orig_filename}",
        "filename": filename,
        "conversion": "success",
    })


def handle_delete_file(handler):
    """POST /api/delete-file — cascade-delete a file and all its wiki pages/objects/edges."""
    if get_ingest_state()["ingest_running"]:
        handler._send_json(503, {"error": "ingest_in_progress", "detail": "Ingest in progress, try again shortly"})
        return

    set_ingest_running(True)
    try:
        _do_delete_file(handler)
    finally:
        set_ingest_running(False)


def _do_delete_file(handler):
    """Internal delete — called with _ingest_running lock held."""
    try:
        cl = int(handler.headers.get("Content-Length", 0))
        if cl > 1_000_000:
            handler._send_json(413, {"error": "body_too_large", "detail": "JSON body exceeds 1 MB limit"})
            return
        body = json.loads(handler.rfile.read(cl).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        handler._send_json(400, {"error": "invalid_body", "detail": "Expected JSON body"})
        return

    rel_path = body.get("path", "")
    if not rel_path:
        handler._send_json(400, {"error": "missing_path", "detail": "path is required"})
        return

    abs_path = _resolve_vault_path(rel_path)
    if abs_path is None:
        handler._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
        return

    parts = rel_path.split("/")
    if len(parts) < 3 or parts[0] != "subjects" or parts[2] != "raw":
        handler._send_json(403, {"error": "forbidden", "detail": "Only raw/ files can be deleted from the UI"})
        return

    subject = parts[1]
    base_name = os.path.splitext(os.path.basename(rel_path))[0]

    if not os.path.exists(abs_path):
        handler._send_json(404, {"error": "not_found", "detail": "File not found"})
        return
    if not os.path.isfile(abs_path):
        handler._send_json(400, {"error": "not_a_file", "detail": "Path is not a file"})
        return

    cascade_result = _cascade_delete(subject, base_name, delete_raw=True)
    removed = [rel_path] + cascade_result["deleted_files"]
    removed_edges = len(cascade_result["deleted_ids"])

    log_path = os.path.join(VAULT, "log.md")
    try:
        from datetime import datetime
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(log_path, "a", encoding="utf-8") as logf:
            logf.write(f"- {ts} | DELETE | {subject} | {base_name} ({len(removed)} files, {removed_edges} edges removed)\n")
    except OSError:
        pass

    try:
        _regenerate_index(subject)
    except OSError:
        pass

    handler._send_json(200, {
        "subject": subject,
        "base_name": base_name,
        "removed": removed,
        "edges_removed": removed_edges,
        "index_updated": True,
    })


def handle_search(handler, params):
    """GET /api/search?q=X&subject=Y"""
    import unicodedata
    q = params.get("q", [""])[0]
    subject_filter = params.get("subject", [""])[0]

    if len(q) < 2:
        handler._send_json(400, {"error": "query_too_short", "detail": "Query must be at least 2 characters"})
        return

    root = os.path.join(VAULT, "subjects", subject_filter) if subject_filter else os.path.join(VAULT, "subjects")
    if not os.path.isdir(root):
        handler._send_json(200, {"query": q, "subject_filter": subject_filter, "results": []})
        return

    results = []
    q_lower = q.lower()
    q_plain = ''.join(c for c in unicodedata.normalize('NFD', q_lower) if not unicodedata.combining(c))

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

            lines = content.splitlines(keepends=True)
            match_positions = []
            for line_no, line in enumerate(lines, 1):
                line_plain = ''.join(
                    c for c in unicodedata.normalize('NFD', line.lower())
                    if not unicodedata.combining(c))
                if q_plain in line_plain:
                    match_positions.append(line_no)

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
                continue

            start = max(0, idx - 75)
            end = min(len(content), idx + len(q) + 75)
            snippet = content[start:end]
            actual_match = content[idx:idx + len(q)]
            snippet = snippet.replace(actual_match, f"\u00a7\u00a7\u00a7{actual_match}\u00a7\u00a7\u00a7", 1)

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
    handler._send_json(200, {
        "query": q,
        "subject_filter": subject_filter,
        "results": results[:20],
    })


def handle_original(handler, params):
    """GET /api/original?path=X — serve original uploaded file."""
    rel_path = params.get("path", [None])[0]
    if not rel_path:
        handler._send_json(400, {"error": "missing_path", "detail": "path parameter is required"})
        return

    abs_path = _resolve_vault_path(rel_path)
    if abs_path is None:
        handler._send_json(403, {"error": "path_traversal", "detail": "Path traversal detected"})
        return

    if not os.path.isfile(abs_path):
        handler._send_json(404, {"error": "file_not_found", "detail": f"File not found: {rel_path}"})
        return

    _, ext = os.path.splitext(abs_path)
    allowed_exts = {".pdf", ".pptx", ".docx", ".xlsx", ".jpg", ".jpeg", ".png"}
    if ext.lower() not in allowed_exts:
        handler._send_json(403, {"error": "forbidden_format", "detail": f"Format '{ext}' not allowed for download"})
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
    handler.send_response(200)
    handler._set_cors()
    handler.send_header("Content-Type", content_type)
    safe_basename = basename.replace('"', '').replace('\n', '').replace('\r', '')
    handler.send_header("Content-Disposition", f'attachment; filename="{safe_basename}"')
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def handle_pending_state(handler, params):
    """GET /api/pending-state?subject=X — return ingested + pending delete state."""
    subject = params.get("subject", [None])[0]
    if not subject:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject parameter required"})
        return

    ingested = _read_ingested(subject)
    pending = _read_pending_deletes(subject)
    raw_dir = os.path.join(VAULT, "subjects", subject, "raw")
    raw_files = []
    if os.path.isdir(raw_dir):
        for f in sorted(os.listdir(raw_dir)):
            if f.endswith(".md") and f != ".ingested.json":
                raw_files.append(f)

    handler._send_json(200, {
        "ingested": sorted(ingested),
        "pending_deletes": pending,
        "raw_files": raw_files,
    })


def handle_mark_file(handler):
    """POST /api/mark-file — mark/unmark a raw file for deletion."""
    try:
        cl = int(handler.headers.get("Content-Length", 0))
        if cl > 1_000_000:
            handler._send_json(413, {"error": "body_too_large", "detail": "JSON body exceeds 1 MB limit"})
            return
        body = json.loads(handler.rfile.read(cl)) if cl else {}
        rel_path = body.get("path", "")
        action = body.get("action", "")
        subject = body.get("subject", "")
        if not subject or not rel_path or action not in ("delete", "undo"):
            handler._send_json(400, {"error": "missing_fields", "detail": "path, subject, and action (delete/undo) are required"})
            return
        if not _subject_exists(subject):
            handler._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
            return
        base_name = os.path.splitext(os.path.basename(rel_path))[0]
        pending = _read_pending_deletes(subject)
        if action == "delete":
            if base_name not in pending:
                pending.append(base_name)
                _write_pending_deletes(subject, pending)
            handler._send_json(200, {"marked": True, "action": "delete", "base_name": base_name})
        elif action == "undo":
            pending = [p for p in pending if p != base_name]
            _write_pending_deletes(subject, pending)
            handler._send_json(200, {"marked": False, "action": "undo", "base_name": base_name})
    except json.JSONDecodeError:
        handler._send_json(400, {"error": "invalid_json"})