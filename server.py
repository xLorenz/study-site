#!/usr/bin/env python3
"""Study server — zero external dependencies. Port 8081."""

import http.server
import json
import os
import socketserver
import urllib.parse

VAULT = os.path.expanduser("~/study-vault")
STUDY_DIR = os.path.expanduser("~/study")
PORT = 8081

with open(os.path.join(STUDY_DIR, "subject_themes.json")) as f:
    SUBJECT_THEMES = json.load(f)


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

    def _send_html(self, path):
        if not os.path.isfile(path):
            self._send_json(404, {"error": "not_found", "detail": "File not found"})
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self._set_cors()
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"

            if path == "/":
                self._send_html(os.path.join(STUDY_DIR, "index.html"))
            elif path == "/api/health":
                self._send_json(200, {"status": "ok", "vault": VAULT})
            else:
                self._send_json(404, {"error": "not_found", "detail": f"Route not found: {path}"})
        except Exception as e:
            self._send_json(500, {"error": "internal", "detail": str(e)})

    def do_POST(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            self._send_json(405, {"error": "method_not_allowed", "detail": f"POST not allowed on {path}"})
        except Exception as e:
            self._send_json(500, {"error": "internal", "detail": str(e)})


if __name__ == "__main__":
    with socketserver.TCPServer(("", PORT), StudyHandler) as httpd:
        print(f"Study server on :{PORT}")
        httpd.serve_forever()
