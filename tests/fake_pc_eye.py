"""A stand-in for pc-eye, faithful to the routes tube-eye actually uses.

Why a stub and not the real server: pc-eye's capture path needs a display (it is
Windows-first, and on this Linux test box the X call segfaults), but the thing
tube-eye depends on is the *protocol* — /state, /selftest, /shot (+headers,
+changed=304), /act — plus the handful of bad states that have actually burned
an agent before: a demo server, eyes and hand in different pixel spaces, a
stale token, a dead tunnel. Those are all reproducible here, deterministically.

Usage in tests:
    with FakePcEye() as fake:
        checks, facts = preflight.run(fake.url, fake.token)
    with FakePcEye(dry_run=True) as fake: ...
    with FakePcEye(coord_consistent=False) as fake: ...
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

TOKEN = "0123456789abcdef0123456789abcdef"


class FakePcEye:
    def __init__(self, token=TOKEN, dry_run=False, coord_consistent=True,
                 capture_ok=True, send_shot_headers=True, selftest_ok=True,
                 screen=(1920, 1080), honour_changed=True, delay=0.0):
        self.token = token
        self.dry_run = dry_run
        self.coord_consistent = coord_consistent
        self.capture_ok = capture_ok
        self.send_shot_headers = send_shot_headers
        self.selftest_ok = selftest_ok
        self.screen = list(screen)
        self.honour_changed = honour_changed
        self.delay = delay
        self.moves = []                      # every /act the client sent
        self._srv = None
        self._thread = None

    # -- lifecycle ---------------------------------------------------------
    def __enter__(self):
        outer = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):       # keep test output clean
                pass

            def _json(self, code, payload, headers=None):
                body = json.dumps(payload).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                for k, v in (headers or {}).items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(body)

            def _token_ok(self, q):
                if self.headers.get("X-Token") == outer.token:
                    return True
                return (q.get("t") or [""])[0] == outer.token

            def do_GET(self):
                if outer.delay:
                    import time
                    time.sleep(outer.delay)
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if not self._token_ok(q):
                    return self._json(401, {"ok": False, "error": "bad or missing token"})
                if u.path == "/state":
                    return self._json(200, {
                        "ok": True, "version": "1.0.3", "host": "FAKE-PC", "os": "Windows",
                        "screen": outer.screen, "capture_ok": outer.capture_ok,
                        "capture_why": None if outer.capture_ok else "no display",
                        "cursor": [10, 10], "uptime_s": 4242, "last": None, "dpi": {},
                        "dry_run": outer.dry_run,
                        "coord_space": {
                            "consistent": outer.coord_consistent,
                            "screen": outer.screen, "input": outer.screen,
                            "warning": None if outer.coord_consistent
                            else "eyes 1920x1080, hand 1536x864 — every click would miss",
                        },
                        "at": "2026-10-28T15:00:00Z",
                    })
                if u.path == "/selftest":
                    checks = [
                        {"name": "capture", "ok": outer.capture_ok, "detail": "1920x1080"},
                        {"name": "token", "ok": True, "detail": "32 chars"},
                        {"name": "platform", "ok": True, "detail": "os=Windows"},
                        {"name": "coordinate-space", "ok": outer.coord_consistent,
                         "detail": "eyes and hand agree" if outer.coord_consistent else "mismatch"},
                    ]
                    if outer.dry_run:
                        checks.append({"name": "TEST-MODE", "ok": True,
                                       "detail": "dry-run: NOTHING is sent to the mouse or keyboard."})
                    return self._json(200, {"ok": outer.selftest_ok and outer.capture_ok,
                                            "version": "1.0.3", "dry_run": outer.dry_run,
                                            "checks": checks})
                if u.path == "/shot":
                    hdrs = {}
                    if outer.send_shot_headers:
                        full = f"{outer.screen[0]}x{outer.screen[1]}"
                        hdrs = {"X-Screen-Full": full, "X-Screen-Sent": "1440x810",
                                "X-Screen-Hash": "4f08b322135dad89"}
                    want = (q.get("changed") or [None])[0]
                    if want and outer.honour_changed and want == "4f08b322135dad89":
                        self.send_response(304)
                        for k, v in hdrs.items():
                            self.send_header(k, v)
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        return
                    body = b"\xff\xd8\xff\xe0" + b"0" * 4096 + b"\xff\xd9"   # >1000 bytes
                    self.send_response(200)
                    self.send_header("Content-Type", "image/jpeg")
                    self.send_header("Content-Length", str(len(body)))
                    for k, v in hdrs.items():
                        self.send_header(k, v)
                    self.end_headers()
                    self.wfile.write(body)
                    return
                return self._json(404, {"ok": False, "error": f"no route {u.path}"})

            def do_POST(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path != "/act":
                    return self._json(404, {"ok": False, "error": f"no route {u.path}"})
                if not self._token_ok(q):
                    return self._json(401, {"ok": False, "error": "bad or missing token"})
                if self.headers.get("Content-Type") != "application/json":
                    return self._json(415, {"ok": False, "error": "send application/json"})
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    action = json.loads(self.rfile.read(n) or b"{}")
                except json.JSONDecodeError:
                    return self._json(400, {"ok": False, "error": "body is not JSON"})
                outer.moves.append(action)
                x, y = action.get("x", 0), action.get("y", 0)
                exact = outer.coord_consistent and not outer.dry_run
                return self._json(200, {"ok": True, "action": action.get("action"),
                                        "did": {}, "cursor": [x, y],
                                        "landed": [x, y] if exact else [0, 0],
                                        "off_by": [0, 0] if exact else [-x, -y],
                                        "exact": exact, "at": "2026-10-28T15:00:01Z"})

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self._srv.server_address[1]
        self._thread = threading.Thread(target=self._srv.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc):
        if self._srv:
            self._srv.shutdown()
            self._srv.server_close()
        if self._thread:
            self._thread.join(timeout=3)
        return False

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"
