# greythr_bridge — Project Reference Manual

> **⚠️ SUPERSEDED 2026-07-11.** This manual documents the retired
> `greythr_bridge` era (Frappe HR ↔ greytHR sync). On 2026-07-10 the project
> pivoted to **`globex_hr_letters`** — a standalone HR letters generation app
> with all greytHR integration removed. Kept for historical reference only;
> file paths, doctypes, and commands below no longer exist. See `PLAN.md`,
> `CLAUDE.md`, and `docs/superpowers/specs/2026-07-10-globex-hr-letters-design.md`.

> **Status: PAUSED 2026-05-26.** Globex signed a 300-employee onboarding deal (60-day timeline) and is consolidating onto greytHR-only for that work. This Frappe HR bridge stays in production-stable state but is not being actively extended. See [§12 Why Paused](#12-why-paused) and [§13 How to Resume](#13-how-to-resume).
>
> **Last working commit**: `8988fd8` (2026-05-26) — A-v2: custom_last_working_date for Separation letters
> **Deployed on**: `gdshr.m.frappe.cloud` (Frappe Cloud, AWS Mumbai)
> **Lines of Python**: ~10,500 across app code + tests
> **Tests**: 261 passing, 3 skipped — `python -m pytest greythr_bridge/tests/`

---

## Table of Contents

1. [At a Glance](#1-at-a-glance)
2. [Business Context](#2-business-context)
3. [Architecture](#3-architecture)
4. [Current State — What Works, What Doesn't](#4-current-state)
5. [Code Map](#5-code-map)
6. [Operational Reference (URLs, Commands)](#6-operational-reference)
7. [Key Design Decisions](#7-key-design-decisions)
8. [Known Gotchas](#8-known-gotchas)
9. [HR Workflow Integration](#9-hr-workflow-integration)
10. [External Dependencies](#10-external-dependencies)
11. [Lessons Learned](#11-lessons-learned)
12. [Why Paused](#12-why-paused)
13. [How to Resume](#13-how-to-resume)

---

## 1. At a Glance

**What it does**: Bridges Frappe HR (running on Frappe Cloud) with greytHR Cloud (HR/payroll SaaS, India DC). greytHR is the system of record for employee master data + payroll. Frappe HR mirrors greytHR employee data and adds a letter-generation pipeline (offer letters via Zoho Sign + 7 other letter types as direct PDFs).

**Why it exists**: Globex wanted custom-branded HR letters (offer, increment, promotion, experience, etc.) with their template designs + Zoho Sign integration. greytHR's stock letters didn't match their brand. The bridge keeps Frappe HR in sync with greytHR's employee data so letters can reference accurate names, dates, designations.

**What's in production**: Sync (daily 6 AM IST + manual button), 8 letter types coded, 3 verified live (Offer, Promotion, Service Certificate), 1 partially verified (Experience + Relieving — needs `custom_last_working_date` populated by HR), 3 not yet verified live (Increment, Consultant Offer, Intern Offer).

---

## 2. Business Context

| Aspect | Reality |
|---|---|
| **System of record** | greytHR Cloud (payroll, leave, attendance, compliance reports) |
| **Frappe HR's role** | Read-only mirror + custom letter generation; NOT used for payroll/leave/attendance |
| **Why two systems** | greytHR is mandatory (payroll compliance with Indian regulations, pharma/chip-mfr compliance reports); Frappe HR is optional polish (custom-branded letters, workflow UI) |
| **Compliance reports** | All in greytHR — pharma + chip-manufacturing client reports are pre-built there |
| **300-employee deal** | Triggered the pause decision — see §12 |

**Key principle that drove all architecture**: greytHR is the source of truth. All sync is one-way (greytHR → Frappe). Frappe-side mutations of synced fields are temporary and get overwritten on next sync. The Frappe bridge has zero write-back to greytHR.

---

## 3. Architecture

### Component Map

```
                            ┌─────────────────────────────────────────┐
                            │ greytHR Cloud (api.greythr.com)         │
                            │   - Employee master (340+ records)      │
                            │   - Payroll, leave, attendance          │
                            │   - Compliance reports                  │
                            │   - Webhook: none (we pull, not push)   │
                            └────────────┬────────────────────────────┘
                                         │
                                         │ HTTPS, OAuth (Basic) + ACCESS-TOKEN header
                                         │ Rate-limited 10 req/sec
                                         │
                            ┌────────────▼────────────────────────────┐
                            │ Frappe HR + greythr_bridge              │
                            │ (Frappe Cloud, hr.globexdigital.ai)     │
                            │                                          │
                            │  pull_employees (daily 6 AM IST + manual)│
                            │      └─ greythr_to_frappe (mapper)      │
                            │      └─ _find_frappe_employee (matching)│
                            │      └─ _is_different_employment (v5)   │
                            │      └─ defensive: REFUSE hijacks       │
                            │                                          │
                            │  letters/                                │
                            │      └─ merger.py (Jinja contexts)      │
                            │      └─ non_signing.py (WeasyPrint PDF) │
                            │      └─ dispatch.py (offer type routing)│
                            │      └─ pdf_convert.py (LibreOffice)    │
                            │                                          │
                            │  webhooks/zoho_sign.py                  │
                            │      ← signed offer letter PDF          │
                            └────────────┬────────────────────────────┘
                                         │
                                         │ Zoho Sign API (India DC, in.zoho.com)
                                         │ HMAC-SHA256 webhook verification
                                         │
                            ┌────────────▼────────────────────────────┐
                            │ Zoho Sign (in.zoho.com)                 │
                            │   - E-signature for offer letters       │
                            │   - NDA + Offer (NDA-first sequence)    │
                            └─────────────────────────────────────────┘
```

### Key data flows

1. **Daily sync (6 AM IST)** — `pull_employees.run` → fetches greytHR `/employee/v2/employees` paginated → mapper → defensive matching (v5) → create/update Frappe Employee + Mapping → logs to greytHR Sync Log
2. **Manual sync** — same code path, triggered via workspace "Sync from greytHR Now" button → calls `pull_employees.run_now`
3. **Letter generation (PDF-only types: Increment, Promotion, Experience, Relieving, Service Cert, Consultant Offer, Intern Offer)** — `on_submit` doc_event on Job Offer / SSA / Employee Separation / manual button → mapper builds context → WeasyPrint renders HTML to PDF → attach + email
4. **Offer letter signing (Employee Offer only)** — Job Offer on_submit → NDA sent to Zoho Sign → webhook receives "signed" → trigger offer letter → sent to Zoho Sign → webhook receives "offer signed" → pull signed PDF → attach to Job Offer + Employee

---

## 4. Current State

### Production-verified end-to-end

- ✅ **Employee sync** — daily + manual, GDS#### naming aligned with greytHR, v5 rehire detection catches duplicate-email rehires
- ✅ **Offer Letter** (Phase A) — generation + Zoho Sign + signed PDF attach
- ✅ **Promotion Letter** — verified for Avinash Nalluri (GDS0391)
- ✅ **Service Certificate** — verified for Avinash Nalluri; template handles empty designation cleanly
- ✅ **Workspace navigation** — 16 cards across Onboarding/Compensation/Recognition/Exit/Operations/Monitor sections
- ✅ **Sync diagnostics** — `inspect_sync_for_employee`, `inspect_greythr_employee`, `force_resync_employee`
- ✅ **Phase 4 UX filter** — 2 invalid-pattern employees (Yarabaka Mahitha, siuad) hidden from all Employee pickers

### Working but partially verified

- 🟡 **Experience + Relieving letters** — verified for nalluri sudha (GDS0021); now requires HR to fill in `custom_last_working_date` on Separation form (A-v2 fix, shipped 8988fd8)
- 🟡 **Letter trigger placeholders** — set up via `setup_letter_placeholders` task; 352 employees backfilled with `Calendar-Only (No Holidays)` holiday list

### Not yet verified live

- ⚪ **Increment Letter** — code shipped, never triggered live
- ⚪ **Consultant Offer** — code shipped, never triggered live
- ⚪ **Intern Offer** — code shipped, never triggered live

### Deferred / not started

- ⬜ **Phase 6 push-back to greytHR** — bidirectional sync (push new hires created in Frappe back to greytHR). Originally planned, never started. Probably never needed if greytHR-only path wins.
- ⬜ **DocType export to fixtures** — `greytHR Sync Log`, `greytHR Settings`, `greytHR Employee Mapping` exist only on live site, not in source. Hygiene gap. Documented in CHANGELOG.
- ⬜ **Data quality dashboard** (workspace cards with counts of ghosts, broken mappings, etc.) — only the diagnostic API endpoints exist, no UI dashboard cards
- ⬜ **3 invalid_pattern records cleanup** — `GSD0033` (Yarabaka Mahitha, typo), `Gds0943274` (siuad, 10 digits), `gds0115` (Gopi Gali, lowercase) — HR needs to fix in greytHR portal then re-run rename
- ⬜ **Past silent-hijack audit** — read-only endpoint to find Frappe Employees corrupted by pre-v5 hijacks. 1 found (GDS0167 / Sundareshwaran) and manually repaired; probably more exist.

---

## 5. Code Map

```
greythr_bridge/
├── api/
│   ├── client.py              # GreytHRClient — auth, rate limit, retry, content-type sanity check
│   ├── employee.py            # /employee/v2/employees, /employees/{id}, work, separation endpoints
│   ├── payroll.py             # /payroll/v2/salary/repository, employee salary endpoints
│   ├── exceptions.py          # GreytHRError + subclasses (Auth, RateLimit, Server, Client)
│   └── zoho_sign.py           # OAuth refresh, send_for_signature, get_signed_document, verify_webhook_hmac
├── mappers/
│   ├── employee_mapper.py     # greythr_to_frappe — name fallbacks, gender map, date sanity, status logic
│   └── salary_mapper.py       # Recursive tree-walk for greytHR salary repository
├── tasks/
│   ├── pull_employees.py      # Daily sync — _find_frappe_employee (v5 defensive), _sync_one, _upsert_mapping
│   ├── pull_salary_structures.py  # Salary Component sync (SSA mirroring deferred)
│   ├── rename_employees_to_greythr_id.py  # One-shot rename HR-EMP-#### → GDS####
│   ├── setup_letter_placeholders.py        # HR setup task — creates Holiday List + Salary Structure + backfill
│   ├── stalled_signings.py    # Daily check for unsigned offers > 28 days
│   └── force_resync_employee  # (in utils/sync_diagnostics.py) HR repair tool for broken mappings
├── hooks_handlers/
│   ├── employee.py            # before_insert hook (set name from greytHR ID + holiday_list), promotion/service cert handlers
│   ├── employee_separation.py # on_submit triggers Experience + Relieving letters; dual-attach via file_url linking
│   ├── job_offer.py           # on_submit triggers offer letter dispatch (Employee/Consultant/Intern)
│   └── salary_structure_assignment.py  # on_submit triggers Increment letter
├── webhooks/
│   └── zoho_sign.py           # Callback for Zoho Sign events (signed, declined, etc.)
├── letters/
│   ├── merger.py              # Jinja context builders for all 8 letter types + _tenure + _format_name
│   ├── non_signing.py         # generate_and_deliver — PDF + dual attach + email
│   ├── dispatch.py            # Offer-type routing (Employee/Consultant/Intern)
│   ├── pdf_convert.py         # LibreOffice headless DOCX → PDF (Phase A fallback)
│   └── pdf_check.py           # Health-check endpoint for letter pipeline
├── utils/
│   ├── retry.py               # @retry decorator (exponential backoff, 3 attempts)
│   ├── rate_limiter.py        # @rate_limited (10 req/sec via ratelimit lib)
│   ├── logging.py             # PII-safe log_error wrapper, get_recent_errors endpoint
│   ├── idempotency.py         # make_key() helper
│   ├── data_quality.py        # list_ghost_employees, list_employees_missing_holiday_list
│   ├── sync_diagnostics.py    # inspect_sync_for_employee, inspect_greythr_employee, force_resync_employee
│   └── permissions.py         # employee_query_conditions (Phase 4 UX filter)
├── greythr/workspace/greythr/
│   └── greythr.json           # Workspace fixture (16 shortcuts)
├── fixtures/
│   ├── custom_field.json      # 27 custom fields across Job Offer / Employee / SSA / Employee Separation
│   └── client_script.json     # Manual-sync button + promotion/service cert buttons on Employee form
├── templates/letters/
│   ├── *.docx                 # Phase A — original DOCX template (offer_letter.docx)
│   └── html/
│       ├── _base.html         # Shared letterhead + watermark + CSS
│       ├── _styles.css        # Shared styles
│       ├── offer_letter.html, consultant_offer_letter.html, intern_offer_letter.html
│       ├── increment_letter.html, promotion_letter.html
│       ├── experience_letter.html, relieving_letter.html, service_certificate.html
│       └── img/hr_signature.png
├── tests/                     # 261 passing tests
├── hooks.py                   # Scheduler events, doc_events, fixtures filter, permission_query_conditions
├── modules.txt                # "greytHR"
└── pyproject.toml             # Dependencies: ratelimit, docxtpl, weasyprint
```

---

## 6. Operational Reference

### Site

- **URL**: https://hr.globexdigital.ai (custom domain) / https://gdshr.m.frappe.cloud (Frappe Cloud)
- **Bench**: `bench-40239-000056-f194m` (Frappe Cloud Private Bench, AWS Mumbai)
- **Site name**: `gdshr.m.frappe.cloud`
- **GitHub repo**: https://github.com/nchandu247/globexhr

### Key whitelisted endpoints (System Manager only unless noted)

| Endpoint | Purpose |
|---|---|
| `greythr_bridge.tasks.pull_employees.run_now` | Manual sync trigger |
| `greythr_bridge.tasks.rename_employees_to_greythr_id.plan_rename` | Read-only rename plan |
| `greythr_bridge.tasks.rename_employees_to_greythr_id.run_rename?confirm=yes` | Execute rename |
| `greythr_bridge.tasks.setup_letter_placeholders.setup_letter_placeholders` | One-time setup of Salary Structure + Holiday List + backfill |
| `greythr_bridge.utils.data_quality.list_ghost_employees` | Audit (HR Manager OK) |
| `greythr_bridge.utils.data_quality.list_employees_missing_holiday_list` | Audit |
| `greythr_bridge.utils.sync_diagnostics.inspect_sync_for_employee?employee_name=GDS0001` | Per-Employee diagnostic |
| `greythr_bridge.utils.sync_diagnostics.inspect_greythr_employee?greythr_id=389` | Per-greytHR-ID diagnostic (no Frappe mapping needed) |
| `greythr_bridge.utils.sync_diagnostics.force_resync_employee?frappe_employee=GDS0215&greythr_id=250` | HR repair for broken mappings |
| `greythr_bridge.utils.sync_diagnostics.list_recent_sync_errors` | Last 20 sync errors |
| `greythr_bridge.utils.logging.get_recent_errors?filter_title=greytHR` | Generic Error Log fetcher |
| `greythr_bridge.webhooks.zoho_sign.callback` | (allow_guest) Zoho Sign webhook target |

### Scheduled jobs (in `hooks.py`)

| Cron | Job |
|---|---|
| `0 6 * * *` | `pull_employees.run` — daily sync at 6 AM IST |
| `0 20 * * *` | `pull_salary_structures.run` — daily salary component sync |
| `0 21 * * *` | `stalled_signings.run` — flag unsigned offers > 28 days |

### Local dev commands

```bash
# Run all tests
python -m pytest greythr_bridge/tests/ -q

# Run specific test file
python -m pytest greythr_bridge/tests/test_pull_employees.py -v

# Bench commands (on Frappe Cloud SSH or local bench)
bench --site gdshr.m.frappe.cloud execute greythr_bridge.api.client.test_connection
bench --site gdshr.m.frappe.cloud migrate
bench --site gdshr.m.frappe.cloud reload-doctype "greytHR Settings"
bench --site gdshr.m.frappe.cloud export-fixtures --app greythr_bridge  # for hygiene
```

### Credentials location

ALL secrets in `greytHR Settings` Single doctype (encrypted Password fields):
- greytHR: client_id, client_secret, cached_token, token_expires_at
- Zoho Sign: zoho_client_id, zoho_client_secret, zoho_refresh_token, zoho_account_id, zoho_webhook_secret

**Never** in source, `frappe.conf`, or env vars (CLAUDE.md hard rule).

---

## 7. Key Design Decisions

### Decisions that hold across the codebase

1. **One-way sync only** (greytHR → Frappe). No write-back. Reason: greytHR is the payroll system of record; bidirectional sync would create irreconcilable divergence on conflicts. Affects: matching logic, rejecting "bridge" handlers that update Employee fields from Separation submit (A-v1 considered, rejected in favor of A-v2).

2. **GDS#### as Frappe Employee primary key** (not HR-EMP-####). Reason: HR sees identical IDs across both systems. Implemented in two layers: Phase 1 `before_insert` hook for new records, Phase 2 one-shot rename for existing 330 records.

3. **Defensive matching with v5 (employee_number + first_name)**. Reason: a chain of v3→v4→v5 attempts each broke on edge cases. v5 only allows reuse of a candidate Frappe Employee when employee_number matches AND first_name doesn't conflict — handles rehires correctly without merging data-corruption cases.

4. **Letters live in Frappe, not greytHR**. Reason: greytHR's stock letter templates didn't match Globex branding. Cost: maintenance burden. (As of 2026-05-26 pause, reconsidering this — see §12.)

5. **Placeholder records for Frappe HR mandatory fields**. Reason: greytHR runs payroll/leave, so Frappe HR's holiday_list / salary_structure validations are blocking workflows we don't need. Option A (placeholders) chosen over Option B (Property Setter to make non-mandatory) to preserve Frappe HR's data invariants for other features.

6. **Custom field `custom_last_working_date` on Employee Separation** (A-v2). Reason: Frappe HR's stock Separation has no field for "last working day" (the closest, `resignation_letter_date`, is when employee handed in resignation, not last day). Our letters need it. Field is conditionally mandatory when letter checkbox is ticked.

7. **Dual-attach via file_url linking** (Separation letters). Reason: attaching the same PDF to both Employee + Separation with content writes twice causes Frappe to append a hash suffix to the second file. Linking via file_url instead avoids duplicate physical files and keeps clean filenames.

8. **All errors via `log_error`, never `print` or bare `pass`**. Reason: DPDP Act compliance + audit trail. Log only IDs/operation names, never PII.

9. **`@rate_limited(10/sec)` on every greytHR call**. Reason: greytHR API limit. Implemented at the `_request` method level in GreytHRClient.

10. **Background jobs for everything triggered from HTTP**. Reason: HTTP handlers must return in 5s. Letter generation, sync, force_resync all enqueued.

---

## 8. Known Gotchas

Things that bit us once; don't let them bite again:

1. **`on_status_change` doesn't exist in Frappe.** To react to Employee status change, use `on_update` and compare `doc.status` vs `doc.get_doc_before_save().status`. Registering `on_status_change` in `hooks.py` silently never fires.

2. **`naming_series` field stays on records after rename.** When we renamed HR-EMP-#### to GDS####, the `naming_series` field still said "HR-EMP-" on those records. Cosmetic only; doesn't affect anything functional. We chose not to touch it.

3. **Submittable doctypes in fixtures don't auto-submit.** Salary Structure is submittable (docstatus 1); fixture inserts as draft. That's why `setup_letter_placeholders.py` is a programmatic task, not a JSON fixture.

4. **Frappe HR's Employee Separation does NOT auto-update Employee.relieving_date on submit.** Verified via source inspection of `hrms`. Don't assume any Frappe HR magic on Separation submit beyond setting up the boarding Project. See A-v2 design rationale in CHANGELOG.

5. **`Salary Component` validates require GL accounts** for posting to general ledger. Our placeholder "CTC" component gets a warning "Accounts not set" — benign (we don't run payroll in Frappe).

6. **Frappe File doctype appends hash suffix** when writing duplicate filenames. Fix: dual-attach uses file_url linking (A-v2 v2).

7. **greytHR's bulk endpoint may return different data than single-employee endpoint.** Suspected during emp 389 investigation. Mapper handles both consistently via the same `greythr_to_frappe()`. Worth keeping in mind if a record fails in bulk sync but looks fine in `inspect_greythr_employee`.

8. **greytHR returns `employeeId` as integer, mapper stringifies it** for `custom_greythr_employee_id`. Always compare with `str()` on both sides. Bug fixed once, regression test pins it.

9. **MariaDB `NOT IN` with NULL silently returns 0 rows.** Original audit query used `filters={"first_name": ["not in", ["", None]]}` → always empty. Use `or_filters` + `is set`/`is not set` instead.

10. **Optimistic locking on `greytHR Settings`.** Multiple `frappe.get_single("greytHR Settings").save()` calls in same transaction → TimestampMismatchError. Use `frappe.db.set_value` for credential updates instead.

11. **`mandatory_depends_on` Frappe field setting** — `"eval:doc.custom_send_experience_letter || doc.custom_send_relieving_letter"`. Note: JS-style `||` works in Frappe's eval, not Python `or`.

12. **Past data hijacks can persist.** Pre-v5 sync hijacks corrupted some records (Sundareshwaran → GDS0167). v5 prevents new hijacks but past damage requires manual `force_resync_employee` calls.

13. **Frappe Cloud Bench ID changes on redeploy.** Old SSH cert from bench-40239-000051 no longer works after redeploy to bench-40239-000056. Re-obtain SSH credentials from the dashboard's "SSH Access" dialog.

14. **DocTypes created via Form Builder don't auto-export to fixtures.** `greytHR Sync Log`, `greytHR Settings`, `greytHR Employee Mapping` live only on the live site. Run `bench export-fixtures --app greythr_bridge` to round-trip them to source.

---

## 9. HR Workflow Integration

### What HR does (where + when)

| Workflow | Where to start | What happens |
|---|---|---|
| **New Employee Offer** | Workspace → New Employee Offer card | Fills Job Offer form → submit → NDA sent to Zoho Sign → after NDA signed, offer letter sent → after offer signed, signed PDF attached to Job Offer |
| **New Consultant Offer** | Workspace → New Consultant Offer card | Same as above with consultant template + NDA |
| **New Intern Offer** | Workspace → New Intern Offer card | Same with intern template |
| **New Salary Revision** | Workspace → New Salary Revision card | SSA form with placeholder structure pre-filled + Increment Letter checkbox ticked → fill in `base` (new CTC) → submit → letter generated |
| **Promotion Letter** | Open Employee record → Letters menu → Generate Promotion Letter | Dialog: old/new designation, effective date, notes → background job |
| **Service Certificate** | Open Active Employee → Letters menu → Generate Service Certificate | Confirmation → background job |
| **Separation** | Workspace → New Separation card | Fill in **Separation Begins On** (when process starts) + **Last Working Date** (real last day, mandatory if letter checkbox ticked) + select letter types → submit → letters generated |
| **Manual sync** | Workspace → Sync from greytHR Now card | Confirms → triggers `pull_employees.run_now` → see Sync Log for results |

### What HR is supposed to do FIRST (one-time setup after each deploy)

1. Click "Sync from greytHR Now" — verify sync works and records are populated
2. Run `setup_letter_placeholders` — creates Holiday List + Salary Structure + backfills (idempotent)
3. Spot-check letter generation for 1 of each type

### What HR is supposed to do BEFORE submitting a Separation

- Fill in **Last Working Date** (`custom_last_working_date`) — Frappe HR's stock Separation doesn't have this field; our custom field fills the gap. Mandatory if either letter checkbox is ticked.

### What HR is NOT supposed to do

- Don't edit `custom_greythr_employee_id`, `custom_greythr_last_synced`, `custom_greythr_full_name` — these are read-only sync metadata
- Don't manually change `employee_number` — greytHR sync owns this field
- Don't delete Employee records in Frappe via the Delete button (memory rule `never_delete_employee_records.md`) — even ghost records have payroll/leave/attendance linked rows

---

## 10. External Dependencies

| Dependency | Purpose | Where credentials live |
|---|---|---|
| **greytHR Cloud** (api.greythr.com / globex.greythr.com) | Source of truth for employee data, payroll, compliance reports | greytHR Settings (Password fields) |
| **Zoho Sign India DC** (in.zoho.com, accounts.zoho.in) | E-signature for offer letters; webhook callbacks | greytHR Settings |
| **Frappe Cloud Private Bench** (n2-mumbai.frappe.cloud) | Hosting | Frappe Cloud dashboard SSH access |
| **GitHub** (github.com/nchandu247/globexhr) | Source code | git config / SSH key |
| **WeasyPrint** | HTML → PDF rendering for non-signing letters | Pip-installed via requirements |
| **LibreOffice headless** | DOCX → PDF for Phase A offer letter (legacy path) | OS package on Frappe Cloud bench |
| **docxtpl** | Jinja-in-DOCX templating for Phase A | Pip |

### Critical API quirks documented in `NOTES_greythr_api.md`

- OAuth endpoint differs from data endpoints (`globex.greythr.com/uas/...` vs `api.greythr.com/...`)
- OAuth via HTTP Basic auth header (not body params)
- Data calls use `ACCESS-TOKEN: <token>` header (no Bearer prefix)
- `x-greythr-domain: globex.greythr.com` required on every data call
- 200 response + `text/html` Content-Type = auth rejected (silent failure trap)
- Token TTL ~45 days

---

## 11. Lessons Learned

The takeaways from 3-5 days of intense development on this:

1. **Defensive matching is harder than it looks.** We went through v3 → v4 → v5 on the rehire-detection logic. Each iteration was correct in isolation but broke on an edge case the previous iteration didn't anticipate. Pattern: greytHR's data has surprising shapes (dates inverted, missing fields, mixed casing, rehires with reused employees, etc.). Defensive code must be tested against real data, not just unit tests.

2. **Sync log counters can lie.** First major bug: "340 updated" while not a single record was actually enriched. Fixed via the counter-honesty patch in `_sync_one` (return "skipped" when no fields changed). Always assert "what changed was what we INTENDED to change."

3. **Past data corruption is a permanent tax.** Pre-v5 hijacks corrupted ~4 Frappe records before we caught it. The `force_resync_employee` endpoint is what saved us. ANY system with mutable state benefits from a per-record "force resync from source" tool.

4. **Frappe HR's mandatory validations encode assumptions about how you'll use it.** When you're using it differently (mirror-only, not payroll), those validations become friction. Two ways out: (a) provide minimum-valid placeholders (Option A pattern), (b) override via Property Setters. (a) is safer because it preserves Frappe HR's invariants for unrelated features.

5. **The "365-day deploy ago" problem.** Code that's deployed but not exercised will rot. Our offer letter generation worked, but Increment / Consultant / Intern letters were never triggered live until weeks later — we got lucky none broke. Habit: trigger every code path within a week of deploy.

6. **Sunk-cost is a real cognitive trap in software.** "We already built it, so we should use it" is wrong reasoning. Each decision should be made on forward value. (Hence the §12 honest pause.)

7. **HR is a different audience than developers.** "Run this URL" is friction. Workspace buttons + Client Scripts + confirmation dialogs are what makes things usable. Anything that requires HR to know an API URL is a deployment failure.

8. **Two sources of truth = constant reconciliation.** The whole defensive-matching saga (rehires, broken mappings, data corruption) wouldn't have existed if there was only ONE system. The complexity grew super-linearly with the second system.

---

## 12. Why Paused

**Date paused**: 2026-05-26
**Trigger**: Globex signed a 300-employee onboarding deal with a 60-day timeline.

**Strategic reasoning** (also see the conversation log):

- 300 onboardings in 60 days = ~5 per day. HR team is at capacity.
- greytHR already has the things they need: payroll, compliance reports for pharma + chip-manufacturing clients (built-in), documents module, leave/attendance.
- The Frappe HR bridge adds operational complexity at the worst possible time. Each sync bug we hit during the 300-employee push directly cuts onboarding capacity.
- The custom letter pipeline (our biggest unique contribution) is nice-to-have, not need-to-have. greytHR's stock letters + their built-in document module can replace it for the 60-day push.
- Pivoting back to a single source of truth (greytHR-only) simplifies HR's mental model.

**Decision**: keep the Frappe HR bridge in production-stable state but stop active development. HR uses greytHR for everything during the 300-employee push. Re-evaluate at day 90.

**What stays in production**:
- Daily sync continues (6 AM IST). If HR wants letters from greytHR-synced data they can still trigger them.
- All deployed endpoints continue to work.
- No code is removed.

**What stops**:
- No new features added to the Frappe bridge during the 60-day window.
- No reactive bug fixes unless something breaks badly enough to affect production.

---

## 13. How to Resume

If you (or a future developer) come back to this project — perhaps because greytHR's stock features didn't meet a specific need — here's the resumption path:

### Day 1 — Orientation
1. Read this file (you're doing it now)
2. Read `CLAUDE.md` for coding conventions (still valid)
3. Read `CHANGELOG.md` end-to-end — it's the detailed log of every change with rationale. Skim sections relevant to what you're resuming.
4. Read `PLAN.md` for the original phase plan (some phases are deferred, see §4)

### Day 2 — Environment setup
1. Pull latest from GitHub: `git pull origin main`
2. Install Python deps: `pip install -r requirements.txt`
3. Run tests: `python -m pytest greythr_bridge/tests/ -q` — should show 261+ passing
4. SSH into Frappe Cloud bench (via dashboard "SSH Access" — bench ID may have changed, see §8 gotcha #13)
5. Verify the site is up: open https://hr.globexdigital.ai → log in → check workspace

### Day 3 — Reconciliation
1. Trigger "Sync from greytHR Now" — see if it's still healthy
2. Run `list_employees_missing_holiday_list` — should be 0; if not, run `setup_letter_placeholders`
3. Run `list_ghost_employees` — see if data integrity is still healthy
4. Run the most recent Sync Log entry — check `records_failed`. If non-zero, debug with `inspect_greythr_employee` for the failing IDs.

### Day 4+ — Decide what to extend
The deferred items (§4) are candidates:
- DocType export to fixtures (hygiene)
- Data quality dashboard cards
- Phase 6 push-back to greytHR
- Or something new entirely

### If reviving after a major Frappe HR / greytHR version change
- Frappe HR (`hrms`) may have changed APIs; re-verify all hooks (especially `on_submit` on Employee Separation, Job Offer, SSA)
- greytHR may have changed API endpoints; re-verify GreytHRClient calls
- Re-run `inspect_greythr_employee?greythr_id=1` to confirm response shape matches the mapper

### Killer question to ask before reviving
**"What specifically can't greytHR do that justifies the Frappe HR bridge?"**

If the answer is "custom-branded letters" — the letter pipeline is the most reusable piece; can be lifted out into its own app. Greythr docs + Word merge + DocuSign may be enough.

If the answer is "specific workflows" — the workspace + Client Scripts pattern is reusable.

If the answer is "I just like Frappe better" — that's not enough justification. Use greytHR.

---

**End of manual.** Last updated 2026-05-26, commit `8988fd8`.

For per-feature change history: see `CHANGELOG.md`.
For architecture-decision-record style design choices: search CHANGELOG for "Decision:" sections.
For specific bug rationale: search CHANGELOG for the bug number or symptom.
