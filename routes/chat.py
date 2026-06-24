"""Chat route handlers."""

import json
import os

from ._base import (
    VAULT, STUDY_DIR,
    _subject_exists,
    handle_chat_start, handle_chat_stream, handle_chat_save, handle_chat_load, delete_chat_file,
    AVAILABLE_MODELS,
)


def handle_model(handler):
    """GET /api/model"""
    handler._send_json(200, {"available_models": AVAILABLE_MODELS, "model": AVAILABLE_MODELS[0]})


def handle_chat_start_route(handler):
    """POST /api/chat-start"""
    handle_chat_start(handler)


def handle_chat_stream_route(handler):
    """POST /api/chat-stream"""
    handle_chat_stream(handler)


def handle_chat_save_route(handler):
    """POST /api/chat-save"""
    handle_chat_save(handler)


def handle_chat_load_route(handler, params):
    """GET /api/chat-load"""
    handle_chat_load(handler, params)


def handle_chat_delete_route(handler):
    """POST /api/chat-delete"""
    try:
        length = int(handler.headers.get("Content-Length", 0))
        if length > 0:
            raw = handler.rfile.read(length)
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                handler._send_json(400, {"error": "Invalid JSON body"})
                return
        else:
            handler._send_json(400, {"error": "subject is required"})
            return
        subject = data.get("subject", "")
        if not subject:
            handler._send_json(400, {"error": "subject is required"})
            return
        deleted = delete_chat_file(subject)
        handler._send_json(200, {"deleted": deleted, "subject": subject})
    except Exception as e:
        import logging
        logging.exception("chat-delete error")
        handler._send_json(500, {"error": "internal", "detail": "Internal server error"})