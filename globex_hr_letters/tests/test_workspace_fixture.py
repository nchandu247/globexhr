"""
Guards for the HR Letters Workspace definition.

Per Frappe v16 convention, the Workspace lives in the per-module folder:
    globex_hr_letters/hr_letters/workspace/hr_letters/hr_letters.json

NOT in fixtures/. Shipping via fixtures triggers Frappe's "Removing orphan
Workspaces" step at the end of migrate, which deletes the record.

These tests run offline (no Frappe runtime) and protect against the four
silent-failure modes seen in the past — each makes the workspace simply not
render, with no error:

  1. Wrong file location
  2. Missing "app" key — v16's workspace loader skips records without it
  3. Missing/empty "content" blob — the page renders blank
  4. Invalid shortcut "type" — the sidebar entry disappears
"""
import json
import os

WORKSPACE_PATH = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__), "..",
        "hr_letters", "workspace", "hr_letters", "hr_letters.json",
    )
)

VALID_SHORTCUT_TYPES = {"DocType", "Report", "Page", "Dashboard", "URL"}


def _load():
    with open(WORKSPACE_PATH, encoding="utf-8") as f:
        return json.load(f)


def test_workspace_file_in_per_module_location():
    """v16 loads public workspaces from the per-module folder, not fixtures."""
    assert os.path.exists(WORKSPACE_PATH), (
        f"Workspace JSON missing at {WORKSPACE_PATH} — shipping it as a "
        "fixture instead gets it deleted by the orphan-Workspace purge."
    )


def test_json_parses_cleanly_as_dict():
    ws = _load()
    assert isinstance(ws, dict)


def test_required_top_level_fields_present():
    ws = _load()
    for key in ("name", "title", "label", "module", "app", "content", "shortcuts"):
        assert key in ws and ws[key] not in ("", None), f"missing/empty key: {key}"
    assert ws["name"] == "HR Letters"
    assert ws["module"] == "HR Letters"
    assert ws["app"] == "globex_hr_letters"
    assert ws["public"] == 1


def test_content_widget_shape():
    """content is a JSON-encoded list of {id, type, data} widget dicts."""
    ws = _load()
    widgets = json.loads(ws["content"])
    assert isinstance(widgets, list) and widgets
    for w in widgets:
        assert set(w.keys()) >= {"id", "type", "data"}, f"bad widget: {w}"
        assert w["type"] in ("header", "shortcut", "card", "spacer"), w["type"]


def test_every_shortcut_type_is_valid_enum():
    ws = _load()
    for sc in ws["shortcuts"]:
        assert sc.get("type") in VALID_SHORTCUT_TYPES, f"invalid type: {sc}"


def test_doctype_shortcuts_have_link_to():
    ws = _load()
    for sc in ws["shortcuts"]:
        if sc["type"] == "DocType":
            assert sc.get("link_to"), f"DocType shortcut missing link_to: {sc}"


def test_every_shortcut_has_label_and_url():
    ws = _load()
    for sc in ws["shortcuts"]:
        assert sc.get("label"), f"shortcut missing label: {sc}"
        assert sc.get("url"), f"shortcut missing url: {sc}"


def test_content_shortcuts_match_shortcut_records():
    """Every shortcut widget in the content blob must reference a shortcut
    record by label — a dangling name renders as an empty card."""
    ws = _load()
    labels = {sc["label"] for sc in ws["shortcuts"]}
    widgets = json.loads(ws["content"])
    for w in widgets:
        if w["type"] == "shortcut":
            name = w["data"].get("shortcut_name")
            assert name in labels, f"content references unknown shortcut: {name}"


def test_core_letter_shortcuts_present():
    ws = _load()
    labels = {sc["label"] for sc in ws["shortcuts"]}
    for expected in ("New HR Letter", "Letter Types", "HR Letters Settings",
                     "Pending Signatures"):
        assert expected in labels, f"missing shortcut: {expected}"


def test_no_greythr_references_remain():
    """The workspace must not reference retired greytHR doctypes or sync."""
    raw = open(WORKSPACE_PATH, encoding="utf-8").read()
    assert "greytHR" not in raw and "greythr" not in raw
