"""tube-eye — tests for src/preflight.py, the pc-eye handshake.

These are the checks that decide whether a posting shift may start. Every bad
state here is one that has actually stopped a real shift or burned a real
click: a dead tunnel (the URL changes every start.bat), a demo server that
records actions instead of doing them, eyes and hand in two pixel spaces, and
a 600 MB download that must be *waited* for rather than re-fetched.

The pc-eye side is a protocol-faithful stub (tests/fake_pc_eye.py) because the
real server needs a display; the contract being tested is the HTTP one.

Run: python3 tests/run_all.py
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))
sys.path.insert(0, HERE)

import preflight  # noqa: E402
from fake_pc_eye import FakePcEye  # noqa: E402

TOKEN = "0123456789abcdef0123456789abcdef"


def by_name(checks, name):
    for c in checks:
        if c.name == name:
            return c
    raise AssertionError(f"no check named {name!r} in {[c.name for c in checks]}")


def verdict_code(checks):
    return preflight.verdict(checks)[0]


class TestLinkGood(unittest.TestCase):
    """The state the human hands over when everything is right."""

    def test_full_green_with_act(self):
        with FakePcEye() as pc:
            checks, facts = preflight.run(pc.url, pc.token, do_act=True)
            # loopback http is a warning by design, never a failure
            self.assertEqual(verdict_code(checks), 2, preflight.verdict(checks)[1])
            for name in ("url", "token", "state", "not-dry-run", "coord-space",
                         "capture", "selftest", "selftest-no-test-mode", "shot",
                         "shot-headers", "shot-changed"):
                self.assertTrue(by_name(checks, name).ok, name)
            self.assertTrue(by_name(checks, "act-move").ok)
            self.assertEqual(pc.moves, [{"action": "move", "x": 960, "y": 540}])

    def test_facts_carry_what_the_agent_needs_to_report(self):
        with FakePcEye() as pc:
            _checks, facts = preflight.run(pc.url, pc.token)
        link = facts["link"]
        self.assertEqual(link["version"], "1.0.3")
        self.assertEqual(link["screen"], [1920, 1080])
        self.assertIs(link["dry_run"], False)
        self.assertGreater(link["shot_bytes"], 1000)

    def test_act_is_not_performed_unless_asked(self):
        with FakePcEye() as pc:
            checks, _ = preflight.run(pc.url, pc.token)          # no do_act
            self.assertEqual(pc.moves, [], "preflight must not touch the mouse by default")
            self.assertTrue(by_name(checks, "act-move").skipped)


class TestLinkBad(unittest.TestCase):
    """Every one of these means: do not start the shift."""

    def test_dry_run_server_is_critical(self):
        with FakePcEye(dry_run=True) as pc:
            checks, _ = preflight.run(pc.url, pc.token)
        self.assertFalse(by_name(checks, "not-dry-run").ok)
        self.assertIn("dry_run is TRUE", by_name(checks, "not-dry-run").detail)
        self.assertEqual(verdict_code(checks), 1)

    def test_test_mode_flag_is_critical(self):
        with FakePcEye(dry_run=True) as pc:
            checks, _ = preflight.run(pc.url, pc.token)
        self.assertFalse(by_name(checks, "selftest-no-test-mode").ok)

    def test_coord_space_mismatch_is_critical(self):
        """The 2026-10-16 bug: 1920x1080 eyes, 1536x864 hand."""
        with FakePcEye(coord_consistent=False) as pc:
            checks, facts = preflight.run(pc.url, pc.token)
        self.assertFalse(by_name(checks, "coord-space").ok)
        self.assertIn("1536x864", by_name(checks, "coord-space").detail)
        self.assertEqual(verdict_code(checks), 1)
        self.assertIs(facts["link"]["coord_space"]["consistent"], False)

    def test_wrong_token_is_401_and_says_so(self):
        with FakePcEye() as pc:
            checks, _ = preflight.run(pc.url, "f" * 32)
        state = by_name(checks, "state")
        self.assertFalse(state.ok)
        self.assertIn("401", state.detail)
        self.assertIn("never guess", state.detail)

    def test_dead_tunnel_does_not_crash_and_explains(self):
        """A closed port is the commonest failure: trycloudflare rotates the URL."""
        checks, _ = preflight.run("http://127.0.0.1:1", TOKEN)   # nothing listens on 1
        state = by_name(checks, "state")
        self.assertFalse(state.ok)
        self.assertIn("cannot reach the PC", state.detail)
        self.assertIn("fresh URL", state.detail)
        self.assertEqual(verdict_code(checks), 1)

    def test_bad_scheme_refused_before_any_secret_leaves(self):
        checks, _ = preflight.run("pc.example.com", TOKEN)
        self.assertFalse(by_name(checks, "url").ok)
        self.assertIn("https://", by_name(checks, "url").detail)
        # and it stopped there: no network checks were attempted
        self.assertEqual([c.name for c in checks if c.name.startswith("shot")], [])

    def test_missing_token_refused(self):
        checks, _ = preflight.run("https://example.trycloudflare.com", "")
        self.assertFalse(by_name(checks, "token").ok)
        self.assertIn("PC_EYE_TOKEN", by_name(checks, "token").detail)

    def test_missing_shot_headers_is_critical(self):
        """Without X-Screen-Full/Sent the agent cannot convert what it sees to where it clicks."""
        with FakePcEye(send_shot_headers=False) as pc:
            checks, _ = preflight.run(pc.url, pc.token)
        self.assertFalse(by_name(checks, "shot-headers").ok)
        self.assertIn("cannot aim safely", by_name(checks, "shot-headers").detail)
        self.assertEqual(verdict_code(checks), 1)

    def test_waiting_mechanism_must_answer_304(self):
        with FakePcEye(honour_changed=False) as pc:
            checks, _ = preflight.run(pc.url, pc.token)
        self.assertFalse(by_name(checks, "shot-changed").ok)
        self.assertIn("expected 304", by_name(checks, "shot-changed").detail)

    def test_capture_failure_is_critical(self):
        with FakePcEye(capture_ok=False) as pc:
            checks, _ = preflight.run(pc.url, pc.token)
        self.assertFalse(by_name(checks, "capture").ok)
        self.assertEqual(verdict_code(checks), 1)

    def test_token_value_never_appears_in_the_report(self):
        with FakePcEye() as pc:
            checks, facts = preflight.run(pc.url, pc.token)
        blob = str([c.as_dict() for c in checks]) + str(facts)
        self.assertNotIn(pc.token, blob)


class TestQueue(unittest.TestCase):
    """The tube-eye half: is there really something to post next?"""

    def setUp(self):
        self.now = datetime(2026, 10, 28, 15, 30, tzinfo=timezone.utc)

    def test_queue_only_does_not_claim_the_link_was_proven(self):
        checks, facts = preflight.run(queue_only=True, now=self.now)
        _code, summary = preflight.verdict(checks, facts)
        self.assertIn("QUEUE OK", summary)
        self.assertNotIn("link proven", summary)

    def test_queue_only_reads_the_committed_plan(self):
        checks, facts = preflight.run(queue_only=True, now=self.now)
        self.assertTrue(by_name(checks, "queue").ok)
        self.assertEqual(facts["queue"]["next"]["delivery_id"], "d-0001")
        # and no network was attempted
        self.assertNotIn("link", facts)

    def test_past_only_plan_means_nothing_to_post(self):
        far = datetime(2030, 1, 1, tzinfo=timezone.utc)
        checks, _ = preflight.run(queue_only=True, now=far)
        self.assertFalse(by_name(checks, "queue").ok)
        self.assertIn("nothing to post", by_name(checks, "queue").detail)
        self.assertEqual(verdict_code(checks), 2)   # a warning, not a broken link

    def test_next_slot_is_the_earliest_future_one(self):
        checks, facts = preflight.run(queue_only=True, now=self.now)
        self.assertTrue(by_name(checks, "next-slot").ok)
        self.assertIn("in ", by_name(checks, "next-slot").detail)

    def test_plan_file_shape_is_what_poster_expects(self):
        checks, facts = preflight.run(queue_only=True, now=self.now)
        nxt = facts["queue"]["next"]
        for key in ("delivery_id", "title", "kind", "publish_at", "manifest"):
            self.assertIn(key, nxt)


if __name__ == "__main__":
    unittest.main()
