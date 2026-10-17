"""Message server: stdlib HTTP, SQLite persistence, optional Basic auth and TLS."""
import base64
import hmac
import html
import json
import os
import re
import sqlite3
import ssl
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from app.redaction import redact

MAX_BODY = 64 * 1024


class Store:
    def __init__(self, path: str):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS messages ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, created_at TEXT NOT NULL)"
            )
            self._conn.commit()

    def add(self, message: str) -> dict:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO messages (message, created_at) VALUES (?, ?)", (message, now)
            )
            self._conn.commit()
            return {"id": cur.lastrowid, "message": message, "created_at": now}

    def all(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, message, created_at FROM messages ORDER BY id"
            ).fetchall()
        return [{"id": r[0], "message": r[1], "created_at": r[2]} for r in rows]

    def delete(self, msg_id: int) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
            self._conn.commit()
            return cur.rowcount > 0


class Handler(BaseHTTPRequestHandler):
    server_version = "MsgServer/1.0"

    def log_message(self, fmt, *args):  # keep test output quiet
        if os.environ.get("LOG_REQUESTS"):
            super().log_message(fmt, *args)

    # ---- helpers
    def _send(self, status: int, body: bytes = b"", ctype: str = "application/json", headers=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, obj):
        self._send(status, json.dumps(obj).encode())

    def _authorized(self) -> bool:
        creds = self.server.credentials  # dict[str, str] or empty
        if not creds:
            return True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            user, _, pw = base64.b64decode(header[6:]).decode().partition(":")
        except Exception:
            return False
        expected = creds.get(user)
        return expected is not None and hmac.compare_digest(expected, pw)

    def _guard(self) -> bool:
        if self._authorized():
            return True
        self._send(
            401,
            json.dumps({"error": "unauthorized"}).encode(),
            headers={"WWW-Authenticate": 'Basic realm="messages"'},
        )
        return False

    # ---- routes
    def do_GET(self):
        if self.path == "/health":
            return self._json(200, {"status": "ok"})
        if not self._guard():
            return
        if self.path == "/messages":
            return self._json(200, self.server.store.all())
        if self.path == "/":
            return self._send(200, self._render_page().encode(), "text/html; charset=utf-8")
        self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self._guard():
            return
        if self.path != "/messages":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._json(400, {"error": "Content-Length required"})
        if length > MAX_BODY:
            return self._json(413, {"error": "payload too large"})
        try:
            data = json.loads(self.rfile.read(length) or b"")
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid JSON"})
        msg = data.get("message") if isinstance(data, dict) else None
        if not isinstance(msg, str) or not msg.strip():
            return self._json(400, {"error": "'message' must be a non-empty string"})
        self._json(201, self.server.store.add(redact(msg)))

    def do_DELETE(self):
        if not self._guard():
            return
        m = re.fullmatch(r"/messages/(\d+)", self.path)
        if not m:
            return self._json(404, {"error": "not found"})
        if self.server.store.delete(int(m.group(1))):
            return self._send(204)
        self._json(404, {"error": "message not found"})

    def _render_page(self) -> str:
        rows = "".join(
            f"<tr><td>{m['id']}</td><td>{html.escape(m['created_at'])}</td>"
            f"<td class='msg'>{html.escape(m['message'])}</td></tr>"
            for m in self.server.store.all()
        )
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>Messages</title></head><body>"
            "<h1>Messages</h1><table id='messages' border='1'>"
            "<thead><tr><th>ID</th><th>Time (UTC)</th><th>Message</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></body></html>"
        )


def make_server(host="127.0.0.1", port=8000, db_path="messages.db",
                credentials=None, certfile=None, keyfile=None) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.store = Store(db_path)
    srv.credentials = credentials or {}
    if certfile and keyfile:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(certfile, keyfile)
        srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    return srv


def main():
    creds = {}
    if os.environ.get("AUTH_USER") and os.environ.get("AUTH_PASS"):
        creds[os.environ["AUTH_USER"]] = os.environ["AUTH_PASS"]
    srv = make_server(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        db_path=os.environ.get("DB_PATH", "messages.db"),
        credentials=creds,
        certfile=os.environ.get("TLS_CERT"),
        keyfile=os.environ.get("TLS_KEY"),
    )
    scheme = "https" if os.environ.get("TLS_CERT") else "http"
    print(f"Serving on {scheme}://{srv.server_address[0]}:{srv.server_address[1]} "
          f"(auth={'on' if creds else 'off'})", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
