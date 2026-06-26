"""System route handlers (graph, lint, regenerate-index, themes, static, index)."""

import json
import os
import re
from datetime import datetime, date as _date

from ._base import (
    VAULT, STUDY_DIR, SUBJECT_THEMES, CFG,
    _subject_exists, _resolve_vault_path, _read_node_meta, _parse_relationships,
    _regenerate_index, _log_action,
)


# ─── Handlers ───

def handle_graph(handler, params):
    """GET /api/graph?subject=X"""
    subject = params.get("subject", [None])[0]
    if not subject:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
        return
    if not _subject_exists(subject):
        handler._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
        return
    nodes, edges = _parse_relationships(subject)
    handler._send_json(200, {"subject_filter": subject, "nodes": nodes, "edges": edges})


def handle_lint(handler, params):
    """GET /api/lint?subject=X — orphan, missing frontmatter, stale checks."""
    subject = params.get("subject", [None])[0]
    if not subject:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject parameter is required"})
        return
    if not _subject_exists(subject):
        handler._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
        return

    nodes, edges = _parse_relationships(subject)
    issues = []

    for n in nodes:
        if n["link_count"] == 0:
            issues.append({
                "type": "orphan",
                "severity": "warning",
                "node": n["id"],
                "detail": f"No edges connect to or from '{n['id']}'"
            })

    scan_dirs = []
    wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
    if os.path.isdir(wiki_dir):
        scan_dirs.append(("wiki", wiki_dir))
    for d in ["concepts", "definitions", "formulas", "exercises"]:
        dpath = os.path.join(VAULT, "subjects", subject, d)
        if os.path.isdir(dpath):
            scan_dirs.append((d, dpath))

    for dir_label, dpath in scan_dirs:
        for fname in sorted(os.listdir(dpath)):
            if not fname.endswith(".md") or fname.startswith("."):
                continue
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
    handler._send_json(200, {
        "subject": subject,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "issue_count": len(issues),
        "issues": issues,
    })


def handle_regenerate_index(handler, params):
    """POST /api/regenerate-index — rewrite index.md from filesystem (or GET with ?subject=X)."""
    subject = params.get("subject", [None])[0] if params else None
    if not subject:
        try:
            cl = int(handler.headers.get("Content-Length", 0))
            if cl > 1_000_000:
                handler._send_json(413, {"error": "body_too_large", "detail": "JSON body exceeds 1 MB limit"})
                return
            if cl > 0:
                body = json.loads(handler.rfile.read(cl).decode("utf-8"))
                subject = body.get("subject", "")
        except (ValueError, json.JSONDecodeError):
            pass
    if not subject:
        handler._send_json(400, {"error": "missing_subject", "detail": "subject is required"})
        return
    if not _subject_exists(subject):
        handler._send_json(404, {"error": "subject_not_found", "detail": f"Subject '{subject}' not found"})
        return
    _regenerate_index(subject)
    handler._send_json(200, {"subject": subject, "path": f"subjects/{subject}/index.md", "updated": True})


def handle_themes(handler):
    """GET /api/themes — return SUBJECT_THEMES."""
    handler._send_json(200, {"themes": SUBJECT_THEMES})


def handle_skill(handler, skill_name):
    """GET /skill/<name> — serve skill markdown content."""
    skill_dirs = CFG.get("skill_dirs", []) or [
        os.path.join(VAULT, "..", "chat", "skills"),
        os.path.join(VAULT, "..", "chat", "skills", "study"),
        os.path.expanduser("~/.hermes/skills/study"),
        os.path.expanduser("~/.hermes/skills/creative"),
    ]
    skill_path = None
    for sp in skill_dirs:
        candidate = os.path.join(sp, f"{skill_name}.md")
        if os.path.isfile(candidate):
            skill_path = candidate
            break
        candidate2 = os.path.join(sp, skill_name, "SKILL.md")
        if os.path.isfile(candidate2):
            skill_path = candidate2
            break
    if skill_path is None:
        handler._send_json(404, {"error": "not_found", "detail": f"Skill '{skill_name}' not found"})
        return
    with open(skill_path, "r", encoding="utf-8") as f:
        content = f.read()
    handler.send_response(200)
    handler._set_cors()
    handler.send_header("Content-Type", "text/plain; charset=utf-8")
    handler.send_header("Content-Length", str(len(content.encode("utf-8"))))
    handler.end_headers()
    handler.wfile.write(content.encode("utf-8"))


def handle_static(handler, path):
    """GET /static/..."""
    static_path = os.path.join(STUDY_DIR, path.lstrip("/"))
    if path.endswith(".css"):
        handler._send_file(static_path, "text/css; charset=utf-8", cache_control="no-cache, no-store, must-revalidate")
    elif path.endswith(".js"):
        handler._send_file(static_path, "application/javascript; charset=utf-8", cache_control="no-cache, no-store, must-revalidate")
    else:
        handler._send_json(404, {"error": "not_found"})


def handle_root(handler):
    """GET /"""
    handler._send_file(os.path.join(STUDY_DIR, "index.html"), "text/html; charset=utf-8", cache_control="no-cache, no-store, must-revalidate")