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
import urllib.parse

VAULT = os.path.expanduser("~/study-vault")
STUDY_DIR = os.path.expanduser("~/study")
PORT = 8081

with open(os.path.join(STUDY_DIR, "subject_themes.json")) as f:
    SUBJECT_THEMES = json.load(f)


def _vault_rel(abs_path):
    """Return vault-relative path for an absolute path under VAULT."""
    return os.path.relpath(abs_path, VAULT)


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


def _has_original(subject, basename):
    """Check if a file with same basename (no ext) exists in originals/{subject}/."""
    name_no_ext, _ = os.path.splitext(basename)
    orig_dir = os.path.join(VAULT, "originals", subject)
    if not os.path.isdir(orig_dir):
        return False
    for fname in os.listdir(orig_dir):
        if fname.startswith("."):
            continue
        f_no_ext, _ = os.path.splitext(fname)
        if f_no_ext == name_no_ext:
            return True
    return False


def _parse_relationships(subject):
    """Parse a subject's relationships.md into nodes + edges list."""
    path = os.path.join(VAULT, "subjects", subject, "relationships.md")
    if not os.path.isfile(path):
        return [], []

    with open(path, encoding="utf-8") as f:
        text = f.read()

    nodes = []
    edges = []
    current_section = None
    edge_re = re.compile(r'^\s*-\s*(.+?)\s*[→➡]\s*(.+?)\s*$')
    node_re = re.compile(r'^\s*-\s*(.+?)\s*$')

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## nodes"):
            current_section = "nodes"
            continue
        elif stripped.lower().startswith("## edges"):
            current_section = "edges"
            continue
        elif stripped.startswith("#"):
            current_section = None
            continue

        if current_section == "edges":
            m = edge_re.match(stripped)
            if m:
                edges.append({"source": m.group(1).strip(), "target": m.group(2).strip()})
        elif current_section == "nodes":
            m = node_re.match(stripped)
            if m:
                node_id = m.group(1).strip()
                # Count inbound edges for link_count
                link_count = sum(1 for e in edges if e["target"] == node_id)
                nodes.append({"id": node_id, "label": node_id, "subject": subject, "link_count": link_count})

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
            entry["has_original"] = _has_original(subject, name)

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

    def _api_upload(self):
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

        self._send_json(200, {
            "markdown_path": f"subjects/{subject}/raw/{md_filename}",
            "original_path": f"originals/{subject}/{orig_filename}",
            "filename": filename,
            "conversion": "success",
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
            elif path == "/api/search":
                self._api_search(params)
            elif path == "/api/original":
                self._api_original(params)
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
            else:
                self._send_json(405, {"error": "method_not_allowed", "detail": f"POST not allowed on {path}"})
        except Exception as e:
            self._send_json(500, {"error": "internal", "detail": str(e)})


if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), StudyHandler) as httpd:
        print(f"Study server on :{PORT}")
        httpd.serve_forever()
