"""tube-eye — preflight: prove the pc-eye link and the queue before a shift.

POSTER.md tells the posting agent *how* to work. This is the machine-checked
counterpart: one command that answers "can I actually post right now?" before
any click is spent, and again whenever something feels wrong.

It answers two independent questions:

  1. **Is the link to the PC real?** — `/state`, `/selftest`, `/shot` and the
     `/shot?changed=` waiting trick, checked against the live pc-eye server.
     A red here means the agent is blind or its hand does not agree with its
     eyes, and the shift cannot start.
  2. **Is there anything to post?** — the plan, the next slot, which delivery
     it belongs to, and whether its receipt already exists.

Usage:
    export PC_EYE_URL=https://<tunnel>.trycloudflare.com
    export PC_EYE_TOKEN=<32 hex chars>
    python3 src/preflight.py                 # link + queue
    python3 src/preflight.py --act           # also move the pointer (harmless)
    python3 src/preflight.py --queue-only    # no network at all
    python3 src/preflight.py --json          # machine-readable

Exit codes: 0 green · 1 a critical check failed (do not post) · 2 warnings only.

The token is never printed, never logged, and never written to a file here.
"""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, "plan", "schedule.json")
RECEIPTS = os.path.join(ROOT, "receipts")

CRITICAL = "critical"
WARN = "warn"


class Check:
    __slots__ = ("name", "ok", "detail", "level", "skipped")

    def __init__(self, name, ok, detail="", level=CRITICAL, skipped=False):
        self.name, self.ok, self.detail = name, ok, detail
        self.level, self.skipped = level, skipped

    def as_dict(self):
        return {"name": self.name, "ok": self.ok, "detail": self.detail,
                "level": self.level, "skipped": self.skipped}


class Link:
    """A pc-eye client that refuses to leak the token and reads its own headers."""

    def __init__(self, url, token, timeout=20.0):
        self.url = (url or "").rstrip("/")
        self.token = token or ""
        self.timeout = timeout

    def _open(self, path, data=None, headers=None):
        hdrs = {"X-Token": self.token}
        hdrs.update(headers or {})
        body = None
        if data is not None:
            body = json.dumps(data).encode()
            hdrs["Content-Type"] = "application/json"
        req = urllib.request.Request(self.url + path, data=body, headers=hdrs,
                                     method="POST" if data is not None else "GET")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, dict(resp.headers), resp.read(), time.time() - t0
        except urllib.error.HTTPError as exc:      # 304, 401, 409, 429 … are answers, not crashes
            return exc.code, dict(exc.headers or {}), exc.read(), time.time() - t0
        except urllib.error.URLError as exc:       # DNS, refused, TLS, timeout — the dead-tunnel case
            reason = getattr(exc, "reason", exc)
            return 0, {}, f"unreachable: {reason}".encode(), time.time() - t0
        except (TimeoutError, OSError) as exc:     # socket-level failures, same meaning
            return 0, {}, f"unreachable: {exc}".encode(), time.time() - t0

    def get(self, path):
        return self._open(path)

    def act(self, action):
        return self._open("/act", data=action)


def link_checks(link, do_act=False):
    """Every check that needs the live PC. Returns (checks, facts)."""
    checks, facts = [], {}

    def add(name, ok, detail="", level=CRITICAL):
        checks.append(Check(name, ok, detail, level))
        return ok

    # 0 — the URL itself. A stale tunnel is the most common failure of all:
    # trycloudflare hands out a new hostname every run.
    loopback = any(link.url.startswith(p) for p in
                   ("http://127.0.0.1", "http://localhost", "http://[::1]"))
    if not link.url.startswith("https://") and not loopback:
        add("url", False, "PC_EYE_URL must start with https:// (plain http off the machine "
                          "would put the token on the wire in clear)")
        return checks, facts
    if loopback:
        checks.append(Check("url-tls", False,
                            "plain http on loopback — fine for a local test, never for a real shift",
                            WARN))
    host = link.url.split("://", 1)[1].split("/", 1)[0]
    if not link.token:
        add("token", False, "no token: set PC_EYE_TOKEN (the 32 hex chars from start.bat)")
        return checks, facts
    add("url", True, f"host {host}")
    add("token", True, f"{len(link.token)} chars (value never printed)")

    status, _h, body, dt = link.get("/state")
    if status != 200:
        err = body[:160].decode("utf-8", "replace") if isinstance(body, bytes) else str(body)
        if status == 0:
            add("state", False, f"cannot reach the PC ({err}). "
                                "The tunnel URL changes on every start.bat run — ask the human "
                                "for the fresh URL and token, do not retry the old one.")
        elif status == 401:
            add("state", False, "GET /state -> 401: wrong or missing token. Ask the human to re-read "
                                "the two lines from start.bat; never guess.")
        else:
            add("state", False, f"GET /state -> {status}: {err or 'no answer'}")
        return checks, facts
    try:
        state = json.loads(body)
    except json.JSONDecodeError:
        add("state", False, "GET /state did not return JSON")
        return checks, facts

    facts.update({
        "version": state.get("version"),
        "host": state.get("host"),
        "os": state.get("os"),
        "screen": state.get("screen"),
        "dry_run": state.get("dry_run"),
        "capture_ok": state.get("capture_ok"),
        "uptime_s": state.get("uptime_s"),
        "coord_space": state.get("coord_space"),
        "state_latency_s": round(dt, 2),
    })
    add("state", True, f"v{state.get('version')} on {state.get('host')} "
                       f"({state.get('os')}), up {state.get('uptime_s')}s, {dt:.2f}s")

    # The two verdicts that exist precisely because they once went wrong on
    # this machine: a demo server, and eyes/hand in different pixel spaces.
    add("not-dry-run", state.get("dry_run") is not True,
        "dry_run is TRUE — nothing would reach the machine. Report it and stop."
        if state.get("dry_run") is True else "real input, not a recording")

    space = state.get("coord_space") or {}
    add("coord-space", space.get("consistent") is True,
        space.get("warning") or f"eyes and hand agree ({state.get('screen')})")

    add("capture", state.get("capture_ok") is not False,
        "capture_ok is false — the agent would be blind"
        if state.get("capture_ok") is False else "capture available")

    if state.get("screen") and isinstance(state.get("screen"), list) and len(state["screen"]) == 2:
        w, h = state["screen"]
        add("screen-size", w >= 1024 and h >= 700, f"{w}x{h}", WARN)

    if dt > 3.0:
        add("latency", False, f"/state took {dt:.1f}s — the tunnel is slow; every click will feel it", WARN)
    else:
        add("latency", True, f"/state {dt:.2f}s")

    # /selftest — the machine's own statement of what it can and cannot do.
    status, _h, body, dt = link.get("/selftest")
    if status != 200:
        add("selftest", False, f"GET /selftest -> {status}")
    else:
        try:
            st = json.loads(body)
        except json.JSONDecodeError:
            st = {}
        failing = [c for c in st.get("checks", []) if not c.get("ok")]
        test_mode = [c for c in st.get("checks", []) if c.get("name") == "TEST-MODE"]
        add("selftest", st.get("ok") is True and not failing,
            "; ".join(f"{c.get('name')}: {c.get('detail')}" for c in failing) or
            f"{len(st.get('checks', []))} checks green ({dt:.2f}s)")
        add("selftest-no-test-mode", not test_mode,
            test_mode[0].get("detail") if test_mode else "no TEST-MODE flag")

    # /shot — the eyes. Bytes, and the two headers that make aiming possible.
    status, hdrs, body, dt = link.get("/shot?max=0")
    full, sent = hdrs.get("X-Screen-Full"), hdrs.get("X-Screen-Sent")
    shot_hash = hdrs.get("X-Screen-Hash")
    ok = status == 200 and isinstance(body, (bytes, bytearray)) and len(body) > 1000
    add("shot", ok, f"{status}, {len(body) // 1024} KB, {dt:.2f}s"
        if ok else f"GET /shot -> {status}")
    add("shot-headers", bool(full and sent), f"full {full} -> sent {sent}"
        if (full and sent) else "X-Screen-Full / X-Screen-Sent missing — you cannot aim safely")
    facts["shot_bytes"] = len(body) if isinstance(body, (bytes, bytearray)) else 0
    facts["shot_latency_s"] = round(dt, 2)

    # /shot?changed= — the waiting mechanism POSTER.md relies on while a 600 MB
    # download lands. It must answer 304, not another frame.
    if shot_hash:
        status, _h, _b, _dt = link.get(f"/shot?changed={shot_hash}")
        add("shot-changed", status == 304,
            "304 with no body (the screen is unchanged — wait, do not re-download)"
            if status == 304 else f"expected 304 for an unchanged screen, got {status}")
    else:
        add("shot-changed", False, "no X-Screen-Hash header to test the wait with")

    if do_act:
        px, py = (200, 200)
        if isinstance(facts.get("screen"), list) and len(facts["screen"]) == 2:
            px, py = facts["screen"][0] // 2, facts["screen"][1] // 2
        status, _h, body, dt = link.act({"action": "move", "x": px, "y": py})
        try:
            reply = json.loads(body) if status == 200 else {}
        except json.JSONDecodeError:
            reply = {}
        exact = reply.get("exact") is True
        add("act-move", status == 200 and exact,
            f"pointer to ({px},{py}) exact={reply.get('exact')} "
            f"landed={reply.get('landed')} in {dt:.2f}s"
            if status == 200 else f"POST /act -> {status}: {body[:120]!r}")
    else:
        checks.append(Check("act-move", True,
                            "not tested — re-run with --act to prove the hand moves too",
                            WARN, skipped=True))
    return checks, facts


def queue_checks(now=None):
    """The tube-eye half: is there a postable delivery, and is it really next?"""
    checks, facts = [], {}
    now = now or datetime.now(timezone.utc)

    if not os.path.exists(PLAN):
        checks.append(Check("plan", False,
                            "plan/schedule.json missing — run src/intake.py then src/scheduler.py"))
        return checks, facts
    with open(PLAN, "r", encoding="utf-8") as fh:
        plan = json.load(fh)

    slots = plan.get("slots", [])
    facts["slots"] = len(slots)
    posted = plan.get("posted", [])
    facts["posted"] = len(posted)

    future = []
    for s in slots:
        try:
            when = datetime.fromisoformat(s["publish_at"])
        except (KeyError, ValueError, TypeError):
            checks.append(Check("slot-parse", False, f"unreadable publish_at in {s.get('delivery_id')}"))
            continue
        if when > now:
            future.append((when, s))

    if not future:
        checks.append(Check("queue", False,
                            "no slot in the future — nothing to post. Run the scheduler, or say so plainly",
                            WARN))
        return checks, facts

    future.sort(key=lambda t: t[0])
    when, slot = future[0]
    receipt = os.path.join(RECEIPTS, f"{slot.get('delivery_id')}.json")
    has_receipt = os.path.exists(receipt)
    facts["next"] = {"delivery_id": slot.get("delivery_id"),
                     "title": slot.get("title"), "kind": slot.get("kind"),
                     "publish_at": slot.get("publish_at"),
                     "manifest": slot.get("manifest"),
                     "already_has_receipt": has_receipt}
    hours = (when - now).total_seconds() / 3600.0
    checks.append(Check("next-slot", not has_receipt,
                        f"{slot.get('delivery_id')} '{slot.get('title')}' in {hours:.1f}h "
                        f"({slot.get('publish_at')})"
                        + (" — but a receipt already exists: posted. Take the one after it."
                           if has_receipt else "")))
    checks.append(Check("queue", True, f"{len(future)} future slot(s), {len(posted)} posted"))
    return checks, facts


def run(url=None, token=None, do_act=False, queue_only=False, now=None, timeout=20.0):
    """Run every check. Returns (checks, facts) — importable, so tests use it."""
    checks, facts = [], {}
    if not queue_only:
        l_checks, l_facts = link_checks(Link(url, token, timeout), do_act=do_act)
        checks += l_checks
        facts["link"] = l_facts
    q_checks, q_facts = queue_checks(now=now)
    checks += q_checks
    facts["queue"] = q_facts
    return checks, facts


def verdict(checks, facts=None):
    critical_failed = [c for c in checks if not c.ok and c.level == CRITICAL]
    warned = [c for c in checks if not c.ok and c.level == WARN]
    link_tested = bool(facts and "link" in facts)
    if critical_failed:
        return 1, f"NOT READY — {len(critical_failed)} critical check(s) failed"
    if warned:
        return 2, f"READY, with {len(warned)} warning(s)"
    if not link_tested:
        return 0, "QUEUE OK — plan is valid (link not tested: --queue-only)"
    return 0, "READY — link proven, queue has work"


def render(checks, facts, use_json=False, as_json=False):
    code, summary = verdict(checks, facts)
    if as_json:
        print(json.dumps({"verdict": summary, "exit": code,
                          "checks": [c.as_dict() for c in checks], "facts": facts}, indent=1))
        return code
    mark = {True: "[ok  ]", False: "[FAIL]"}
    print("tube-eye preflight\n")
    for c in checks:
        label = mark[c.ok]
        if not c.ok and c.level == WARN:
            label = "[warn]"
        if c.skipped:
            label = "[skip]"
        print(f"  {label} {c.name:<20} {c.detail}")
    nxt = (facts.get("queue") or {}).get("next")
    if nxt:
        print(f"\n  next up: {nxt['delivery_id']} [{nxt['kind']}] '{nxt['title']}' "
              f"-> {nxt['publish_at']}")
    print(f"\n  {summary}")
    return code


def main():
    ap = argparse.ArgumentParser(description="prove the pc-eye link and the posting queue")
    ap.add_argument("--url", default=os.environ.get("PC_EYE_URL", ""))
    ap.add_argument("--token", default=os.environ.get("PC_EYE_TOKEN", ""))
    ap.add_argument("--act", action="store_true", help="also move the pointer (harmless, proves the hand)")
    ap.add_argument("--queue-only", action="store_true", help="skip the network entirely")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--timeout", type=float, default=20.0)
    args = ap.parse_args()

    checks, facts = run(args.url, args.token, do_act=args.act,
                        queue_only=args.queue_only, timeout=args.timeout)
    sys.exit(render(checks, facts, as_json=args.json))


if __name__ == "__main__":
    main()
