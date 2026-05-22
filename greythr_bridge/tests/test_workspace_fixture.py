"""
Offline validation of the greytHR Workspace fixture.

These tests parse fixtures/workspace.json directly — no Frappe runtime
needed. They protect against:
  - JSON syntax errors (trailing commas, missing brackets)
  - Drift between shortcut URLs and the custom fields they reference
  - Card-count mismatch with the spec
  - Module-filter mismatch with hooks.py
"""
import json
import os
import re
import unittest


FIXTURE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "workspace.json")
)
CUSTOM_FIELD_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "custom_field.json")
)
HOOKS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "hooks.py")
)


def _load_workspace():
    with open(FIXTURE_PATH) as f:
        data = json.load(f)
    assert isinstance(data, list) and len(data) == 1, \
        "workspace.json must be a single-element JSON array"
    return data[0]


def _load_custom_fields():
    with open(CUSTOM_FIELD_PATH) as f:
        return json.load(f)


class TestWorkspaceFixture(unittest.TestCase):
    """Validate greythr_bridge/fixtures/workspace.json against the spec."""

    def test_fixture_file_exists(self):
        self.assertTrue(os.path.exists(FIXTURE_PATH),
                        f"Missing fixture: {FIXTURE_PATH}")

    def test_json_parses_cleanly(self):
        _load_workspace()

    def test_required_top_level_fields_present(self):
        ws = _load_workspace()
        for key in ("doctype", "name", "module", "app", "public", "shortcuts"):
            self.assertIn(key, ws, f"Workspace missing required field: {key}")
        self.assertEqual(ws["doctype"], "Workspace")
        self.assertEqual(ws["name"], "greytHR")
        self.assertEqual(ws["module"], "greytHR")
        self.assertEqual(ws["app"], "greythr_bridge",
                         "Frappe v16 requires `app` on Workspace, else the "
                         "'Removing orphan Workspaces' migrate step deletes it.")
        self.assertEqual(ws["public"], 1)

    def test_exactly_15_shortcuts(self):
        ws = _load_workspace()
        shortcuts = ws.get("shortcuts", [])
        self.assertEqual(len(shortcuts), 15,
                         f"Expected 15 shortcuts (per spec §3), got {len(shortcuts)}")

    def test_every_shortcut_has_label_and_url(self):
        ws = _load_workspace()
        for i, sc in enumerate(ws["shortcuts"]):
            self.assertTrue(sc.get("label"), f"Shortcut {i} missing label")
            self.assertTrue(sc.get("url"), f"Shortcut {i} ({sc.get('label')}) missing url")
            self.assertTrue(sc["url"].startswith("/app/"),
                            f"Shortcut {i} url must start with /app/: {sc['url']}")

    # Frappe v15/v16 Workspace Shortcut child-table `type` enum.
    # Anything outside this set causes the workspace insert to roll back silently.
    _VALID_SHORTCUT_TYPES = {"DocType", "Report", "Page", "Dashboard Chart"}

    def test_every_shortcut_type_is_valid_enum(self):
        """Frappe rejects shortcuts with `type` outside the allowed enum
        (no `URL` type exists). Validation failure rolls back the whole
        Workspace insert silently — caught us once already."""
        ws = _load_workspace()
        for i, sc in enumerate(ws["shortcuts"]):
            self.assertIn(
                sc.get("type"), self._VALID_SHORTCUT_TYPES,
                f"Shortcut {i} ({sc.get('label')}) has invalid type "
                f"{sc.get('type')!r}. Allowed: {sorted(self._VALID_SHORTCUT_TYPES)}"
            )

    def test_doctype_shortcuts_have_link_to(self):
        """When `type` is `DocType`, the `link_to` field is required by
        Frappe's child-table validator. The explicit `url` field overrides
        the click destination but doesn't relax this requirement."""
        ws = _load_workspace()
        for i, sc in enumerate(ws["shortcuts"]):
            if sc.get("type") == "DocType":
                self.assertTrue(
                    sc.get("link_to"),
                    f"Shortcut {i} ({sc.get('label')}) has type=DocType "
                    f"but no link_to — Frappe will reject this."
                )

    # Phase A custom fields created via the live-site UI but never round-tripped
    # back to fixtures/custom_field.json. They exist on the live site and are
    # used by the Monitor cards, but the test can't see them. Remove entries
    # from this allowlist as the fields get added to the fixture.
    _PHASE_A_LIVE_ONLY_FIELDS = {
        "custom_zoho_sign_request_id",
        "custom_zoho_sign_signed_at",
    }

    def test_custom_field_urls_reference_real_fields(self):
        """Any URL referencing a custom_* field must match a fieldname
        defined in fixtures/custom_field.json — catches rename drift."""
        ws = _load_workspace()
        custom_fields = _load_custom_fields()
        known_fieldnames = {d["fieldname"] for d in custom_fields if "fieldname" in d}
        allowed = known_fieldnames | self._PHASE_A_LIVE_ONLY_FIELDS

        url_field_pattern = re.compile(r"custom_[a-z0-9_]+")
        for sc in ws["shortcuts"]:
            for referenced in url_field_pattern.findall(sc["url"]):
                self.assertIn(
                    referenced, allowed,
                    f"Shortcut '{sc['label']}' references unknown custom field "
                    f"'{referenced}' — was it renamed in custom_field.json? "
                    f"(If it's a live-only Phase A field, add it to "
                    f"_PHASE_A_LIVE_ONLY_FIELDS.)"
                )

    def test_no_content_blob(self):
        """Per spec §5.1: omit `content` so Frappe auto-generates layout
        from shortcuts[] order. Including it courts drift."""
        ws = _load_workspace()
        self.assertNotIn("content", ws,
                         "Do not include `content` field — Frappe auto-generates it.")

    def test_hooks_fixtures_list_includes_workspace(self):
        """hooks.py fixtures list must include a Workspace entry filtered
        to module=greytHR — otherwise migrate won't load the fixture."""
        with open(HOOKS_PATH) as f:
            hooks_source = f.read()
        self.assertRegex(
            hooks_source,
            r'"dt"\s*:\s*"Workspace"[\s\S]*?"module"[\s\S]*?"greytHR"',
            "hooks.py fixtures list must include "
            "{'dt': 'Workspace', 'filters': [['module', '=', 'greytHR']]}"
        )


if __name__ == "__main__":
    unittest.main()
