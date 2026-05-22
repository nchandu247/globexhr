"""
Offline validation of the greytHR Workspace definition.

Per Frappe v16 convention, the Workspace lives in the per-module folder:
    greythr_bridge/greythr/workspace/greythr/greythr.json

NOT in fixtures/. Shipping via fixtures triggers Frappe's "Removing orphan
Workspaces" step at the end of migrate, which deletes the record.

These tests run offline (no Frappe runtime) and protect against:
  - JSON syntax errors (trailing commas, missing brackets)
  - Drift between shortcut URLs and the custom fields they reference
  - Card-count mismatch with the spec
  - Frappe v16 validator violations (invalid shortcut `type`, missing
    `link_to`, missing top-level `app`)
  - Accidentally re-adding the workspace to hooks.py fixtures (which
    would re-trigger orphan deletion)
"""
import json
import os
import re
import unittest


WORKSPACE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..",
                 "greythr", "workspace", "greythr", "greythr.json")
)
CUSTOM_FIELD_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "custom_field.json")
)
HOOKS_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "hooks.py")
)
OLD_FIXTURE_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "fixtures", "workspace.json")
)


def _load_workspace():
    with open(WORKSPACE_PATH) as f:
        data = json.load(f)
    assert isinstance(data, dict), \
        "Per-module workspace JSON must be a single dict (not a list)"
    return data


def _load_custom_fields():
    with open(CUSTOM_FIELD_PATH) as f:
        return json.load(f)


class TestWorkspaceDefinition(unittest.TestCase):
    """Validate greythr_bridge/greythr/workspace/greythr/greythr.json."""

    def test_workspace_file_in_per_module_location(self):
        """Workspace MUST live in <module>/workspace/<name>/<name>.json
        per Frappe v16 convention. fixtures/workspace.json is wrong and
        triggers orphan-removal."""
        self.assertTrue(os.path.exists(WORKSPACE_PATH),
                        f"Missing workspace at {WORKSPACE_PATH}")
        self.assertFalse(os.path.exists(OLD_FIXTURE_PATH),
                         f"Old fixture path still exists: {OLD_FIXTURE_PATH} "
                         f"— delete it. Frappe's orphan-removal will kill it.")

    def test_json_parses_cleanly_as_dict(self):
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

    _VALID_SHORTCUT_TYPES = {"DocType", "Report", "Page", "Dashboard Chart"}

    def test_every_shortcut_type_is_valid_enum(self):
        """Frappe rejects shortcuts with `type` outside the allowed enum
        (no `URL` type exists). Validation failure rolls back the whole
        Workspace insert silently."""
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
    # used by the Monitor cards, but the test can't see them.
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

    def test_content_present_and_well_formed(self):
        """v4 correction: `content` IS required for the workspace to render.
        Frappe v16 only auto-generates `content` when saved via the in-browser
        editor — file-loaded workspaces have null content and render as stuck
        skeleton placeholders. The renderer code is `editor.render({blocks:
        this.content || []})` — null content → empty editor → never resolves."""
        ws = _load_workspace()
        self.assertIn("content", ws,
                      "`content` field is required; without it the page is "
                      "stuck on skeleton loaders.")
        # `content` is stored as a stringified JSON array
        self.assertIsInstance(ws["content"], str,
                              "`content` must be a string (stringified JSON).")
        content = json.loads(ws["content"])
        self.assertIsInstance(content, list,
                              "`content` must parse as a JSON array of widget dicts.")
        self.assertGreater(len(content), 0, "`content` array must not be empty.")

    _VALID_WIDGET_TYPES = {
        "header", "shortcut", "card", "chart", "number_card",
        "quick_list", "spacer", "paragraph", "onboarding",
    }

    def test_content_widget_shape(self):
        """Every widget in `content` must have id, type (from valid enum),
        and data with at least a `col` value."""
        ws = _load_workspace()
        content = json.loads(ws["content"])
        seen_ids = set()
        for i, w in enumerate(content):
            self.assertIn("id", w, f"Widget {i} missing id")
            self.assertIn("type", w, f"Widget {i} missing type")
            self.assertIn("data", w, f"Widget {i} missing data")
            self.assertNotIn(w["id"], seen_ids,
                             f"Widget {i} has duplicate id {w['id']}")
            seen_ids.add(w["id"])
            self.assertIn(w["type"], self._VALID_WIDGET_TYPES,
                          f"Widget {i} has invalid type {w['type']!r}. "
                          f"Allowed: {sorted(self._VALID_WIDGET_TYPES)}")
            self.assertIn("col", w["data"],
                          f"Widget {i} ({w['type']}) data missing `col`")

    def test_content_shortcut_names_match_shortcut_labels(self):
        """Every `shortcut`-type widget in `content` must reference a
        `shortcut_name` that exactly matches a `label` in the `shortcuts[]`
        child table. Mismatches produce silent empty cards on the page."""
        ws = _load_workspace()
        content = json.loads(ws["content"])
        shortcut_labels = {s["label"] for s in ws["shortcuts"]}
        referenced = {
            w["data"].get("shortcut_name")
            for w in content if w["type"] == "shortcut"
        }
        unmatched = referenced - shortcut_labels
        self.assertFalse(
            unmatched,
            f"content widgets reference unknown shortcuts: {unmatched}. "
            f"Every shortcut_name must match a shortcuts[].label exactly."
        )
        unused = shortcut_labels - referenced
        self.assertFalse(
            unused,
            f"shortcuts[] has labels not referenced in content: {unused}. "
            f"They won't render on the page. Add a shortcut widget to content."
        )

    def test_hooks_fixtures_list_does_NOT_include_workspace(self):
        """Workspace must NOT be in hooks.py fixtures list. Shipping via
        fixtures causes Frappe to insert the record then delete it in
        the same migrate via 'Removing orphan Workspaces'."""
        with open(HOOKS_PATH) as f:
            hooks_source = f.read()
        self.assertNotRegex(
            hooks_source,
            r'"dt"\s*:\s*"Workspace"',
            "Remove the {'dt': 'Workspace', ...} entry from hooks.py. "
            "Workspaces use per-module folder convention, not fixtures."
        )


if __name__ == "__main__":
    unittest.main()
