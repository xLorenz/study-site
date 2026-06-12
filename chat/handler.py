"""SSE HTTP handlers for the study chat system."""

import json
import time

from . import state
from .types import CHATS_DIR, MAX_BODY_SIZE, AVAILABLE_MODELS


def _read_body(handler):
    """Read request body with size limit."""
    length = int(handler.headers.get("Content-Length", 0))
    if length > MAX_BODY_SIZE:
        return None, 413
    return handler.rfile.read(length), 200


def handle_chat_start(handler):
    """POST /api/chat-start — Start background LLM task, return task_id immediately."""
    raw, status = _read_body(handler)
    if status != 200:
        handler._send_json(status, {"error": "Request too large"})
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        handler._send_json(400, {"error": "Invalid JSON body"})
        return

    subject = data.get("subject", "")
    message = data.get("message", "")
    conversation = data.get("conversation", [])
    model = data.get("model", AVAILABLE_MODELS[0])

    if not subject or not message:
        handler._send_json(400, {"error": "subject and message are required"})
        return

    task_id = state.start_background_task(subject, message, conversation, model)
    handler._send_json(200, {"task_id": task_id})


def handle_chat_stream(handler):
    """POST /api/chat-stream — SSE stream from existing background task."""
    raw, status = _read_body(handler)
    if status != 200:
        handler._send_json(status, {"error": "Request too large"})
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        handler._send_json(400, {"error": "Invalid JSON body"})
        return

    task_id = data.get("task_id", "")
    task = state.get_task(task_id)
    if not task:
        handler._send_json(404, {"error": f"Task {task_id} not found"})
        return

    # SSE response
    handler.send_response(200)
    handler._set_cors()
    handler.send_header("Content-Type", "text/event-stream")
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Connection", "close")
    handler.send_header("X-Accel-Buffering", "no")
    handler.end_headers()

    try:
        while True:
            try:
                event = task.buffer.get(timeout=15)
            except Exception:
                # Queue empty for 15s — send keepalive comment
                try:
                    handler.wfile.write(b": keepalive\n\n")
                    handler.wfile.flush()
                except Exception:
                    pass
                continue
            if event["type"] == "_task_done":
                break

            data_line = json.dumps(event, ensure_ascii=False)
            handler.wfile.write(f"data: {data_line}\n\n".encode("utf-8"))
            handler.wfile.flush()

            if event["type"] in ("done", "error"):
                break
    except BrokenPipeError:
        pass
    except Exception as e:
        try:
            handler.wfile.write(f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n".encode("utf-8"))
            handler.wfile.flush()
        except Exception:
            pass


def handle_chat_save(handler):
    """POST /api/chat-save — Manual save (fallback)."""
    raw, status = _read_body(handler)
    if status != 200:
        handler._send_json(status, {"error": "Request too large"})
        return
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        handler._send_json(400, {"error": "Invalid JSON body"})
        return

    subject = data.get("subject", "")
    messages = data.get("messages", [])
    if not subject:
        handler._send_json(400, {"error": "subject is required"})
        return

    state.save_chat(subject, messages)
    handler._send_json(200, {"status": "ok"})


def handle_chat_load(handler, params):
    """GET /api/chat-load?subject=X — Load chat history."""
    subject_list = params.get("subject", [])
    if not subject_list:
        handler._send_json(400, {"error": "subject query parameter is required"})
        return
    subject = subject_list[0]
    messages = state.load_chat(subject)
    handler._send_json(200, {"messages": messages})
