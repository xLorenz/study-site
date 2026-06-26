#!/usr/bin/env python3
"""Study server — zero external dependencies. Port 8081."""

import http.server
import json
import os
import shutil
import signal
import socketserver
import sys
import threading
import urllib.parse
import yaml

# Derive STUDY_DIR from __file__ (repo root), allow env override
STUDY_DIR = os.environ.get("STUDY_DIR", os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(STUDY_DIR, ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Load .env (gitignored, API keys)
ENV_PATH = os.path.join(STUDY_DIR, ".env")
if os.path.isfile(ENV_PATH):
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

# Load config.yaml (non-secrets)
CFG_PATH = os.path.join(STUDY_DIR, "config.yaml")
CFG = {}
if os.path.isfile(CFG_PATH):
    try:
        with open(CFG_PATH) as f:
            CFG = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: config.yaml load failed: {e}")

# Env var overrides — set BEFORE importing chat modules
os.environ.setdefault("STUDY_DIR", STUDY_DIR)
os.environ.setdefault("CACHE_DIR", CACHE_DIR)

# Resolve vault: env var → config.yaml path (relative→absolute via STUDY_DIR) → fallback
_vault_path = CFG.get("vault_path", "vaults")
VAULT = os.path.expanduser(os.environ.get("STUDY_VAULT_PATH",
    _vault_path if os.path.isabs(_vault_path) else os.path.join(STUDY_DIR, _vault_path)))
VAULT = os.path.normpath(VAULT)
os.environ.setdefault("VAULT_DIR", VAULT)

os.environ.setdefault("NIM_BASE_URL", CFG.get("nim_base_url", "https://integrate.api.nvidia.com/v1"))
os.environ.setdefault("ZEN_BASE_URL", CFG.get("zen_base_url", "https://opencode.ai/zen/v1"))
os.environ.setdefault("SKILL_DIR", os.path.expanduser("~/.hermes/skills/study"))

# Add MiKTeX to PATH so manim can find pdflatex
_pdflatex = shutil.which("pdflatex")
if _pdflatex:
    _miktex_dir = os.path.dirname(os.path.realpath(_pdflatex))
    if _miktex_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = _miktex_dir + os.pathsep + os.environ.get("PATH", "")

os.environ.setdefault("NIM_API_KEY", "")
os.environ.setdefault("OPENCODE_ZEN_API_KEY", "")
NIM_API_KEY = os.environ.get("NIM_API_KEY", "")
OPENCODE_ZEN_API_KEY = os.environ.get("OPENCODE_ZEN_API_KEY", "")
NIM_BASE_URL = os.environ.get("NIM_BASE_URL", CFG.get("nim_base_url", "https://integrate.api.nvidia.com/v1"))
HOST = os.environ.get("HOST", CFG.get("host", "0.0.0.0"))
PORT = int(os.environ.get("PORT", CFG.get("port", 8081)))

if not NIM_API_KEY and not OPENCODE_ZEN_API_KEY:
    print("[WARNING] No API keys configured. Copy .env.example to .env and add your keys.")
    print("   LLM features (chat, wiki ingest) will fail without API keys.")

from routes import register, setup_routes


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
        file_size = os.path.getsize(abs_path)
        self.send_response(200)
        self._set_cors()
        if cache_control:
            self.send_header("Cache-Control", cache_control)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.end_headers()
        with open(abs_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    # ─── Routing ───

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
                self._api_root()
            elif path == "/api/health":
                self._api_health()
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
                self._api_chat_load(params)
            elif path == "/api/model":
                self._api_model()
            elif path == "/api/themes":
                self._api_themes()
            elif path.startswith("/skill/"):
                skill_name = path[len("/skill/"):]
                self._api_skill(skill_name)
            elif path.startswith("/static/"):
                self._api_static(path)
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
                self._api_chat_start()
            elif path == "/api/chat-stream":
                self._api_chat_stream()
            elif path == "/api/chat-save":
                self._api_chat_save()
            elif path == "/api/chat-delete":
                self._api_chat_delete()
            elif path == "/api/create-subject":
                self._api_create_subject()
            elif path == "/api/delete-subject":
                self._api_delete_subject()
            else:
                self._send_json(405, {"error": "method_not_allowed", "detail": f"POST not allowed on {path}"})
        except Exception as e:
            import logging
            logging.exception("do_POST unhandled error")
            self._send_json(500, {"error": "internal", "detail": "Internal server error"})


# Register all routes after class definition
register(StudyHandler)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True

    # Initialize routes with config
    setup_routes(
        StudyHandler,
        study_dir=STUDY_DIR,
        vault=VAULT,
        cache_dir=CACHE_DIR,
        cfg=CFG,
        nim_api_key=NIM_API_KEY,
        opencode_zen_api_key=OPENCODE_ZEN_API_KEY,
        nim_base_url=NIM_BASE_URL,
        host=HOST,
        port=PORT,
    )

    httpd = socketserver.ThreadingTCPServer((HOST, PORT), StudyHandler)
    httpd.allow_reuse_address = True

    def _shutdown(signum, frame):
        print("\nShutting down gracefully...")
        httpd.shutdown()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    print(f"Study server on {HOST}:{PORT}")
    httpd.serve_forever()