"""tube-eye — scheduler: turn validated deliveries into a publish plan.

Deterministic: same inputs, same plan. Reads config.json, deliveries/*.json,
plan/intake_report.json (from intake.py) and receipts/*.json, and writes
plan/schedule.json — the queue the posting agent (POSTER.md) works through.

Rules, in force:
  * a delivery only gets a slot if it passed intake and has no receipt yet
  * nothing is scheduled closer than min_lead_hours — that window is the
    human's chance to cancel in YouTube Studio before anything goes public
  * long-form gets config.long_form.publish_time, max_per_day per day;
    Shorts get their own earlier slot and cap
  * desired_publish_at is honoured when it is far enough in the future;
    otherwise the delivery falls back to the next free slot (and the plan
    says so)

Usage:
    python3 src/scheduler.py           # write plan/schedule.json
    python3 src/scheduler.py --print   # also print the plan
"""

import argparse
import json
import os
import sys
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import manifest as mf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_hhmm(s):
    hh, mm = s.split(":")
    return time(int(hh), int(mm))


def slot_datetime(day, hhmm, tz):
    """Combine a date and 'HH:MM' in the channel timezone -> aware datetime."""
    return datetime.combine(day, parse_hhmm(hhmm), tzinfo=tz)


def plan(config, deliveries, intake_report, receipts, now=None):
    """Pure planning function — no I/O, so tests can pin 'now'."""
    tz = ZoneInfo(config.get("timezone", "Europe/Rome"))
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    lead = timedelta(hours=config.get("min_lead_hours", 24))
    earliest = now + lead

    long_cfg = config.get("long_form", {"publish_time": "17:00", "max_per_day": 1})
    short_cfg = config.get("shorts", {"publish_time": "13:00", "max_per_day": 2})

    posted_ids = set(receipts)

    eligible = []
    for name in sorted(deliveries):
        m = deliveries[name]
        errors = mf.validate(m)
        rep = (intake_report or {}).get("deliveries", {}).get(name, {})
        if errors or not rep.get("ok", False):
            continue  # intake.py already reported why
        if m.get("id") in posted_ids:
            continue
        eligible.append((name, m))

    used = {"video": {}, "short": {}}  # day -> count
    slots = []

    for name, m in eligible:
        kind = m["kind"]
        cfg = short_cfg if kind == "short" else long_cfg
        cap = int(cfg.get("max_per_day", 1))
        publish_time = cfg["publish_time"]

        desired = m.get("desired_publish_at")
        placed = None
        note = None
        if desired:
            try:
                want = datetime.fromisoformat(desired)
                if want.tzinfo is None:
                    want = want.replace(tzinfo=tz)
                if want >= earliest:
                    placed = want.astimezone(tz)
                else:
                    note = (f"desired_publish_at {desired} is inside the "
                            f"{config.get('min_lead_hours', 24)}h lead window; "
                            "fell back to the next free slot")
            except ValueError:
                note = f"desired_publish_at '{desired}' is not ISO-8601; ignored"

        if placed is None:
            day = earliest.date()
            while True:
                cand = slot_datetime(day, publish_time, tz)
                if cand >= earliest and used[kind].get(day, 0) < cap:
                    placed = cand
                    break
                day += timedelta(days=1)

        used[kind][placed.date()] = used[kind].get(placed.date(), 0) + 1
        slots.append({
            "delivery_id": m["id"],
            "manifest": name,
            "title": m["title"],
            "kind": kind,
            "visibility": m["visibility"],
            "publish_at": placed.isoformat(timespec="minutes"),
            "note": note,
        })

    slots.sort(key=lambda s: s["publish_at"])
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "timezone": config.get("timezone", "Europe/Rome"),
        "min_lead_hours": config.get("min_lead_hours", 24),
        "slots": slots,
        "posted": sorted(posted_ids),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", action="store_true", dest="show")
    args = parser.parse_args()

    config = load_json(os.path.join(ROOT, "config.json"), {})
    delivery_dir = os.path.join(ROOT, "deliveries")
    deliveries = {}
    if os.path.isdir(delivery_dir):
        for f in sorted(os.listdir(delivery_dir)):
            if f.endswith(".json") and f != "TEMPLATE.json":
                deliveries[f] = mf.load(os.path.join(delivery_dir, f))

    intake_report = load_json(os.path.join(ROOT, "plan", "intake_report.json"), {})
    receipt_dir = os.path.join(ROOT, "receipts")
    receipts = {}
    if os.path.isdir(receipt_dir):
        for f in os.listdir(receipt_dir):
            if f.endswith(".json"):
                r = load_json(os.path.join(receipt_dir, f), {})
                if r and r.get("delivery_id"):
                    receipts[r["delivery_id"]] = f

    result = plan(config, deliveries, intake_report, receipts)

    plan_dir = os.path.join(ROOT, "plan")
    os.makedirs(plan_dir, exist_ok=True)
    with open(os.path.join(plan_dir, "schedule.json"), "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=1)
        fh.write("\n")

    print(f"scheduler: {len(result['slots'])} planned, "
          f"{len(result['posted'])} already posted -> plan/schedule.json")
    if args.show:
        for s in result["slots"]:
            extra = f"  ({s['note']})" if s["note"] else ""
            print(f"  {s['publish_at']}  {s['delivery_id']}  [{s['kind']}] "
                  f"{s['title']}{extra}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
