"""The generated timer is the difference between "runs for me" and "runs for you".

The docs used to hand the reader a plist with placeholders to substitute by
hand, so these tests assert that what we emit carries the real interpreter,
entrypoint, config path and log directory taken from the running process.
"""

import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import subscription_schedule, subscriptions


def _config(root: Path) -> dict:
    return {"_config_path": str(root / "chubby.yaml")}


def _args(**overrides):
    base = dict(
        subscriptions="",
        process_limit=3,
        interval_minutes=60,
        dry_run=False,
    )
    base.update(overrides)
    return types.SimpleNamespace(**base)


class SchedulePathsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def test_command_carries_real_paths_not_placeholders(self):
        paths = subscription_schedule.schedule_paths(_args(), _config(self.root))
        command = " ".join(paths["command"])
        self.assertNotIn("/absolute/path", command)
        self.assertNotIn("$", command)
        self.assertIn(str(Path(subscription_schedule.ENTRYPOINT)), command)
        self.assertIn(str(self.root / "chubby.yaml"), command)
        self.assertIn("tick", paths["command"])
        self.assertIn("--due", paths["command"])

    def test_logs_live_next_to_the_config(self):
        paths = subscription_schedule.schedule_paths(_args(), _config(self.root))
        self.assertEqual(paths["log_dir"], self.root / ".chubby" / "logs")
        self.assertEqual(paths["tick_log"], self.root / ".chubby" / "tick-log.jsonl")

    def test_explicit_subscriptions_path_is_forwarded(self):
        override = self.root / "elsewhere" / "subs.json"
        paths = subscription_schedule.schedule_paths(
            _args(subscriptions=str(override)), _config(self.root)
        )
        self.assertIn("--subscriptions", paths["command"])
        self.assertIn(str(override), paths["command"])

    def test_missing_config_path_is_refused(self):
        with self.assertRaises(subscription_schedule.ScheduleError):
            subscription_schedule.schedule_paths(_args(), {})


class UnitGenerationTest(unittest.TestCase):
    def setUp(self):
        self.paths = {
            "command": ["/usr/bin/python3", "/repo/tools/chubby.py", "subscribe", "tick", "--due"],
            "log_dir": Path("/repo/.chubby/logs"),
            "config_path": Path("/repo/chubby.yaml"),
            "tick_log": Path("/repo/.chubby/tick-log.jsonl"),
            "python": "/usr/bin/python3",
        }

    def test_launchd_plist_runs_the_command_directly(self):
        plist = subscription_schedule.build_launchd_plist(self.paths, interval_minutes=30)
        self.assertIn("<string>/usr/bin/python3</string>", plist)
        self.assertIn("<string>/repo/tools/chubby.py</string>", plist)
        self.assertIn("<integer>1800</integer>", plist)
        self.assertIn(str(self.paths["log_dir"] / "subscribe.err.log"), plist)
        # A shell wrapper is what broke under macOS TCC in an earlier iteration.
        self.assertNotIn("<string>/bin/bash</string>", plist)

    def test_systemd_units_pair_service_and_timer(self):
        units = subscription_schedule.build_systemd_units(self.paths, interval_minutes=30)
        self.assertEqual(
            sorted(units), sorted([subscription_schedule.SYSTEMD_SERVICE, subscription_schedule.SYSTEMD_TIMER])
        )
        service = units[subscription_schedule.SYSTEMD_SERVICE]
        timer = units[subscription_schedule.SYSTEMD_TIMER]
        self.assertIn("ExecStart=/usr/bin/python3 /repo/tools/chubby.py", service)
        self.assertIn("OnUnitActiveSec=30min", timer)
        self.assertIn("WantedBy=timers.target", timer)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "chubby.yaml").write_text("output_dir: output\n", encoding="utf-8")

    def test_interval_is_bounded(self):
        for value in (0, 4, 1441):
            with self.assertRaises(subscription_schedule.ScheduleError):
                subscription_schedule.install(_args(interval_minutes=value), _config(self.root))

    def test_dry_run_writes_nothing(self):
        with patch.object(subscription_schedule, "launchd_path", return_value=self.root / "x.plist"):
            code = subscription_schedule.install(
                _args(dry_run=True), _config(self.root)
            )
        self.assertEqual(code, 0)
        self.assertFalse((self.root / "x.plist").exists())


class StatusTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        (self.root / "chubby.yaml").write_text("output_dir: output\n", encoding="utf-8")
        self.tick_log = self.root / ".chubby" / "tick-log.jsonl"
        self.tick_log.parent.mkdir(parents=True)

    def test_status_reads_the_tick_log(self):
        rows = [
            {"ts": "2026-10-05T02:19:01Z", "due": 5, "healthy": 4, "unchanged": 1, "errors": 0, "processed": 0, "status": "ok"},
            {"ts": "2026-10-05T03:19:01Z", "due": 0, "healthy": 0, "unchanged": 0, "errors": 0, "processed": 0, "status": "lock_held"},
        ]
        self.tick_log.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
        entries = subscription_schedule._tail_tick_log(self.tick_log)
        self.assertEqual(len(entries), 2)
        self.assertIn("due=5", subscription_schedule._describe(entries[0]))
        self.assertIn("跳过", subscription_schedule._describe(entries[1]))

    def test_status_survives_a_missing_log(self):
        self.assertEqual(subscription_schedule._tail_tick_log(self.tick_log), [])

    def test_status_ignores_a_corrupt_line(self):
        self.tick_log.write_text('{"ts": "x", "status": "ok"}\nnot json\n', encoding="utf-8")
        self.assertEqual(len(subscription_schedule._tail_tick_log(self.tick_log)), 1)


class TickLogTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.document = Path(self.temporary.name).resolve() / ".chubby" / "subscriptions.json"
        self.document.parent.mkdir(parents=True)
        self.document.write_text("{}", encoding="utf-8")

    def read(self):
        rows = (self.document.parent / "tick-log.jsonl").read_text(encoding="utf-8").splitlines()
        return [json.loads(row) for row in rows]

    def test_counts_are_summarised_beside_the_config(self):
        summaries = [
            {"status": "healthy"},
            {"status": "healthy"},
            {"status": "unchanged"},
            {"status": "error"},
        ]
        subscriptions._write_tick_log(self.document, summaries, processed=2)
        entry = self.read()[0]
        self.assertEqual(
            (entry["due"], entry["healthy"], entry["unchanged"], entry["errors"], entry["processed"]),
            (4, 2, 1, 1, 2),
        )
        self.assertEqual(entry["status"], "ok")
        self.assertRegex(entry["ts"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def test_a_skipped_tick_is_recorded_rather_than_silent(self):
        subscriptions._write_tick_log(self.document, [], status="lock_held")
        entry = self.read()[0]
        self.assertEqual(entry["status"], "lock_held")
        self.assertEqual(entry["due"], 0)

    def test_entries_accumulate(self):
        subscriptions._write_tick_log(self.document, [], status="ok")
        subscriptions._write_tick_log(self.document, [], status="ok")
        self.assertEqual(len(self.read()), 2)


if __name__ == "__main__":
    unittest.main()
