"""
Offline validation of hooks.py (scheduler + doc_events) and the
fixtures/client_script.json file.

Why these tests exist:
  - Scheduler cron strings are easy to silently misspell — the scheduler just
    no-ops if the string is invalid, so a typo goes unnoticed until someone
    notices stale data days later.
  - Client Scripts are JSON-encoded JS strings; broken JSON only surfaces on
    `bench migrate`. A schema check here catches it offline.
  - The 2026-05-24 cadence change (every 15 min → daily 6 AM IST + manual
    button) is exactly the kind of decision that's easy to accidentally revert.
    Pin it.
"""
import json
import os
import re
import unittest


HOOKS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "hooks.py")
)
CLIENT_SCRIPT_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..",
                 "fixtures", "client_script.json")
)


def _read_hooks():
    with open(HOOKS_PATH) as f:
        return f.read()


def _load_client_scripts():
    with open(CLIENT_SCRIPT_PATH) as f:
        return json.load(f)


class TestSchedulerCadence(unittest.TestCase):
    """The 2026-05-24 cadence change for pull_employees."""

    def test_pull_employees_runs_daily_not_every_15_min(self):
        """Sync is now daily at 6 AM IST. Cron-string '*/15 * * * *' would
        be a regression (used to be that, generated 96 calls/day, masked
        the 'sync claims success while doing nothing' bug for weeks)."""
        source = _read_hooks()

        # Negative: the 15-min cron must not be present
        self.assertNotIn(
            '"*/15 * * * *"', source,
            "pull_employees cron reverted to every 15 minutes. Manual button "
            "in workspace ('Sync from greytHR Now') replaces the high-frequency "
            "schedule. Keep the daily cadence."
        )

        # Positive: daily-6AM cron must point at pull_employees
        # Match the line that pairs the cron with the task name.
        pattern = re.compile(
            r'"0 6 \* \* \*"\s*:\s*\[\s*"greythr_bridge\.tasks\.pull_employees\.run"\s*\]'
        )
        self.assertRegex(
            source, pattern,
            "Expected daily 6 AM IST cron for pull_employees.run. "
            "Format: \"0 6 * * *\": [\"greythr_bridge.tasks.pull_employees.run\"]"
        )

    def test_pull_salary_structures_still_daily(self):
        """Salary sync was already daily — should not have changed."""
        source = _read_hooks()
        self.assertIn(
            '"greythr_bridge.tasks.pull_salary_structures.run"', source,
            "Salary structure sync task is missing from scheduler_events."
        )

    def test_stalled_signings_still_daily(self):
        source = _read_hooks()
        self.assertIn(
            '"greythr_bridge.tasks.stalled_signings.run"', source,
            "Stalled-signings daily check is missing from scheduler_events."
        )


class TestClientScriptShape(unittest.TestCase):
    """Validate fixtures/client_script.json: parses, required fields, expected
    scripts present."""

    def test_json_parses_as_list(self):
        scripts = _load_client_scripts()
        self.assertIsInstance(scripts, list, "client_script.json must be a list")
        self.assertGreater(len(scripts), 0, "client_script.json is empty")

    def test_every_script_has_required_fields(self):
        scripts = _load_client_scripts()
        required = {"doctype", "name", "dt", "view", "enabled",
                    "module", "script"}
        for i, s in enumerate(scripts):
            missing = required - set(s.keys())
            self.assertFalse(
                missing,
                f"Client Script {i} ({s.get('name')!r}) missing fields: {missing}"
            )
            self.assertEqual(s["doctype"], "Client Script")
            self.assertEqual(s["module"], "greytHR",
                             f"Client Script {i} ({s['name']!r}) must be in "
                             f"the greytHR module (so the hooks.py fixtures "
                             f"filter module=greytHR picks it up).")
            self.assertEqual(s["enabled"], 1)
            self.assertIn(s["view"], {"Form", "List", "Tree", "Report"},
                          f"Client Script {i} has invalid view {s['view']!r}")

    def test_sync_now_button_script_present(self):
        """The Sync Log list-view button (paired with the workspace shortcut
        'Sync from greytHR Now') is what gives HR control over manual sync
        cadence. Without it, HR can only trigger via the raw API URL.

        Uses startswith matching on 'greytHR Sync Log' + endswith 'Sync Now
        Button' to avoid Windows source-encoding fragility around the
        em-dash separator in the canonical name.
        """
        scripts = _load_client_scripts()
        sync_script = next(
            (s for s in scripts
             if s["name"].startswith("greytHR Sync Log")
             and s["name"].endswith("Sync Now Button")),
            None,
        )
        self.assertIsNotNone(
            sync_script,
            "Missing the greytHR Sync Log Sync Now Button Client Script. "
            "The manual-sync UI depends on it."
        )
        self.assertEqual(sync_script["dt"], "greytHR Sync Log")
        self.assertEqual(sync_script["view"], "List")

        body = sync_script["script"]
        # Script must call our whitelisted endpoint, not invent its own
        self.assertIn(
            "greythr_bridge.tasks.pull_employees.run_now", body,
            "Sync Now script must call the run_now endpoint."
        )
        # Script must include the confirm dialog (prevents accidental triggers)
        self.assertIn("frappe.confirm", body,
                      "Sync Now script must show a confirm dialog.")
        # Script must check role (HR Manager / System Manager only)
        self.assertIn("HR Manager", body,
                      "Sync Now script must gate by HR Manager role.")
        self.assertIn("System Manager", body,
                      "Sync Now script must gate by System Manager role.")
        # Auto-open via ?manual_sync=1 (workspace shortcut entry point)
        self.assertIn("manual_sync", body,
                      "Sync Now script must read ?manual_sync=1 query param "
                      "to auto-open the confirm dialog when arriving via the "
                      "workspace shortcut.")


if __name__ == "__main__":
    unittest.main()
