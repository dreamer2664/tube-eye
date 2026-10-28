"""tube-eye — tests for manifest validation and scheduler planning.

Pure logic, no network, no clock dependence (now is pinned). Run:
    python3 tests/run_all.py
"""

import copy
import json
import os
import sys
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

import manifest as mf  # noqa: E402
import scheduler  # noqa: E402

ROME = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 10, 28, 15, 30, tzinfo=ROME)  # a Wednesday afternoon, mid-shift

CONFIG = {
    "timezone": "Europe/Rome",
    "long_form": {"publish_time": "17:00", "max_per_day": 1},
    "shorts": {"publish_time": "13:00", "max_per_day": 2},
    "min_lead_hours": 24,
}


def good_manifest(vid="d-0001", **over):
    m = {
        "schema_version": 1,
        "id": vid,
        "title": "A Fine Video About A Thing",
        "description": "What it is, what is synthetic, where it came from.",
        "tags": ["thing", "history"],
        "producer": "tester",
        "source_repo": "dreamer2664/competitionvideo28",
        "kind": "video",
        "visibility": "scheduled",
        "approved_by_human": False,
        "synthetic_media_disclosure": True,
        "desired_publish_at": None,
        "video": {
            "url": "https://github.com/dreamer2664/storagecode/releases/download/t/x.mp4",
            "sha256": "a" * 64,
            "bytes": 1234,
            "duration_s": 300.0,
        },
        "thumbnail": {
            "url": "https://github.com/dreamer2664/storagecode/releases/download/t/x.png",
            "sha256": "b" * 64,
        },
    }
    m.update(over)
    return m


def intake_ok(*names):
    return {"deliveries": {n: {"ok": True} for n in names}}


class TestManifest(unittest.TestCase):
    def test_good_manifest_passes(self):
        self.assertEqual(mf.validate(good_manifest()), [])

    def test_bad_id(self):
        self.assertTrue(mf.validate(good_manifest(id="vid-1")))

    def test_missing_title(self):
        m = good_manifest()
        del m["title"]
        self.assertTrue(mf.validate(m))

    def test_title_over_100(self):
        self.assertTrue(mf.validate(good_manifest(title="x" * 101)))

    def test_description_over_5000(self):
        self.assertTrue(mf.validate(good_manifest(description="x" * 5001)))

    def test_tags_over_500_total(self):
        self.assertTrue(mf.validate(good_manifest(tags=["x" * 300, "y" * 300])))

    def test_bad_sha256(self):
        m = good_manifest()
        m["video"]["sha256"] = "nothex"
        self.assertTrue(mf.validate(m))

    def test_uppercase_sha256_rejected(self):
        m = good_manifest()
        m["video"]["sha256"] = "A" * 64
        self.assertTrue(mf.validate(m))

    def test_http_url_rejected(self):
        m = good_manifest()
        m["video"]["url"] = "http://insecure.example/x.mp4"
        self.assertTrue(mf.validate(m))

    def test_public_requires_human_approval(self):
        errs = mf.validate(good_manifest(visibility="public"))
        self.assertTrue(any("approved_by_human" in e for e in errs))
        self.assertEqual(mf.validate(good_manifest(visibility="public", approved_by_human=True)), [])

    def test_short_over_180s_rejected(self):
        m = good_manifest(kind="short")
        m["video"]["duration_s"] = 200
        self.assertTrue(mf.validate(m))

    def test_short_under_180s_ok(self):
        m = good_manifest(kind="short")
        m["video"]["duration_s"] = 58
        self.assertEqual(mf.validate(m), [])

    def test_thumbnail_required_for_long_form_only(self):
        m = good_manifest()
        del m["thumbnail"]
        self.assertTrue(mf.validate(m))
        m2 = good_manifest(kind="short")
        m2["video"]["duration_s"] = 58
        del m2["thumbnail"]
        self.assertEqual(mf.validate(m2), [])

    def test_captions_language_required(self):
        m = good_manifest(captions={"url": "https://example/x.srt"})
        self.assertTrue(mf.validate(m))

    def test_disclosure_must_be_bool(self):
        self.assertTrue(mf.validate(good_manifest(synthetic_media_disclosure="yes")))


class TestScheduler(unittest.TestCase):
    def test_first_video_gets_next_day_slot(self):
        # now = Wed 15:30; lead 24h -> earliest Thu 15:30; Thu 17:00 qualifies
        d = {"a.json": good_manifest()}
        out = scheduler.plan(CONFIG, d, intake_ok("a.json"), {}, now=NOW)
        self.assertEqual(len(out["slots"]), 1)
        self.assertEqual(out["slots"][0]["publish_at"], "2026-10-29T17:00+01:00")

    def test_same_day_never_used(self):
        d = {"a.json": good_manifest()}
        out = scheduler.plan(CONFIG, d, intake_ok("a.json"), {}, now=NOW)
        slot = datetime.fromisoformat(out["slots"][0]["publish_at"])
        self.assertGreaterEqual(slot, NOW + timedelta(hours=24))

    def test_one_long_form_per_day(self):
        d = {f"{i}.json": good_manifest(vid=f"d-000{i}") for i in range(1, 4)}
        out = scheduler.plan(CONFIG, d, intake_ok(*d), {}, now=NOW)
        days = [datetime.fromisoformat(s["publish_at"]).date() for s in out["slots"]]
        self.assertEqual(len(days), 3)
        self.assertEqual(len(set(days)), 3)  # three different days

    def test_two_shorts_share_a_day(self):
        d = {}
        for i in (1, 2, 3):
            m = good_manifest(vid=f"d-000{i}", kind="short")
            m["video"]["duration_s"] = 58
            d[f"{i}.json"] = m
        out = scheduler.plan(CONFIG, d, intake_ok(*d), {}, now=NOW)
        days = [datetime.fromisoformat(s["publish_at"]).date() for s in out["slots"]]
        self.assertEqual(days[0], days[1])   # cap is 2/day
        self.assertNotEqual(days[1], days[2])

    def test_posted_deliveries_skipped(self):
        d = {"a.json": good_manifest()}
        out = scheduler.plan(CONFIG, d, intake_ok("a.json"), {"d-0001": "receipt.json"}, now=NOW)
        self.assertEqual(out["slots"], [])
        self.assertEqual(out["posted"], ["d-0001"])

    def test_failed_intake_skipped(self):
        d = {"a.json": good_manifest(), "b.json": good_manifest(vid="d-0002")}
        report = {"deliveries": {"a.json": {"ok": True}, "b.json": {"ok": False}}}
        out = scheduler.plan(CONFIG, d, report, {}, now=NOW)
        self.assertEqual([s["delivery_id"] for s in out["slots"]], ["d-0001"])

    def test_desired_publish_at_honoured(self):
        want = (NOW + timedelta(days=5)).replace(hour=10, minute=0)
        m = good_manifest(desired_publish_at=want.isoformat())
        d = {"a.json": m}
        out = scheduler.plan(CONFIG, d, intake_ok("a.json"), {}, now=NOW)
        self.assertEqual(out["slots"][0]["publish_at"], want.isoformat(timespec="minutes"))
        self.assertIsNone(out["slots"][0]["note"])

    def test_desired_too_soon_falls_back_with_note(self):
        m = good_manifest(desired_publish_at=(NOW + timedelta(hours=3)).isoformat())
        out = scheduler.plan(CONFIG, {"a.json": m}, intake_ok("a.json"), {}, now=NOW)
        self.assertIsNotNone(out["slots"][0]["note"])
        slot = datetime.fromisoformat(out["slots"][0]["publish_at"])
        self.assertGreaterEqual(slot, NOW + timedelta(hours=24))

    def test_slots_sorted_chronologically(self):
        d = {}
        for i in range(1, 5):
            d[f"{i}.json"] = good_manifest(vid=f"d-000{i}")
        out = scheduler.plan(CONFIG, d, intake_ok(*d), {}, now=NOW)
        times = [s["publish_at"] for s in out["slots"]]
        self.assertEqual(times, sorted(times))


class TestRealDeliveries(unittest.TestCase):
    """The shipped deliveries/ must stay valid — CI enforces this."""

    def test_all_shipped_deliveries_valid(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ddir = os.path.join(root, "deliveries")
        files = [f for f in os.listdir(ddir) if f.endswith(".json") and f != "TEMPLATE.json"]
        self.assertTrue(files, "no deliveries at all?")
        for f in files:
            with self.subTest(f):
                m = mf.load(os.path.join(ddir, f))
                self.assertEqual(mf.validate(m), [])

    def test_ids_unique(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ddir = os.path.join(root, "deliveries")
        ids = []
        for f in os.listdir(ddir):
            if f.endswith(".json") and f != "TEMPLATE.json":
                ids.append(mf.load(os.path.join(ddir, f))["id"])
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
