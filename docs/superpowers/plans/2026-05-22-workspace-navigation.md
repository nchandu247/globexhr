# greytHR Workspace Navigation Hub — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Frappe Workspace fixture (`greytHR`) as a single atomic commit, giving HR users a one-click sidebar entry that surfaces all 8 letter trigger flows + integration utilities + filtered monitor views.

**Architecture:** Hand-written Workspace JSON fixture loaded via the `fixtures` hook on `bench migrate`. 15 shortcut cards across 6 lifecycle groups. URL-based pre-fill (`?field=value`) for new-doc actions and JSON-encoded operator arrays for list-view filters. No `content` blob — Frappe auto-generates one from the `shortcuts[]` array. No Python at runtime — the only Python is in the offline JSON-validation test.

**Tech Stack:** Frappe v16, Python 3.12 for tests (pytest), Frappe fixture loader, JSON.

**Spec reference:** `docs/superpowers/specs/2026-05-22-workspace-navigation-design.md` (commit `ed78cc9`).

---

## File Structure

| File | Status | Purpose |
|---|---|---|
| `greythr_bridge/fixtures/workspace.json` | **create** | Single Workspace record with 15 shortcuts |
| `greythr_bridge/hooks.py` | modify (lines 10-28) | Add `Workspace` to the `fixtures` list |
| `greythr_bridge/tests/test_workspace_fixture.py` | **create** | 8 offline JSON-validation tests |
| `CHANGELOG.md` | modify (append) | One paragraph describing the workspace |

No new directories. No new Python source under `greythr_bridge/` (the test file is the only `.py` added).

---

## Task 1: Write the failing JSON-validation tests (TDD)

**Files:**
- Create: `greythr_bridge/tests/test_workspace_fixture.py`

The test file checks the fixture exists, parses, has 15 shortcuts, all URLs reference real fields, and the module filter matches `hooks.py`. Tests fail until the JSON file is created.

- [ ] **Step 1: Create the test file with all 8 assertions**

Write `greythr_bridge/tests/test_workspace_fixture.py`:

```python
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
        # Will raise json.JSONDecodeError if malformed
        _load_workspace()

    def test_required_top_level_fields_present(self):
        ws = _load_workspace()
        for key in ("doctype", "name", "module", "public", "shortcuts"):
            self.assertIn(key, ws, f"Workspace missing required field: {key}")
        self.assertEqual(ws["doctype"], "Workspace")
        self.assertEqual(ws["name"], "greytHR")
        self.assertEqual(ws["module"], "greytHR")
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

    def test_custom_field_urls_reference_real_fields(self):
        """Any URL referencing a custom_* field must match a fieldname
        defined in fixtures/custom_field.json — catches rename drift."""
        ws = _load_workspace()
        custom_fields = _load_custom_fields()
        known_fieldnames = {d["fieldname"] for d in custom_fields if "fieldname" in d}

        # Extract every "custom_*" token appearing in any shortcut URL
        url_field_pattern = re.compile(r"custom_[a-z0-9_]+")
        for sc in ws["shortcuts"]:
            for referenced in url_field_pattern.findall(sc["url"]):
                self.assertIn(
                    referenced, known_fieldnames,
                    f"Shortcut '{sc['label']}' references unknown custom field "
                    f"'{referenced}' — was it renamed in custom_field.json?"
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
        # Look for a fixtures entry mentioning Workspace + greytHR module
        self.assertRegex(
            hooks_source,
            r'"dt"\s*:\s*"Workspace".*?"module".*?"greytHR"',
            "hooks.py fixtures list must include "
            "{'dt': 'Workspace', 'filters': [['module', '=', 'greytHR']]}"
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest greythr_bridge/tests/test_workspace_fixture.py -v`

Expected: All 8 tests **FAIL** (or error) — fixture file does not exist yet, and hooks.py doesn't have the Workspace entry. Specifically you'll see `FileNotFoundError` on the loaders.

This is the red-green-refactor "RED" state. Do **not** commit yet.

---

## Task 2: Create the workspace.json fixture

**Files:**
- Create: `greythr_bridge/fixtures/workspace.json`

Hand-author the JSON with all 15 shortcuts. Order matches the lifecycle groups from spec §3 (Onboarding → Compensation → Recognition → Exit → Operations → Monitor). Frappe renders shortcuts in array order; the section headers are conceptual (we omit `content` so Frappe auto-lays-out as one flowing grid of tiles).

- [ ] **Step 1: Write the fixture file**

Create `greythr_bridge/fixtures/workspace.json`:

```json
[
 {
  "doctype": "Workspace",
  "name": "greytHR",
  "title": "greytHR",
  "label": "greytHR",
  "module": "greytHR",
  "public": 1,
  "is_hidden": 0,
  "icon": "mail",
  "sequence_id": 50,
  "shortcuts": [
   {
    "type": "DocType",
    "link_to": "Job Offer",
    "label": "New Employee Offer",
    "color": "Blue",
    "url": "/app/job-offer/new?custom_offer_type=Employee"
   },
   {
    "type": "DocType",
    "link_to": "Job Offer",
    "label": "New Consultant Offer",
    "color": "Blue",
    "url": "/app/job-offer/new?custom_offer_type=Consultant"
   },
   {
    "type": "DocType",
    "link_to": "Job Offer",
    "label": "New Intern Offer",
    "color": "Blue",
    "url": "/app/job-offer/new?custom_offer_type=Intern"
   },
   {
    "type": "DocType",
    "link_to": "Salary Structure Assignment",
    "label": "New Salary Revision",
    "color": "Green",
    "url": "/app/salary-structure-assignment/new?custom_send_increment_letter=1"
   },
   {
    "type": "DocType",
    "link_to": "Employee",
    "label": "Generate Promotion Letter",
    "color": "Yellow",
    "url": "/app/employee"
   },
   {
    "type": "DocType",
    "link_to": "Employee",
    "label": "Generate Service Certificate",
    "color": "Yellow",
    "url": "/app/employee?status=Active"
   },
   {
    "type": "DocType",
    "link_to": "Employee Separation",
    "label": "New Separation (Experience / Relieving)",
    "color": "Red",
    "url": "/app/employee-separation/new?custom_send_experience_letter=1&custom_send_relieving_letter=1"
   },
   {
    "type": "URL",
    "label": "greytHR Settings",
    "color": "Grey",
    "url": "/app/greythr-settings"
   },
   {
    "type": "DocType",
    "link_to": "greytHR Sync Log",
    "label": "Sync Logs",
    "color": "Grey",
    "url": "/app/greythr-sync-log"
   },
   {
    "type": "DocType",
    "link_to": "greytHR Employee Mapping",
    "label": "Employee Mappings",
    "color": "Grey",
    "url": "/app/greythr-employee-mapping"
   },
   {
    "type": "DocType",
    "link_to": "Error Log",
    "label": "Error Log (greytHR)",
    "color": "Grey",
    "url": "/app/error-log?title=%5B%22like%22%2C%22greytHR%25%22%5D"
   },
   {
    "type": "DocType",
    "link_to": "Job Offer",
    "label": "Pending Signatures",
    "color": "Orange",
    "url": "/app/job-offer?custom_zoho_sign_request_id=%5B%22is%22%2C%22set%22%5D&custom_zoho_sign_signed_at=%5B%22is%22%2C%22not+set%22%5D"
   },
   {
    "type": "DocType",
    "link_to": "Job Offer",
    "label": "Recently Signed",
    "color": "Green",
    "url": "/app/job-offer?custom_zoho_sign_signed_at=%5B%22is%22%2C%22set%22%5D"
   },
   {
    "type": "DocType",
    "link_to": "greytHR Sync Log",
    "label": "Sync Failures",
    "color": "Red",
    "url": "/app/greythr-sync-log?status=Failed"
   },
   {
    "type": "DocType",
    "link_to": "Error Log",
    "label": "Letter Errors",
    "color": "Red",
    "url": "/app/error-log?title=%5B%22like%22%2C%22%25Letter%25%22%5D"
   }
  ]
 }
]
```

- [ ] **Step 2: Validate the JSON parses**

Run: `python -c "import json; json.load(open('greythr_bridge/fixtures/workspace.json'))"`

Expected: no output, exit code 0. If you see a `JSONDecodeError`, fix the trailing comma / unbalanced bracket.

- [ ] **Step 3: Re-run the test suite**

Run: `python -m pytest greythr_bridge/tests/test_workspace_fixture.py -v`

Expected: **7 PASS, 1 FAIL** — only `test_hooks_fixtures_list_includes_workspace` still fails (hooks.py not yet updated). All other tests should pass now.

If any other test fails: re-read the failure message and fix the JSON. Common issues:
- Forgot a shortcut → `test_exactly_15_shortcuts` fails
- Misspelled `custom_offer_type` → `test_custom_field_urls_reference_real_fields` fails
- Accidentally included `"content": "..."` → `test_no_content_blob` fails

Do not commit yet.

---

## Task 3: Wire the fixture into hooks.py

**Files:**
- Modify: `greythr_bridge/hooks.py` lines 23-28

Add one new entry to the `fixtures` list so `bench migrate` picks up `workspace.json`.

- [ ] **Step 1: Edit hooks.py**

Use the Edit tool to replace the existing Client Script entry with Client Script + Workspace:

**Old:**
```python
    # Phase B — Client Scripts for Employee form buttons (Promotion + Service Cert)
    {
        "dt": "Client Script",
        "filters": [["module", "=", "greytHR"]],
    },
]
```

**New:**
```python
    # Phase B — Client Scripts for Employee form buttons (Promotion + Service Cert)
    {
        "dt": "Client Script",
        "filters": [["module", "=", "greytHR"]],
    },
    # Navigation — left-sidebar workspace with letter + ops shortcuts
    {
        "dt": "Workspace",
        "filters": [["module", "=", "greytHR"]],
    },
]
```

- [ ] **Step 2: Run the test suite (full suite, not just workspace tests)**

Run: `python -m pytest greythr_bridge/tests/ -v 2>&1 | tail -20`

Expected: **122 passed, 3 skipped** (previous 114 + 8 new). All previous tests still pass; all 8 workspace tests pass.

If any test fails:
- `test_hooks_fixtures_list_includes_workspace` still fails → regex didn't match; check you put the Workspace dict on its own line with `"dt": "Workspace"` and `"greytHR"` both present
- A previously-passing test fails → you broke something in hooks.py syntax; re-read the diff

Do not commit yet.

---

## Task 4: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md` (append at end)

- [ ] **Step 1: Append the workspace entry**

Use the Edit tool to add at the very end of `CHANGELOG.md` (after the existing Phase B section):

```markdown

---

## [Unreleased] — Workspace Navigation (2026-05-22)

### Workspace — left-sidebar navigation hub

- ✅ **`greythr_bridge/fixtures/workspace.json`** — single Workspace record `greytHR`, auto-installed on `bench migrate` via fixtures filter `module=greytHR`. 15 shortcut cards arranged by employee lifecycle:
  - **Onboarding** (3): New Employee / Consultant / Intern Offer — each opens a new Job Offer with `custom_offer_type` pre-selected via URL param
  - **Compensation** (1): New Salary Revision — opens new SSA with the increment-letter checkbox pre-ticked
  - **Recognition** (2): Promotion Letter, Service Certificate — link to the Employee list; per-employee Client Script buttons handle the trigger
  - **Exit** (1): New Separation — opens new Employee Separation with both Experience and Relieving checkboxes pre-ticked
  - **Operations** (4): greytHR Settings, Sync Logs, Employee Mappings, Error Log (filtered to greytHR titles)
  - **Monitor** (4): Pending Signatures, Recently Signed, Sync Failures, Letter Errors — all filtered list views via URL-encoded operator arrays
- ✅ **`hooks.py`** — added `{"dt": "Workspace", "filters": [["module", "=", "greytHR"]]}` to the fixtures list
- ✅ **`tests/test_workspace_fixture.py`** — 8 offline validation tests: JSON parses, 15 shortcuts present, every `custom_*` URL token references a fieldname in `custom_field.json`, no `content` blob, hooks.py fixtures list updated
- ✅ Test suite: **122 passing** (was 114), 3 skipped
- ⬜ **Live-site verification (post-deploy):** Fetch + Update Bench + Migrate; refresh `/app`; confirm `greytHR` sidebar entry appears with 15 cards and each card lands on the expected URL.

**Workspace authoring caveat:** This workspace is shipped as a fixture and is system-managed. Edits made via the in-browser Workspace Editor will be overwritten on the next `bench migrate`. All future workspace changes should go via PR to `fixtures/workspace.json`.
```

- [ ] **Step 2: No test re-run needed**

CHANGELOG is documentation only — no tests reference it.

---

## Task 5: Final pre-commit check + commit + push

- [ ] **Step 1: Full test suite (sanity)**

Run: `python -m pytest greythr_bridge/tests/ 2>&1 | tail -5`

Expected: `122 passed, 3 skipped`.

- [ ] **Step 2: Re-validate the JSON one more time**

Run: `python -c "import json; data = json.load(open('greythr_bridge/fixtures/workspace.json')); assert len(data) == 1; assert len(data[0]['shortcuts']) == 15; print('OK: 15 shortcuts, JSON valid')"`

Expected: `OK: 15 shortcuts, JSON valid`

- [ ] **Step 3: Review git status**

Run: `git status`

Expected to see:
- `modified: CHANGELOG.md`
- `modified: greythr_bridge/hooks.py`
- `new file: greythr_bridge/fixtures/workspace.json`
- `new file: greythr_bridge/tests/test_workspace_fixture.py`

If you see any unrelated file (e.g., the untracked `logo.png` at repo root), **do not** add it.

- [ ] **Step 4: Stage exactly the 4 files and commit**

Run:
```bash
git add CHANGELOG.md greythr_bridge/hooks.py greythr_bridge/fixtures/workspace.json greythr_bridge/tests/test_workspace_fixture.py
```

Then commit with a HEREDOC message:
```bash
git commit -m "$(cat <<'EOF'
Workspace: greytHR navigation hub (15-card sidebar, fixture-driven)

Adds a left-sidebar Workspace entry "greytHR" auto-installed on
bench migrate via the fixtures hook. 15 shortcuts arranged by
employee lifecycle (Onboarding/Compensation/Recognition/Exit/
Operations/Monitor), each linking to either a pre-filled new-doc
form, a filtered list view, or a Single doctype.

- workspace.json: hand-authored, no content blob (Frappe auto-
  generates layout from shortcuts[] order)
- hooks.py: one new fixtures entry filtered to module=greytHR
- test_workspace_fixture.py: 8 offline JSON-validation tests
  (parses, 15 shortcuts, custom_* URL tokens match custom_field.json,
  no content blob, hooks.py wiring present)

Test suite: 122 passing, 3 skipped. No runtime Python changes.

Spec: docs/superpowers/specs/2026-05-22-workspace-navigation-design.md

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Expected: commit hash printed, no pre-commit hook errors.

- [ ] **Step 5: Push to origin**

Run: `git push origin main`

Expected: push succeeds (`origin/main` updated).

- [ ] **Step 6: Hand off to user**

Output a final message:
> Workspace shipped as commit `<hash>`. Deploy steps on Frappe Cloud:
> 1. Bench → Fetch → Update Bench → Migrate
> 2. Refresh `/app` in browser
> 3. Verify left sidebar shows `greytHR` entry with 15 cards
> 4. Click one card from each group and verify it lands on the right URL

---

## Self-review checklist (done before this plan was published)

**Spec coverage:** Every spec section has a task:
- §3 Layout → Task 2 (workspace.json with 15 shortcuts in lifecycle order)
- §4 Card behaviour → Task 2 (URLs in workspace.json)
- §5 Fixture mechanics → Task 2 (workspace.json) + Task 3 (hooks.py)
- §6 Deploy path → Task 5 Step 6 (hand-off message)
- §7 Failure modes (rename drift) → Task 1 `test_custom_field_urls_reference_real_fields`
- §8 Definition of done → Task 5 Step 6 verification checklist
- §10 Tests → Task 1 (8 assertions match spec's 8)
- §11 Implementation order → Task structure matches

**Placeholder scan:** No "TBD", no "TODO", every code block is complete and runnable.

**Type consistency:** Field names verified against `custom_field.json` (Phase B fields confirmed in spec §3 Appendix A and test):
- `custom_offer_type`, `custom_send_increment_letter`, `custom_send_experience_letter`, `custom_send_relieving_letter` — all present in `fixtures/custom_field.json` (Phase B commit `703110b`)
- `custom_zoho_sign_request_id`, `custom_zoho_sign_signed_at` — Phase A fields, present in existing fixtures
- Status field on `greytHR Sync Log` accepts value `Failed` — verified in `tasks/pull_employees.py:99` and `tasks/pull_salary_structures.py:89`
