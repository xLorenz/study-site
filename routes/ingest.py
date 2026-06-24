"""Ingest route handlers."""

import json
import os
import threading
from datetime import datetime, timezone

from ._base import (
    VAULT, STUDY_DIR,
    get_ingest_state, set_ingest_running, set_ingest_result,
    set_ingest_current_subject, set_ingest_total_pending,
    set_ingest_initial_total, set_ingest_initial_wiki_count,
    set_ingest_last_created_name, get_upload_in_progress, set_upload_in_progress,
    _subject_exists, _log_action, _read_ingested, _read_pending_deletes,
    _write_pending_deletes, _get_remaining_ingest, _cascade_delete, _regenerate_index,
    _now_iso, run_ingest,
)


# ─── Ingest Helpers ───

def _run_llm_ingest_thread(subject: str):
    """Background thread: runs the new chat.ingest.run_ingest() module."""
    def _on_progress(event):
        if event.get("event") == "page_created":
            set_ingest_last_created_name(event.get("filename", "?"))
        elif event.get("event") == "file_ingested":
            _log_action(subject, "INGEST_PAGE",
                        f"file ingested: {event.get('filename', '?')}")

    try:
        result = run_ingest(subject, on_progress=_on_progress)
    except Exception as e:
        result = {
            "pages_created": 0,
            "tokens_used": 0,
            "model": "unknown",
            "status": "error",
            "message": f"Ingest thread crashed: {e}",
            "finished_at": _now_iso(),
        }

    set_ingest_result({
        "pages_created": result.get("pages_created", 0),
        "files_deleted": 0,
        "tokens_used": result.get("tokens_used", 0),
        "model": result.get("model", "unknown"),
        "message": result.get("message", ""),
        "finished_at": result.get("finished_at", _now_iso()),
        "status": result.get("status", "error"),
    })
    set_ingest_running(False)
    set_ingest_current_subject(None)
    set_ingest_total_pending(0)
    _log_action(subject, "UPDATE_WIKI_INGEST",
                f"{result.get('pages_created', 0)} pages, "
                f"{result.get('tokens_used', 0)} tokens, "
                f"model={result.get('model', '?')}, "
                f"status={result.get('status', '?')}")


# ─── Handlers ───

def handle_health(handler):
    """GET /api/health"""
    handler._send_json(200, {"status": "ok", "vault": VAULT})


def handle_status(handler):
    """GET /api/status — current server state (ingest lock, queue, last result)."""
    state = get_ingest_state()
    # If ingest is running, compute live progress from filesystem
    wiki_pages_created = 0
    if state["ingest_running"] and state.get("current_subject"):
        remaining = len(_get_remaining_ingest(state["current_subject"]))
        state["pending_total"] = remaining
        wiki_dir = os.path.join(VAULT, "subjects", state["current_subject"], "wiki")
        if os.path.isdir(wiki_dir):
            current_wiki_count = sum(
                1 for f in os.listdir(wiki_dir)
                if f.endswith(".md") and f not in ("index.md", "log.md")
            )
            wiki_pages_created = max(0, current_wiki_count - state["initial_wiki_count"])
    state["wiki_pages_created"] = wiki_pages_created
    handler._send_json(200, state)


def handle_update_wiki(handler):
    """POST /api/update-wiki — cascade delete sync, LLM ingest async."""
    if get_ingest_state()["ingest_running"]:
        handler._send_json(503, {"error": "ingest_in_progress", "detail": "Wait for current operation to finish"})
        return

    try:
        cl = int(handler.headers.get("Content-Length", 0))
        if cl > 1_000_000:
            handler._send_json(413, {"error": "body_too_large", "detail": "JSON body exceeds 1 MB limit"})
            return
        body = json.loads(handler.rfile.read(cl)) if cl else {}
        subject = body.get("subject", "")
        if not subject:
            handler._send_json(400, {"error": "missing_subject"})
            return

        vault_subject = os.path.join(VAULT, "subjects", subject)
        raw_dir = os.path.join(vault_subject, "raw")
        ingested = _read_ingested(subject)
        pending = _read_pending_deletes(subject)
        results = {"files_deleted": 0, "deleted_files": []}

        # Step 1: Cascade delete (sync, fast) via shared function
        all_deleted_ids = set()

        for base_name in pending:
            cascade_result = _cascade_delete(subject, base_name, delete_raw=True)
            results["deleted_files"].extend(cascade_result["deleted_files"])
            all_deleted_ids.update(cascade_result["deleted_ids"])
            results["files_deleted"] += 1

        # Step 2: Clear pending, regenerate index
        _write_pending_deletes(subject, [])
        _regenerate_index(subject)
        _log_action(subject, "UPDATE_WIKI_DELETE",
                    f"{results['files_deleted']} deleted, starting LLM ingest")

        # Step 3: Count files pending ingest and spawn LLM thread (async)
        ingested = _read_ingested(subject)
        if os.path.isdir(raw_dir):
            uningested = [f for f in os.listdir(raw_dir)
                          if f.endswith(".md") and f != ".ingested.json" and f not in ingested]
        else:
            uningested = []

        set_ingest_total_pending(len(uningested))
        set_ingest_initial_total(len(uningested))
        set_ingest_current_subject(subject)

        wiki_dir = os.path.join(VAULT, "subjects", subject, "wiki")
        if os.path.isdir(wiki_dir):
            set_ingest_initial_wiki_count(sum(
                1 for f in os.listdir(wiki_dir)
                if f.endswith(".md") and f not in ("index.md", "log.md")
            ))
        else:
            set_ingest_initial_wiki_count(0)

        set_ingest_running(True)
        set_ingest_result(None)

        t = threading.Thread(target=_run_llm_ingest_thread, args=(subject,), daemon=True)
        t.start()

        handler._send_json(202, {
            **results,
            "ingest_started": True,
            "pending_total": len(uningested),
            "message": (f"Deleted {results['files_deleted']} files. LLM ingest running in background...")
        })
    except Exception as e:
        set_ingest_running(False)
        set_ingest_total_pending(0)
        import logging
        logging.exception("_api_update_wiki unhandled error")
        handler._send_json(500, {"error": "internal", "detail": "Internal server error"})