# greytHR Workspace — Navigation Hub for All Letters + Operations

**Status:** Spec — awaiting user approval before implementation
**Date:** 2026-05-22
**Phase context:** Builds on Phase A (offer letter via WeasyPrint) + Phase B (7 additional letter types). No new letter functionality — pure navigation.

---

## 1. Goal

Give HR users a single sidebar entry (`greytHR`) that surfaces every letter trigger flow + integration utilities + monitoring views in one workspace, organised by employee lifecycle. Today these flows are scattered across the Job Offer / SSA / Employee Separation / Employee doctypes — discoverable only via global search or by memorising the right doctype.

**Out of scope:** new letter types, dashboards/charts, custom Vue pages, mobile app screens, public web pages.

---

## 2. Approach decision — Workspace fixture

Frappe-native **Workspace** doctype, shipped as a fixture (auto-installed on `bench migrate`, same mechanism that ships our 22 Custom Fields and 2 Client Scripts).

### Why not other approaches

| Approach | Why not |
|---|---|
| Custom Page (HTML/Vue) | Overkill for a navigation hub; loses Frappe's built-in permission gating; harder to maintain |
| Module Onboarding | Different feature (Form Tours / checklists), not a sidebar entry |
| Two workspaces (Letters + Ops) | Two sidebar entries for one app — clutter without benefit |
| Skip and rely on global search (Ctrl+G) | Users have to know what to search for — fails the discoverability test |

### Validation (research summary)

Independent research against Frappe v16 docs + GitHub issues + forum threads confirmed:

- Workspace doctype is still the recommended sidebar nav pattern in v16 (no deprecation, no replacement)
- Fixture loading works in current v16.x — the `name` PK prevents duplicate Workspace records; child-table shortcut duplication ([frappe#36872](https://github.com/frappe/frappe/issues/36872)) is patched in recent v16.x
- URL pre-fill via query params works (`set_route_options_from_url()` in router.js)
- List-view filter URLs work but require JSON-encoded operator arrays
- Single-doctype Shortcut bug [frappe#37623](https://github.com/frappe/frappe/issues/37623) — workaround documented below
- Frappe Cloud handles Workspace fixtures identically to local bench

Sources: [Workspace docs](https://docs.frappe.io/framework/user/en/desk/workspace), [v16 features](https://frappe.io/framework/version-16), [Migrating to v16 wiki](https://github.com/frappe/frappe/wiki/Migrating-to-version-16).

---

## 3. Layout

Single workspace `greytHR`, six section headers, **15 shortcut cards** total:

```
greytHR  (sidebar entry, envelope icon)
├── ONBOARDING
│    [New Employee Offer]    [New Consultant Offer]    [New Intern Offer]
├── COMPENSATION
│    [New Salary Revision (Increment Letter)]
├── RECOGNITION
│    [Generate Promotion Letter]    [Generate Service Certificate]
├── EXIT
│    [New Separation (Experience / Relieving Letter)]
├── OPERATIONS
│    [greytHR Settings]    [Sync Logs]    [Employee Mappings]    [Error Log]
└── MONITOR
     [Pending Signatures]   [Recently Signed]
     [Sync Failures]        [Letter Errors]
```

Grouping is by **employee lifecycle** (Onboarding → Compensation → Recognition → Exit), then operational/monitoring at the bottom. HR users do not need to know which underlying doctype each letter lives on.

---

## 4. Card behaviour (smart pre-fill)

Each shortcut is a `Workspace Shortcut` row with a `url` that does one of three things:

### 4.1 Pre-filled "new doc" shortcuts (7 cards)

Open the new-doc form with one field already set. Frappe's `set_route_options_from_url()` reads query params and applies them as field defaults.

| Card | URL |
|---|---|
| New Employee Offer | `/app/job-offer/new?custom_offer_type=Employee` |
| New Consultant Offer | `/app/job-offer/new?custom_offer_type=Consultant` |
| New Intern Offer | `/app/job-offer/new?custom_offer_type=Intern` |
| New Salary Revision | `/app/salary-structure-assignment/new?custom_send_increment_letter=1` |
| New Separation | `/app/employee-separation/new?custom_send_experience_letter=1&custom_send_relieving_letter=1` |
| Generate Promotion Letter | `/app/employee` (list view; user picks employee, then clicks **Letters → Generate Promotion Letter** button from the Client Script) |
| Generate Service Certificate | `/app/employee?status=Active` (Active list; user picks employee, then **Letters → Generate Service Certificate** button) |

**Note on Promotion / Service Cert:** these are per-employee actions, not new-doc creations. The card leads to the Employee list as the natural entry point. The Client Script buttons (shipped in Phase B) handle the actual trigger.

**Default checkbox pre-fill:** the SSA and Separation pre-fills tick the "send letter" checkbox(es) on form load. HR can untick before submit if they don't want the letter.

### 4.2 List-view monitor shortcuts (4 cards)

Open the standard Frappe list view with filters already applied. URL filter encoding: `?<field>=%5B%22<op>%22%2C%22<value>%22%5D` (URL-encoded JSON `["op","value"]`).

| Card | Filter (logical) | URL |
|---|---|---|
| Pending Signatures | Job Offer where `custom_zoho_sign_request_id` IS set AND `custom_zoho_sign_signed_at` IS NOT set | `/app/job-offer?custom_zoho_sign_request_id=%5B%22is%22%2C%22set%22%5D&custom_zoho_sign_signed_at=%5B%22is%22%2C%22not+set%22%5D` |
| Recently Signed | Job Offer where `custom_zoho_sign_signed_at` IS set, sorted desc | `/app/job-offer?custom_zoho_sign_signed_at=%5B%22is%22%2C%22set%22%5D` |
| Sync Failures | greytHR Sync Log where `status=Failed` | `/app/greythr-sync-log?status=Failed` |
| Letter Errors | Error Log where `title` LIKE "%Letter%" | `/app/error-log?title=%5B%22like%22%2C%22%25Letter%25%22%5D` |

(Unfiltered "All Sync Logs" view is reachable via the **Sync Logs** card in Operations — no need to duplicate it in Monitor.)

### 4.3 Direct doctype links (4 cards)

Plain `/app/<doctype-name>` URLs for the Operations group. Singles use `/app/greythr-settings` (workaround for [frappe#37623](https://github.com/frappe/frappe/issues/37623) which breaks `link_to` for Single doctypes).

| Card | URL |
|---|---|
| greytHR Settings | `/app/greythr-settings` |
| Sync Logs | `/app/greythr-sync-log` |
| Employee Mappings | `/app/greythr-employee-mapping` |
| Error Log | `/app/error-log?title=%5B%22like%22%2C%22greytHR%25%22%5D` (filtered to our errors) |

---

## 5. Fixture mechanics

### 5.1 New file: `greythr_bridge/fixtures/workspace.json`

Single-element JSON array (Frappe fixture convention) containing one Workspace record. Hand-authored from a minimal template — no `content` layout blob (Frappe auto-generates one from the `shortcuts` array on first save). Approximate shape:

```json
[
 {
  "doctype": "Workspace",
  "name": "greytHR",
  "title": "greytHR",
  "label": "greytHR",
  "module": "greytHR",
  "app": "greythr_bridge",
  "for_user": "",
  "public": 1,
  "is_hidden": 0,
  "icon": "mail",
  "sequence_id": 50,
  "shortcuts": [
    {"type": "DocType", "link_to": "Job Offer",
     "label": "New Employee Offer", "color": "Blue",
     "url": "/app/job-offer/new?custom_offer_type=Employee"},
    {"type": "DocType", "link_to": "greytHR Settings",
     "label": "greytHR Settings", "color": "Grey",
     "url": "/app/greythr-settings"},
    ...13 more shortcut rows...
  ]
 }
]
```

**Critical Frappe v16 requirements (learned the hard way):**

- **`app` field is required** — even though the Workspace doctype JSON does not mark it mandatory, the `Removing orphan Workspaces` cleanup step at the end of every `bench migrate` deletes any Workspace whose `app` is empty. Set it to the app name (`greythr_bridge`).
- **`type` enum is strict** — Workspace Shortcut accepts only `DocType`, `Report`, `Page`, `Dashboard Chart`. There is no `URL` type. For a shortcut to a Single doctype where we want the URL workaround for [frappe#37623](https://github.com/frappe/frappe/issues/37623), keep `type: "DocType"` AND `link_to: "<Single Doctype Name>"`, then add the explicit `url` field — the URL field overrides the click destination, the `link_to` keeps Frappe's validator happy.
- **`for_user: ""`** — explicit empty string for public workspaces. Some v16.x versions require the key to be present.

### 5.2 `hooks.py` — one new fixtures entry

```python
fixtures = [
    {"dt": "DocType", "filters": [["module", "=", "greytHR"]]},
    {"dt": "Custom Field", "filters": [...]},
    {"dt": "Client Script", "filters": [["module", "=", "greytHR"]]},
    {"dt": "Workspace", "filters": [["module", "=", "greytHR"]]},   # NEW
]
```

### 5.3 No patch needed

Earlier draft proposed a one-shot patch to handle workspace duplication. On review, the `name` column is the MariaDB primary key, so two Workspace rows named `greytHR` can't coexist — the fixture loader does INSERT...ON DUPLICATE KEY UPDATE. The historical [frappe#36872](https://github.com/frappe/frappe/issues/36872) bug duplicates child-table *shortcut* rows under a single workspace, and is patched in recent v16.x. If shortcut duplication is observed post-deploy, the manual remediation is one minute in the in-browser Workspace Editor (delete the extra rows, save) — not worth a patch.

---

## 6. Deploy path

1. PR with `workspace.json`, `hooks.py` change, tests — single commit
2. User on Frappe Cloud: **Bench → Fetch → Update Bench → Migrate**
3. `bench migrate` loads the workspace fixture
4. Refresh browser → sidebar shows new `greytHR` entry
5. No bench restart needed

**Rollback:** `git revert <commit>` → `Update Bench` → `Migrate`. Workspace is removed automatically because the fixture filter `module=greytHR` no longer matches it.

---

## 7. Failure modes

1. **A shortcut URL drifts when a custom field gets renamed.** Example: renaming `custom_zoho_sign_request_id` to `custom_zoho_request_id` silently breaks the "Pending Signatures" filter (filter becomes a no-op, list shows everything).
   *Mitigation:* `test_workspace_fixture.py` (see §10) reads every URL, extracts the field name, and asserts it exists in `fixtures/custom_field.json` or in the underlying Frappe HR doctype.

2. **Workspace fixture conflicts with hand-edited workspace on the live site.** If HR uses the in-browser Workspace Editor to tweak the layout, those changes are overwritten on the next `bench migrate`.
   *Mitigation:* `public: 1` flag marks the workspace as system-managed (a small notice appears in the editor); team is told via CHANGELOG that workspace edits must go via PR.

3. **Permission gap on per-card actions.** A user without HR User role clicks "New Job Offer" → Frappe shows a permission error.
   *Mitigation:* this is the expected Frappe-native behaviour. The workspace is public; per-card actions inherit doctype permissions. A permission error is clearer than a hidden card.

4. **Workspace ordering conflict.** `sequence_id: 50` is a guess — if it collides with another app's workspace, the sidebar order looks arbitrary. Low impact.
   *Mitigation:* pick a value (50) that's safely between Frappe's defaults (10s for core, high numbers for plugins); leave room to adjust.

5. **`content` blob drift.** Frappe auto-generates a `content` JSON string on first save that describes visual layout. If HR adds a card via UI, `content` mutates, and the next `export-fixtures` (which we can't run on Frappe Cloud anyway) would diverge.
   *Mitigation:* omit `content` from the fixture entirely — Frappe regenerates it from `shortcuts[]` order. Accept that complex two-column layouts are not achievable this way (we don't need them).

---

## 8. Definition of done (observable)

- After `bench migrate`, the left sidebar shows a `greytHR` entry with envelope icon, slotted between Frappe HR's core entries
- Clicking it reveals 6 sections totalling **15 cards**, grouped: Onboarding (3), Compensation (1), Recognition (2), Exit (1), Operations (4), Monitor (4)
- Clicking **New Consultant Offer** lands on `/app/job-offer/new` with the `custom_offer_type` field already set to `Consultant`
- Clicking **New Salary Revision** lands on `/app/salary-structure-assignment/new` with `custom_send_increment_letter` checkbox already ticked
- Clicking **Pending Signatures** lands on a Job Offer list showing only offers where `custom_zoho_sign_request_id` is set AND `custom_zoho_sign_signed_at` is empty
- Clicking **greytHR Settings** lands on the Single edit view
- Clicking **Error Log** in Operations lands on Error Log filtered to titles starting with `greytHR`
- Re-running `bench migrate` does not duplicate the workspace (fixture filter on `module=greytHR` + Workspace `name` PK guarantee this)
- All 114 existing tests continue to pass; new workspace-fixture test passes

---

## 9. Non-goals (explicit)

- **Number Cards / live count badges** — research recommends them for queue cards, but they need their own fixture file and a saved-filter doctype. Defer to v2 if HR asks ("I want to see '3 Pending Signatures' as a badge, not have to click in").
- **Charts / dashboards** — out of scope. If HR wants letter-volume trends, that's a separate spec.
- **Mobile / web view** — Workspaces only render in `/app` (Desk). Frappe HR's mobile app does its own thing.
- **Custom column on the Job Offer list view** to show signature status visually — separate spec.
- **Workspace per-user customisation** — `for_user` field stays empty; one workspace for everyone.

---

## 10. Tests

New file: `greythr_bridge/tests/test_workspace_fixture.py` — runs offline, no Frappe needed. Asserts:

1. **JSON parses cleanly** — no trailing commas, valid array of length 1
2. **Top-level required fields present** — `doctype`, `name`, `module`, `public`, `shortcuts`
3. **Exactly 15 shortcuts** — count must equal the design
4. **Every shortcut has `label` + `url`** — no empty entries
5. **Every URL referencing a `custom_*` field has that field in `fixtures/custom_field.json`** — catches rename drift (failure mode #1)
6. **`module` is `greytHR`** — so fixtures filter picks it up
7. **No `content` field present** — design says Frappe auto-generates it; including it courts drift
8. **All `/app/<doctype>` URL slugs match a known doctype** — kebab-case of Frappe HR or greytHR doctype names

These are pure JSON-validation tests. Total: ~80 lines of pytest, 1.5s to run.

---

## 11. Implementation order (single atomic commit)

1. Write `greythr_bridge/fixtures/workspace.json` (~75 lines JSON, 15 shortcuts)
2. Add `Workspace` fixtures entry to `hooks.py`
3. Write `greythr_bridge/tests/test_workspace_fixture.py` (8 assertions)
4. Run full test suite (expect 122 passing: 114 + 8)
5. Update `CHANGELOG.md` with Workspace entry
6. Commit + push as single atomic commit
7. User: Fetch → Update → Migrate on Frappe Cloud
8. User: verify the observable outcomes in §8

---

## 12. Open questions

None. All design choices have been confirmed in conversation:

- Scope: Letters + greytHR utilities (Q1 ✓)
- Grouping: By employee lifecycle (Q2 ✓)
- Card behaviour: Smart pre-fill (Q3 ✓)
- Reports depth: Light — 5 filtered list shortcuts (Q4 ✓)
- Approach validated against Frappe v16 docs + GitHub issues (§2)

---

## Appendix A — Full URL reference

For copy-paste verification post-deploy. URL-encoded forms used in the fixture:

```
/app/job-offer/new?custom_offer_type=Employee
/app/job-offer/new?custom_offer_type=Consultant
/app/job-offer/new?custom_offer_type=Intern
/app/salary-structure-assignment/new?custom_send_increment_letter=1
/app/employee-separation/new?custom_send_experience_letter=1&custom_send_relieving_letter=1
/app/employee
/app/employee?status=Active
/app/greythr-settings
/app/greythr-sync-log
/app/greythr-employee-mapping
/app/error-log?title=%5B%22like%22%2C%22greytHR%25%22%5D
/app/job-offer?custom_zoho_sign_request_id=%5B%22is%22%2C%22set%22%5D&custom_zoho_sign_signed_at=%5B%22is%22%2C%22not+set%22%5D
/app/job-offer?custom_zoho_sign_signed_at=%5B%22is%22%2C%22set%22%5D
/app/greythr-sync-log?status=Failed
/app/error-log?title=%5B%22like%22%2C%22%25Letter%25%22%5D
```

(15 URLs = 15 shortcuts. Grouped: Onboarding 3, Compensation 1, Recognition 2, Exit 1, Operations 4, Monitor 4.)
