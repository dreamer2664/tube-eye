"""tube-eye — intake: validate every delivery, write plan/intake_report.json.

Offline by default (CI-safe). With --online it also HEADs every asset URL and
records reachability + content-length, so a broken release link is caught here
and not at 17:00 in YouTube Studio.

Usage:
    python3 src/intake.py            # offline validation
    python3 src/intake.py --online   # + reachability check of asset URLs
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifest as mf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DELIVERIES = os.path.join(ROOT, "deliveries")
PLAN_DIR = os.path.join(ROOT, "plan")
REPORT = os.path.join(PLAN_DIR, "intake_report.json")


def delivery_files():
    if not os.path.isdir(DELIVERIES):
        return []
    return sorted(
        os.path.join(DELIVERIES, f)
        for f in os.listdir(DELIVERIES)
        if f.endswith(".json") and f != "TEMPLATE.json"
    )


def check_url(url):
    """HEAD (falling back to ranged GET) an asset URL. Returns (ok, detail)."""
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            length = resp.headers.get("Content-Length")
            return True, {"status": resp.status, "bytes": int(length) if length else None}
    except Exception as exc:  # noqa: BLE001 — intake must never crash on one bad link
        return False, {"error": str(exc)[:200]}


def run(online=False):
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "online": online,
        "deliveries": {},
    }
    any_invalid = False

    for path in delivery_files():
        name = os.path.basename(path)
        try:
            m = mf.load(path)
        except (json.JSONDecodeError, OSError) as exc:
            report["deliveries"][name] = {"ok": False, "errors": [f"unreadable: {exc}"]}
            any_invalid = True
            continue

        errors = mf.validate(m)
        entry = {"ok": not errors, "errors": errors, "id": m.get("id"), "kind": m.get("kind")}

        if online and not errors:
            assets = {}
            for key in ("video", "thumbnail", "captions"):
                block = m.get(key)
                if isinstance(block, dict) and block.get("url"):
                    ok, detail = check_url(block["url"])
                    assets[key] = detail
                    if not ok:
                        errors.append(f"{key}.url unreachable: {detail.get('error')}")
                    elif key == "video" and block.get("bytes") and detail.get("bytes"):
                        if detail["bytes"] != block["bytes"]:
                            errors.append(
                                f"video.bytes says {block['bytes']} but the server "
                                f"serves {detail['bytes']}"
                            )
            entry["ok"] = not errors
            entry["assets"] = assets

        report["deliveries"][name] = entry
        any_invalid = any_invalid or not entry["ok"]

    os.makedirs(PLAN_DIR, exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1)
        fh.write("\n")

    total = len(report["deliveries"])
    good = sum(1 for e in report["deliveries"].values() if e["ok"])
    print(f"intake: {good}/{total} deliveries valid"
          f"{' (online)' if online else ' (offline)'} -> plan/intake_report.json")
    for name, entry in report["deliveries"].items():
        flag = "ok  " if entry["ok"] else "FAIL"
        print(f"  [{flag}] {name}")
        for e in entry["errors"]:
            print(f"         - {e}")
    return 1 if any_invalid else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--online", action="store_true", help="also check asset URLs")
    sys.exit(run(online=parser.parse_args().online))
