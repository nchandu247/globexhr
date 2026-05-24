# Changelog

All notable changes to `greythr_bridge` are documented here.
Format: `## [Unreleased]` until first production deploy, then version + date.

---

## [Unreleased]

### Phase 0 — Scaffolding

- ✅ **Task 0.5:** API user `globexdigital` created in greytHR Admin with the following
  roles: Salary API, Employee API, User API, Employee API read access,
  Employee Document API access.

- ✅ **Task 0.6:** greytHR OAuth and data endpoints verified via PowerShell.
  Confirmed working auth pattern:
  - OAuth endpoint: `https://globex.greythr.com/uas/v1/oauth2/client-token`
    (tenant host — different from the data API host `api.greythr.com`)
  - OAuth credential delivery: HTTP Basic auth header (not body params)
  - Data calls: `ACCESS-TOKEN: <token>` header (no Bearer prefix)
  - Tenant routing: `x-greythr-domain: globex.greythr.com` required on every data call
  - Token TTL: ~45 days
  - Silent failure trap: 200 + `text/html` = auth rejected; must validate Content-Type
  - Confirmed endpoints (JSON + `{"data": [...]}` wrapper):
    - `GET /employee/v2/employees`
    - `GET /employee/v2/employees/work`
    - `GET /employee/v2/employees/separation`
    - `GET /payroll/v2/salary/repository`
  - Observed field keys captured in `NOTES_greythr_api.md`

- ⬜ **Task 0.0 (partial):** Write endpoint availability (POST employee, POST docs,
  POST salary revision) not yet verified with the correct auth pattern.
  Required before Phase 6 begins.

- ✅ **Task 0.1:** Frappe Cloud site created at `globex.m.frappe.cloud` (AWS Mumbai region).
- ✅ **Task 0.2:** Frappe HR (`hrms`) installed at site creation.
- ✅ **Task 0.7:** Custom domain `hr.globexdigital.ai` configured in Frappe Cloud; SSL provisioned.
- ⬜ **Task 0.3:** Setup wizard — company, country, currency, fiscal year. Run next.
- ⬜ **Task 0.4:** Timezone `Asia/Kolkata`, date format `dd-mm-yyyy`. Run after 0.3.
- ✅ **Task 0.9:** GitHub repo created at `https://github.com/nchandu247/globexhr`.
  Scaffold committed: pyproject.toml, hooks.py, modules.txt, all package stubs,
  .gitignore, .github/workflows/ci.yml, README.md.
- ✅ **Task 0.10 (partial):** Frappe Cloud V16 bench "GlobexHR" deployed successfully.
  Workaround applied: official `frappe/erpnext` (version-16) must be present in the bench
  alongside `frappe/hrms` due to a Frappe Cloud account-level resolver bug that
  auto-adds a broken ERPNext fork (`vorasmit/erpnext`) otherwise.
  ERPNext will NOT be installed on the site — bench only.
  Raise support ticket with Frappe Cloud to clean up the broken fork registrations.
- ✅ **Task 0.10 (complete):** Bench GlobexHR deployed successfully with all 6 apps:
  frappe v16.18.2, Builder v1.24.6, Insights v3.9.9, ERPNext (frappe/erpnext) 799d6d1,
  HR & Payroll v16.7.0, greytHR Bridge cc0155a. Site created on AWS Mumbai, ₹820/mo plan.
- ✅ **Fix:** Renamed module from `greytHR Bridge` to `greytHR` and created
  `greythr_bridge/greythr/` module directory. Frappe was trying to import
  `greythr_bridge.greythr_bridge` (name collision with app package). Commit `de4ffbb`.
- ✅ **Site created** on GlobexHR private bench (AWS Mumbai). greythr_bridge installs clean.
- ✅ **Task 0.3:** Setup wizard completed — Globex Digital Solutions Pvt Ltd, India, INR, FY April 2025.
- ✅ **Task 0.4:** Timezone set to Asia/Kolkata, date format dd-mm-yyyy.
- ✅ **Task 0.7:** hr.globexdigital.ai CNAME configured in Cloudflare (DNS only, grey cloud).
- ✅ **Task 0.8:** HR team invited with HR Manager role. Personal admin user created.

## Phase 0 — COMPLETE

---

## [Unreleased] — Phase 1

### Phase 1 — Settings + API Client

- ✅ **Tasks 1.3–1.5, 1.7:** Core API client implemented and tested.
  - `api/exceptions.py` — GreytHRError, GreytHRAuthError, GreytHRRateLimitError,
    GreytHRServerError, GreytHRClientError, ZohoSignError
  - `utils/retry.py` — @retry decorator with exponential backoff (1s/2s/4s, 3 attempts)
  - `utils/rate_limiter.py` — @rate_limited decorator (10 req/sec via ratelimit library)
  - `utils/logging.py` — PII-safe frappe.log_error wrapper
  - `utils/idempotency.py` — make_key() helper
  - `api/client.py` — GreytHRClient with correct greytHR auth (Basic OAuth on tenant host,
    ACCESS-TOKEN header, x-greythr-domain header, Content-Type HTML trap, one-shot retry)
  - `tests/conftest.py` — frappe + ratelimit mocks, shared fixtures
  - `tests/test_client.py` — 11 tests, all passing offline
- ✅ **Tasks 1.1, 1.2:** greytHR Settings + greytHR Sync Log DocTypes created via
  Frappe v16 Form Builder. Permissions set (System Manager full, HR Manager read).
- ✅ **Task 1.6:** test_connection verified live on site — HTTP 200, code runs cleanly,
  Settings read correctly, dry_run mode works. Phase 1 fully verified.

## Phase 1 — COMPLETE

---

## [Unreleased] — Phase 2

### Phase 2 — Pull Employees (code complete, UI tasks deferred)

- ✅ **Task 2.3:** `mappers/employee_mapper.py` — greythr_to_frappe() with date conversion,
  status inference from leavingDate, fitToBeRehired→custom_fit_to_rehire, email→company_email.
- ✅ **Task 2.4:** `api/employee.py` — list_employees(), get_employee(),
  list_employee_work_details(), list_employee_separations().
- ✅ **Task 2.5:** `tasks/pull_employees.py` — paginated pull with matching priority chain,
  duplicate email detection, sync log, failure notifications, dry_run support.
- ✅ **Task 2.8:** 22 tests passing (test_mappers.py + test_pull_employees.py).
  Fixed conftest mock reset bug (call_args_list accumulated across tests).
- ✅ Pre-task decisions: fitToBeRehired=capture, onboardingStatus=ignore, email=company_email.
- ✅ **Task 2.1:** greytHR Employee Mapping DocType created (Frappe v16 Form Builder).
  Fields: frappe_employee (Link), greythr_employee_id, greythr_employee_no, sync_status
  (Select), last_sync_error, first/last/last_pushed timestamps.
- ✅ **Task 2.2:** Custom fields confirmed on Employee (all 5 existed from earlier session).
  Custom fields added to Job Offer (custom_zoho_sign_request_id, custom_zoho_sign_nda_request_id,
  custom_zoho_sign_signed_at, custom_signed_pdf_pushed) and Salary Structure Assignment
  (custom_pushed_to_greythr). All UI tasks across phases batched and complete.
- ✅ **Task 2.6:** Scheduler wired — pull_employees.run fires every 15 min. Confirmed live.
- ✅ **Phase 2 live verified:** 340 employees pulled, 0 failed, Status: Success.
  Three bugs fixed during live testing:
  1. Frappe Datetime field passed as object to requests URL params → convert to string
  2. Frappe v16 iterates over datetime during Datetime field validation → store as string
  3. greytHR Settings version conflict (GreytHRClient saves settings mid-run) → db.set_value

## Phase 2 — COMPLETE

---

## [Unreleased] — Phase 3

### Phase 3 — Pull Salary Structures

- ✅ **Task 3.1:** `api/payroll.py` — get_salary_repository(), get_employee_salary(),
  list_employee_salaries() (employee salary endpoints pending Essential plan verification).
- ✅ **Task 3.2:** `mappers/salary_mapper.py` — recursive tree-walk to flatten greytHR
  salary tree, component_to_frappe() with known abbreviation table, type mapping.
  14 mapper tests passing.
- ✅ **Task 3.3 (partial):** `tasks/pull_salary_structures.py` — Salary Component sync
  only. Employee SSA mirroring deferred until employee salary endpoint verified.
- ✅ **Task 3.4:** Scheduler wired — pull_salary_structures.run daily at 2AM IST.
- ✅ **Phase 3 live verified:** 176 salary components synced (175 created, 1 updated,
  0 failed). Tree-walk correctly flattened 3 top-level greytHR salary trees.
- ⬜ **Task 3.5:** "Sync Salary from greytHR" button on Employee form. Deferred (UI task).
- ⬜ **Employee SSA mirroring** (task 3.3 remainder): deferred until employee salary
  endpoint verified on Essential plan.

## Phase 3 — COMPLETE (partial — SSA mirroring deferred)

---

## [Unreleased] — Phase 5

### Phase 5 — E-Signature Integration

- ✅ **Task 5.1:** Zoho Sign business account on India DC (in.zoho.com).
  API credit plan selected (₹6/credit — more cost-effective than user plan).
- ✅ **Task 5.2:** Webhook configured in Zoho Sign console pointing to
  `https://gdshr.m.frappe.cloud/api/method/greythr_bridge.webhooks.zoho_sign.callback`.
  Events: Completed by all, Expires, Recalled, Declined.
  Security: HMAC-SHA256 (X-ZS-WEBHOOK-SIGNATURE header, base64 encoded) + timestamp.
- ✅ **Task 5.3:** `api/zoho_sign.py` — OAuth token refresh (client_credentials flow via
  accounts.zoho.in), send_for_signature (multi-signer ordered), get_signed_document,
  resend_signing_request, verify_webhook_hmac (base64 HMAC-SHA256).
- ✅ **Task 5.4:** `hooks_handlers/job_offer.py` — on_offer_submitted enqueues NDA send;
  send_offer_letter triggered by webhook after NDA completes (NDA-first flow).
- ✅ **Task 5.5:** `webhooks/zoho_sign.py` — HMAC + timestamp verified callback;
  dispatches NDA completion, offer completion, decline, expiry to queue=short.
- ✅ **Task 5.7:** `tasks/stalled_signings.py` — daily check for unsigned offers >28 days.
- ✅ Credentials configured: Client ID, Client Secret, Refresh Token, Webhook Secret,
  Account ID stored in greytHR Settings. Access Token auto-cached on first API call.
- ✅ 59 tests passing.
- ⬜ **Task 5.6:** "Resend Signing Request" button on Job Offer form. Deferred (UI task).
- ✅ **Task 5.6 (unblocked):** `_generate_pdf()` now uses python-docx mail merge
  (see Phase 4 below) — no longer blocked on Frappe Print Formats.

## Phase 5 — COMPLETE (5.6 UI button deferred)

---

## [Unreleased] — Phase 4

### Phase 4 — Letter Templates (python-docx mail merge approach)

- ✅ **Architecture decision:** Replaced Frappe HTML/Jinja Print Formats with
  `docxtpl` (Jinja2 inside DOCX) + LibreOffice headless PDF conversion.
  Rationale: original DOCX templates already exist and are HR-approved;
  recreating them pixel-perfectly in HTML/CSS was not feasible.
- ✅ `greythr_bridge/letters/__init__.py` — module root.
- ✅ `greythr_bridge/letters/merger.py` — `merge_to_pdf(template, context)` and
  `build_offer_context(doc)` with full salary field mapping, INR formatting,
  ESI/PF/medical conditional logic.
- ✅ `greythr_bridge/letters/pdf_convert.py` — `docx_to_pdf_bytes()` via
  LibreOffice headless subprocess (60s timeout, temp dir cleanup).
- ✅ `greythr_bridge/hooks_handlers/job_offer.py` updated — `_generate_pdf(doc)`
  now calls `merge_to_pdf("offer_letter.docx", build_offer_context(doc))`.
- ✅ `greythr_bridge/templates/letters/PLACEHOLDERS.md` — guide for HR to add
  `{{ variable }}` placeholders to their Word templates.
- ✅ `docxtpl` added to `requirements.txt`.
- ✅ 7 new tests in `tests/test_letters.py` — all passing offline.
- ✅ **Context builder extended** to match actual HR template placeholders
  (analyzed from `Globex Digital Solutions _ Template _ Offer Letter.pdf`):
  - All numeric values now bare (no `₹` prefix), Indian comma format (`6,00,000`)
  - Added annual versions of every salary component (`*_annual` keys)
  - Added totals: `total_deductions_monthly/annual`, `employer_deductions_annual`
  - Added `band`, `current_date`, `gross_annual`, `net_take_home_annual`
  - Added 10 candidate-detail / offer-term keys: `candidate_email`, `candidate_mobile`,
    `candidate_address`, `work_location`, `reporting_to`, `probation_period`,
    `notice_period`, `joining_bonus`, `variable_pay_annual`, `acceptance_deadline`
- ✅ `fixtures/custom_field.json` — 8 new Job Offer custom fields auto-installed
  on `bench migrate`: `custom_band`, `custom_work_location`, `custom_reporting_to`
  (Link → Employee), `custom_probation_period`, `custom_notice_period`,
  `custom_joining_bonus` (Currency), `custom_variable_pay_annual` (Currency),
  `custom_acceptance_deadline` (Date). Defaults: Hyderabad / 6 months / 60 days.
- ✅ `hooks.py` fixtures extended to include `Custom Field` for Job Offer,
  Employee, and Salary Structure Assignment.
- ✅ Test suite expanded to 15 tests (was 7) — all passing offline.
- ✅ **`scripts/build_offer_template.py`** — one-shot DOCX rewriter. Reads the
  HR-approved `templates/Globex Digital Solutions _ Template _ Offer Letter.docx`,
  applies 21 `«…»` → `{{ }}` substitutions + fixes `{{ candidate_name }` typo,
  saves to `greythr_bridge/templates/letters/offer_letter.docx`. Preserves
  fonts, logo, tables, page layout.
- ✅ **`offer_letter.docx` built** — 65 placeholders / 36 unique variables.
  Smoke-tested: docxtpl renders cleanly, all sample values appear in output.
- ⬜ **End-to-end test on live site:** Submit a Job Offer → PDF generates
  via LibreOffice headless → sent to Zoho Sign.

---

## [Unreleased] — Phase B (2026-05-22)

### Phase B — Seven additional letter types (HTML+WeasyPrint, all-in-one deploy)

Builds on the Phase A offer-letter pipeline. Two letter families:

- **Zoho-signed** (uploaded to Zoho Sign with embedded text tags): Consultant Offer, Intern Offer
- **PDF-only** (rendered + attached + emailed, no signature flow): Increment, Promotion, Experience, Relieving, Service Certificate

#### Custom fields (12 new, fixtures auto-installed on `bench migrate`)

- **Job Offer:** `custom_offer_type` (Select: Employee/Consultant/Intern), `custom_engagement_duration_months`, `custom_professional_fees_monthly`, `custom_stipend_monthly`, `custom_internship_duration_months`
- **Salary Structure Assignment:** `custom_annual_ctc`, `custom_send_increment_letter`, `custom_increment_letter_generated`
- **Employee Separation:** `custom_send_experience_letter`, `custom_send_relieving_letter`
- **Employee:** `custom_promotion_letter_attached`, `custom_service_certificate_issued_at`

#### Shared infrastructure

- `letters/non_signing.py` — `generate_and_deliver()`: render PDF via `merge_to_pdf_via_html`, attach as private File, email with fallback chain (company → personal, reversed for separation letters)
- `letters/dispatch.py` — `dispatch_offer_letter(doc)` selects template + context builder from `custom_offer_type`
- `letters/merger.py` — 6 new context builders (`build_consultant_offer_context`, `build_intern_offer_context`, `build_increment_context`, `build_promotion_context`, `build_experience_context`/`build_relieving_context`, `build_service_certificate_context`) + helpers (`_resolve_signatory_name`, `_resolve_employee_email`, `_tenure`)
- `letters/pdf_check.py` — extended with `hr_signature_image_*` health-check fields
- `templates/letters/html/_styles.css` — `.hr-sig-block / .hr-sig-image / .hr-sig-line / .hr-sig-label` classes for non-signing letters
- `templates/letters/html/img/hr_signature.png` — HR signatory image embedded into PDF-only letters

#### Document event handlers / manual triggers

- `hooks.py` — added `doc_events` for `Salary Structure Assignment` (on_submit) and `Employee Separation` (on_submit); added `Client Script` to fixtures filter; added `Employee Separation` to Custom Field fixtures
- `hooks_handlers/salary_structure_assignment.py` — `on_ssa_submitted` enqueues `send_increment_letter` background job (skip if no prior SSA or no CTC delta)
- `hooks_handlers/employee_separation.py` — `on_separation_submitted` enqueues `send_experience_letter` and/or `send_relieving_letter` based on the two checkboxes; both emails prefer `personal_email` (company email may already be deactivated)
- `hooks_handlers/employee.py` — whitelisted `send_promotion_letter()` + `send_service_certificate()` (HR/System Manager only, Active-status check on service cert), both run as background jobs
- `hooks_handlers/job_offer.py` — `_generate_document()` now uses `dispatch_offer_letter(doc)` (instead of hardcoded `offer_letter.html`)

#### Client Scripts (fixtures, auto-installed)

- `fixtures/client_script.json` — two scripts under the "Letters" button group on the Employee form:
  - "Generate Promotion Letter" — dialog asks old/new designation + effective date + optional notes
  - "Generate Service Certificate" — confirm dialog only; restricted to Active employees
  - Both gated by `frappe.user_roles.includes('HR Manager' || 'System Manager')`

#### Templates (7 new, all extend `_base.html` with brand watermark + letterhead)

- `consultant_offer_letter.html` — engagement language (not employment), GST clause, IP clause, two Zoho Sign tags
- `intern_offer_letter.html` — stipend (not salary), learning objectives, certificate-of-completion promise, two Zoho Sign tags
- `increment_letter.html` — old-vs-new CTC comparison table, embedded HR signature image
- `promotion_letter.html` — old → new designation, effective date, optional manager notes
- `experience_letter.html` — "To Whom It May Concern", tenure (`X years and Y months`), conduct certification
- `relieving_letter.html` — confirmation of relieving + clearance status
- `service_certificate.html` — current-employment confirmation with tenure-so-far

#### Tests

- `tests/test_letters.py` extended from 89 → 114 passing (3 skipped). Added:
  - `_FakeJobOfferConsultant`, `_FakeJobOfferIntern` fixtures
  - `TestConsultantOfferContext` (2 tests), `TestInternOfferContext` (2 tests)
  - `TestDispatcher` (4 tests — Employee/Consultant/Intern/missing-field routing)
  - `TestPhaseBHTMLRendering` (7 tests — one per template, render via Jinja2 with StrictUndefined)
  - `TestTenureCalculation` (4 tests — same year, multi-year, partial month, less-than-a-month)
  - `TestPhaseBCustomFields` (1 test verifying all 12 new fields present in `fixtures/custom_field.json`)

- Local smoke test: rendered all 7 templates outside Frappe with realistic contexts — all parsed cleanly, no undefined variables.

- ⬜ **End-to-end test on live site (post-deploy):** Verify each of the 7 letter types end-to-end — fetch + bench update + migrate, then trigger each flow and confirm PDF/attachment/email.

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
- ✅ **`tests/test_workspace_fixture.py`** — 8 offline validation tests: JSON parses, 15 shortcuts present, every `custom_*` URL token references a fieldname in `custom_field.json` (with allowlist for two Phase A live-only fields not yet exported), no `content` blob, hooks.py fixtures list updated
- ✅ Test suite: **122 passing** (was 114), 3 skipped
- ⚠️ **Known gap:** `custom_zoho_sign_request_id` and `custom_zoho_sign_signed_at` exist on the live site (created via Customize Form during Phase A) but are not yet in `fixtures/custom_field.json`. Tracked in the test allowlist `_PHASE_A_LIVE_ONLY_FIELDS`. Separate PR will round-trip them so fresh environments install identically.
- ⬜ **Live-site verification (post-deploy):** Fetch + Update Bench + Migrate; refresh `/app`; confirm `greytHR` sidebar entry appears with 15 cards and each card lands on the expected URL.

**Workspace authoring caveat:** This workspace is shipped as a fixture and is system-managed. Edits made via the in-browser Workspace Editor will be overwritten on the next `bench migrate`. All future workspace changes should go via PR to `fixtures/workspace.json`.

### Workspace v2 — fixes for Frappe v16 fixture-loader rejection

First deploy of the workspace fixture did NOT appear in the sidebar. Root cause was two stacked bugs:

1. **Missing top-level `app` field** — Frappe v16 runs a `Removing orphan Workspaces` step at the end of every `bench migrate` that deletes any Workspace whose `app` is empty. Our fixture set `module` but not `app`, so the workspace was inserted then immediately removed in the same migrate.
2. **Invalid shortcut `type: "URL"`** on the greytHR Settings card — Frappe v15/v16 Shortcut child-table `type` enum only accepts `DocType`, `Report`, `Page`, `Dashboard Chart`. The invented `URL` value caused the whole Workspace insert to roll back silently.

Fixes shipped:

- ✅ Added `"app": "greythr_bridge"` and `"for_user": ""` to the workspace top-level record
- ✅ Changed greytHR Settings shortcut: `type: "DocType"` + `link_to: "greytHR Settings"` + explicit `url: "/app/greythr-settings"` (the url field overrides the click destination, working around bug [frappe#37623](https://github.com/frappe/frappe/issues/37623) for Single doctypes while keeping the validator happy)
- ✅ Two new test assertions added — `test_every_shortcut_type_is_valid_enum` and `test_doctype_shortcuts_have_link_to` — would have caught both bugs before deploy. Plus `test_required_top_level_fields_present` now asserts `app == "greythr_bridge"`.
- ✅ Test suite: **124 passing** (was 122), 3 skipped
- ✅ Spec updated (§5.1) to document the v16-required `app` field and the correct Single-doctype shortcut shape, so the next reader doesn't repeat the same mistake.

### Workspace v3 — root cause was the wrong file location, not the JSON

Even after v2 fixes (`app` field + valid shortcut type), the workspace STILL did not appear post-migrate. Deep source-code investigation (`frappe/model/sync.py`) found the real root cause:

**Public app-owned Workspaces are not shipped via `fixtures/` in Frappe v16.** They live in a per-module folder convention. Frappe HR, ERPNext, Insights and Builder all use this layout. Our `fixtures/workspace.json` was being inserted in the `Syncing fixtures...` step, then deleted seconds later in the `Removing orphan Workspaces` step of the SAME migrate, because the orphan-cleanup glob `<app>/**/workspace/**/*.json` didn't match `<app>/fixtures/workspace.json`.

Fix:

- ✅ **Deleted** `greythr_bridge/fixtures/workspace.json`
- ✅ **Created** `greythr_bridge/greythr/workspace/greythr/greythr.json` (single dict, not array)
- ✅ **Created** `greythr_bridge/greythr/workspace/__init__.py` and `.../greythr/__init__.py` (empty)
- ✅ **Removed** the `{"dt": "Workspace", ...}` entry from `hooks.py` fixtures list
- ✅ Test file updated to validate the new path and to assert hooks.py does NOT include Workspace
- ✅ Test suite: still 124 passing, 3 skipped
- ✅ Spec §5 rewritten to document the per-module folder convention and the root cause, so future contributors don't reinvent the same fixture-based mistake.

**Reference:** Frappe HR's recruitment workspace lives at [hrms/hr/workspace/recruitment/recruitment.json](https://github.com/frappe/hrms/blob/develop/hrms/hr/workspace/recruitment/recruitment.json) — same convention.

### Workspace v4 — add `content` blob to actually render cards

After v3 fixed the file location, the sidebar entry appeared and the URL resolved — but the workspace page got stuck on skeleton placeholders that never resolved into cards. Source-verified root cause: Frappe v16 renders the workspace from a separate `content` field (a stringified JSON array of widget descriptors), NOT from the `shortcuts[]` child table directly. The renderer is `editor.render({ blocks: this.content || [] })` — null content means empty editor blocks, which means `remove_page_skeleton()` is never called.

Earlier spec said "omit `content` so Frappe auto-generates it." That was wrong for v16: auto-generation only happens when a Workspace is saved via the in-browser editor; file-loaded workspaces have null `content` forever.

Fix:

- ✅ Added a `content` field to `greythr.json` — a stringified JSON array of 21 widgets: 6 section headers (col=12, one per lifecycle group) + 15 shortcut tiles (col=4, three per row). All `shortcut_name` values match `shortcuts[].label` exactly.
- ✅ Test file updated:
  - Removed `test_no_content_blob` (which actively asserted the wrong thing)
  - Added `test_content_present_and_well_formed` — content exists, parses as JSON array, non-empty
  - Added `test_content_widget_shape` — every widget has id/type/data + valid type enum + col
  - Added `test_content_shortcut_names_match_shortcut_labels` — every `shortcut_name` in content must match a label in `shortcuts[]` (catches the next likely silent-failure: empty cards from typos)
- ✅ Spec §5.3 updated with the v4 correction (and explicit warning that earlier "omit content" guidance was wrong)
- ✅ Test suite: **126 passing** (was 124), 3 skipped

**Reference:** widget schema verified against [hrms/payroll/workspace/payroll/payroll.json](https://github.com/frappe/hrms/blob/develop/hrms/payroll/workspace/payroll/payroll.json) and Frappe v16 renderer source at [workspace.js](https://github.com/frappe/frappe/blob/develop/frappe/public/js/frappe/views/workspace/workspace.js).

---

## [Unreleased] — Zoho Sign webhook hardening (2026-05-22)

### Stuck "Awaiting Response" status — root cause + defensive fix

**Symptom:** Two Job Offers (Megahna Reddy, Rajyalakshmi Nalluri) remained on `status = Awaiting Response` even though both signers had signed in Zoho Sign. Bhuvan and Chandu showed `Accepted`, so the code worked for some offers but not others.

**Root cause:** the `custom_zoho_sign_signed_at` field did not exist on the Job Offer DocType. Confirmed via Frappe DataError:
> `Field not permitted in query: custom_zoho_sign_signed_at`

The webhook's `RequestCompleted` handler was doing TWO `frappe.db.set_value` calls in one transaction:
```python
frappe.db.set_value("Job Offer", docname, "status", "Accepted")           # succeeds
frappe.db.set_value("Job Offer", docname, "custom_zoho_sign_signed_at", ...) # SQL error
```
When the second `set_value` hit the missing column, MariaDB rolled back the **entire** transaction — including the `status` update from one line above. The outer `try/except Exception` swallowed the error, returned 200 OK to Zoho, and from the outside it looked fine. Nothing actually saved.

(Previously-marked "Accepted" offers had their status changed manually via the form, not by the webhook.)

**Earlier CHANGELOG note retraction:** the v1 Workspace entry claimed `custom_zoho_sign_request_id` and `custom_zoho_sign_signed_at` "exist on the live site (created via Customize Form during Phase A)." That was a documentation assumption, not a verified fact. The `_request_id` field did exist; the `_signed_at` field did not. The note is now corrected by this fix.

**Fixes shipped:**

- ✅ **`fixtures/custom_field.json`** — added both `custom_zoho_sign_request_id` (Data, read-only) and `custom_zoho_sign_signed_at` (Datetime, read-only) on Job Offer with `module=greytHR`. Auto-installs on `bench migrate` for fresh deployments.
- ✅ **`webhooks/zoho_sign.py`** — new `_safe_set_value(doctype, name, field, value)` helper that:
  1. Checks `frappe.get_meta(doctype).has_field(field)` first — if missing, logs `"greytHR Webhook Field Missing"` to Error Log and returns False (no SQL fired, no transaction poisoned)
  2. On successful `set_value`, explicit `frappe.db.commit()` — per-field durability so a later failure can't undo earlier writes
  3. On unexpected DB error, `frappe.db.rollback()` + log + return False — next call works cleanly
- ✅ All three `set_value` call sites in the webhook routed through `_safe_set_value`: `RequestCompleted` handler, `_handle_declined`, `force_complete_offer`.
- ✅ **`tests/test_zoho_sign.py`** — three focused tests for `_safe_set_value`: field exists path, field missing path (must NOT call set_value), DB error path (must rollback).
- ✅ **`tests/test_workspace_fixture.py`** — removed the `_PHASE_A_LIVE_ONLY_FIELDS` allowlist; the workspace test now strictly requires both `custom_zoho_sign_*` fields to be in the fixture (no allowlist escape hatch).
- ✅ Test suite: **129 passing** (was 126), 3 skipped.
- ⬜ **Stranded offers recovery (post-deploy):** HR to call `force_complete_offer` for Megahna Reddy (HR-OFF-2026-00004) and Rajyalakshmi Nalluri (HR-OFF-2026-00003) once this fix is live — the endpoint now uses `_safe_set_value` so it actually persists status + signed_at instead of silently rolling back.

**Why this matters beyond Zoho Sign:** the `_safe_set_value` pattern (check meta before SQL + commit-per-field) is a general defense against the "missing custom field rolls back the whole transaction" trap. Any future webhook or background job that writes multiple fields in one handler should follow the same pattern.

---

## [Unreleased] — Employee Data Integrity, Phase 1 (2026-05-23)

### Read-only audit endpoint for ghost / unmapped Employees

Discovered while investigating workspace cards: Frappe Employee `HR-EMP-00684` opens with all fields blank (first_name, last_name, email, date_of_joining empty). Counter at 684 but only 332 records exist — 352 were deleted historically. Root cause: `pull_employees.py` accepts greytHR rows where critical fields are null/missing (mapper records `_mapping_errors` but doesn't gate creation), then `frappe.new_doc("Employee")` with `ignore_mandatory=True` creates a half-empty "ghost" record.

User-specified hard constraint: greytHR is production payroll; no Employee or `greytHR Employee Mapping` deletion at any stage. Saved as memory rule `never_delete_employee_records.md`.

Approved plan: 6 phases, all non-destructive — read-only audit → heal at greytHR source → prevent new ghosts in pull code → UI fixes for `GDS####` display and ghost filtering → data-quality dashboard → missing-48 investigation. Full plan committed to `docs/superpowers/specs/2026-05-23-employee-data-integrity-plan.md`.

This commit implements **Phase 1 only** — the read-only audit. No data touched.

- ✅ **`greythr_bridge/utils/data_quality.py`** — new module. Single endpoint `list_ghost_employees()` (whitelisted; restricted to HR Manager / System Manager) returns three categories:
  - `ghosts` — Employees with blank `first_name` (created by pull task from incomplete greytHR data)
  - `mapped_clean` — Employees with first_name AND a greytHR mapping (well-formed records)
  - `frappe_only` — Employees with first_name but NO greytHR mapping (manually created, never synced)
  - Plus a `summary` with counts of each category and total mappings
  - Three `frappe.get_all()` calls (Employees with no first_name, Employees with first_name, Employee Mappings). Zero writes.
- ✅ **`greythr_bridge/tests/test_data_quality.py`** — 5 offline tests including a critical invariant: `test_list_ghost_employees_does_not_write_to_db` spies on every write method (`set_value`, `sql`, `delete`, `commit`, `rollback`, `new_doc`, `delete_doc`, `rename_doc`) and asserts none were called.
- ✅ **`greythr_bridge/tests/conftest.py`** — small fix: `patch_frappe` fixture now also resets `side_effect` on commonly-scripted mocks (`get_all`, `db.set_value`) so iterator state from one test doesn't leak into the next and cause StopIteration.
- ✅ Test suite: **134 passing** (was 129), 3 skipped.

**How to use after deploy:**

Call from any HR Manager session:
```
/api/method/greythr_bridge.utils.data_quality.list_ghost_employees
```

Returns JSON. HR reviews counts and per-record details, then proceeds with **Phase 2** (open each ghost in greytHR portal, fill missing data; next 15-min sync auto-heals Frappe via the existing update path). No code change needed for Phase 2 — HR action only.

**Next phases** (separate commits, only after Phase 1 audit reviewed):
- Phase 3: code guard in `_sync_one` to skip new ghosts going forward
- Phase 4: UI fixes (employee_number column in Employee list, autocomplete filter, hide ghosts from pickers)
- Phase 5: data-quality dashboard cards on the workspace
- Phase 6: missing-48 investigation (read-only diff against greytHR API)

---

## [Unreleased] — Sync diagnostics + counter-honesty fix (2026-05-23)

### Phase 1 audit revealed a deeper bug: sync claims success while doing nothing

When HR ran the Phase 1 audit (`list_ghost_employees`), the result showed **all 332 records are ghosts** — 100% have `first_name`, `custom_greythr_employee_id`, and `custom_greythr_last_synced` blank. Yet the most recent successful `pull_employees` run reported `records_processed: 340, records_updated: 340, records_failed: 0`. Contradiction: sync claims 340 updates while not a single record was actually enriched.

Root cause of the misleading counter (proven by code inspection):

In `tasks/pull_employees.py::_sync_one`, the update path was:
```python
if changed:
    frappe_employee.save(ignore_permissions=True)
_upsert_mapping(...)
return "updated"  # ← always "updated", even when changed=False
```

The function returned `"updated"` regardless of whether anything actually changed. The sync log counter incremented for every matched record, masking the fact that `changed=False` on every iteration → save never ran → records stayed blank.

The deeper question — **why is changed=False everywhere?** — is the next investigation. Likely answers:
- (A) greytHR's API response shape doesn't match mapper expectations (mapper produces sparse output → no field differs)
- (B) Frappe HR validate hooks silently reject Employee saves when `first_name` is empty
- (C) Mappings created by the 2026-05-19 bulk import have empty `greythr_employee_id`, so sync fall-through matches by email/employee_number but the matched mapper output happens to equal the existing record

This commit ships the tooling to answer that definitively, plus a counter-accuracy fix so future sync logs don't lie.

#### Changes

- ✅ **`greythr_bridge/utils/sync_diagnostics.py`** — new module with two read-only endpoints (System Manager only):
  - **`inspect_sync_for_employee(employee_name, save_dry_run=True)`** — full pipeline diagnostic for ONE employee. Returns: current Frappe record state, mapping row, raw greytHR API response, extracted employee payload, mapper output, mapper errors, would-change diff (field-by-field). With `save_dry_run=false`, also attempts the save and captures result/traceback (with explicit `frappe.db.commit()` or `rollback()` so partial state never persists silently).
  - **`list_recent_sync_errors(limit=20)`** — recent Error Log entries with `title LIKE %greytHR%`. Companion to the audit endpoint.

- ✅ **`greythr_bridge/tasks/pull_employees.py`** — counter-honesty fix in `_sync_one`:
  ```python
  return "updated" if changed else "skipped"
  ```
  Sync logs now accurately reflect what was actually persisted. After deploy, expect the next sync run to show `records_updated: 0, records_skipped: ~332` — which is the truth that was previously hidden behind `records_updated: 340`.

- ✅ **`greythr_bridge/tests/test_pull_employees.py`** — new test `test_existing_employee_no_changes_returns_skipped` that pins the counter-honesty behaviour so it can't regress.

- ✅ **`greythr_bridge/tests/test_sync_diagnostics.py`** — 8 new tests covering: System Manager role check, missing mapping, empty greythr_employee_id, full happy-path dry run, opt-in save success, save exception capture (with rollback), list_recent_sync_errors filtering + permission.

- ✅ Test suite: **143 passing** (was 134), 3 skipped.

#### How to use after deploy

1. **Identify a target employee** from the Phase 1 audit (any record from the `ghosts` list, e.g., `HR-EMP-00869` which has `employee_number: "GDS0234"`).

2. **Run the diagnostic** as System Manager:
   ```
   https://hr.globexdigital.ai/api/method/greythr_bridge.utils.sync_diagnostics.inspect_sync_for_employee?employee_name=HR-EMP-00869
   ```
   Returns JSON with `greythr_api_response` showing exactly what greytHR returned, and `mapper_output` showing what the mapper extracted. If the API response has full data but mapper output is sparse → field-name mismatch in mapper. If both are populated and `would_change_fields` is non-empty → the save mechanism is the suspect (run with `&save_dry_run=false` to see whether save fails).

3. **Optional — try the actual save** (still safe; rolls back on failure):
   ```
   …inspect_sync_for_employee?employee_name=HR-EMP-00869&save_dry_run=false
   ```
   If `save_result: "OK"` and the next audit run shows the record is no longer a ghost → save mechanism works; the bug is elsewhere in `_sync_one` (likely the mapper or matching logic). If `save_result: "FAILED: ..."` with a traceback → the traceback names the validate hook or layer that's rejecting the save. Either answer points us to the exact fix.

4. **Verify counter honesty** — the next scheduled sync (every 15 min) should now show realistic counts. If `records_skipped: ~332` and `records_updated: 0`, the bug is the no-change path. If `records_updated > 0` for the first time, something fixed itself (unlikely but possible).

#### Still no destructive operations

This commit continues the zero-deletion / zero-rename pattern. The optional save in the diagnostic is the only write — and only when the caller explicitly disables `save_dry_run`. Even then, it's a single record at a time and rolls back on any failure. The constraint from `memory/never_delete_employee_records.md` is honoured.

---

## [Unreleased] — Employee mapper fixes + missing custom fields (2026-05-23)

### Root cause finally pinned down: 3 custom fields don't exist + mapper expects wrong API shape

The `inspect_sync_for_employee` diagnostic shipped earlier revealed two stacked bugs:

**Bug 1: Three Employee custom fields the sync code writes to don't exist in Frappe meta at all.**
Confirmed via DevTools (`cur_frm.meta.fields.find(...)` returned `NOT IN META` for all three):
- `custom_greythr_employee_id` — referenced in pull_employees, mapper, data_quality, diagnostics
- `custom_greythr_last_synced` — referenced in pull_employees
- `custom_fit_to_rehire` — referenced in mapper

Without the fields existing in meta, `frappe.db.set_value`/`doc.set()` accept the assignment in memory but the SQL UPDATE silently skips unknown columns. `save()` reports OK (no exception). `modified` timestamp updates. But the actual values never persist. Sync log says "340 updated" while not a single record has `custom_greythr_employee_id` populated.

**Bug 2: greytHR's `/employees/{id}` response shape doesn't match what the mapper expects.**
The diagnostic captured an actual greytHR response (Sanjeev Gandla, GDS0234):
- `employeeId` returned as INTEGER (`270`), not string
- `firstName`/`lastName`/`middleName` all NULL — full name in combined `name` field ("Gandla Sanjeev")
- Dates in ISO `yyyy-MM-dd` format, not legacy `dd-MM-yyyy`
- `gender: "M"` (Frappe HR's Gender Link doctype expects "Male"/"Female")
- `mobile`, `personalEmail`, `dateOfBirth`, `leftorg` — useful fields the mapper ignored
- `designation` is a Link field — values must pre-exist in Designation doctype (deferred to follow-up)

Net effect: mapper produced a sparse output for every record. The few fields it did extract usually matched what was already in Frappe (e.g., `status: "Active"`), so `changed=False`, no save attempt, ghosts stayed ghosts.

### Fixes shipped

#### `greythr_bridge/fixtures/custom_field.json` — 4 new Employee fields

- `custom_greythr_employee_id` (Data, read-only, after employee_number)
- `custom_greythr_last_synced` (Datetime, read-only)
- `custom_greythr_full_name` (Data, read-only) — preserves greytHR's original combined name string for audit
- `custom_fit_to_rehire` (Check, default 0) — was already referenced in code

All 4 auto-install on `bench migrate` via the existing fixtures filter (`module=greytHR`).

#### `greythr_bridge/mappers/employee_mapper.py` — 9 bug fixes

1. **Stringify integer `employeeId`** — `str(270)` not int 270
2. **Name fallback chain** — prefer `firstName`/`lastName`/`middleName` if present (future-proof in case greytHR adds them); fall back to combined `name` field; full string goes into `first_name`, `last_name` stays empty (Indian naming conventions vary too much for safe automated split)
3. **Preserve original combined name** in new `custom_greythr_full_name` field for audit
4. **Dual date format support** in `_parse_date` — try `dd-MM-yyyy` then ISO `yyyy-MM-dd`
5. **Gender mapping** — explicit `M → Male`, `F → Female`, `O → Other` lookup table (Frappe HR's `gender` is a Link to Gender doctype, not raw string)
6. **dateOfBirth → date_of_birth** (new field mapping)
7. **mobile → cell_number** (new field mapping)
8. **personalEmail → personal_email** (new field mapping; null-preserving so Frappe edits aren't overwritten)
9. **leftorg flag as fallback** for status=Left logic (used when leavingDate is null — but status only flips when relieving_date can be set, so leftorg-without-date stays Active with mapper error logged)

Designation mapping intentionally **deferred** — it's a Link to the Designation doctype and would need target records to pre-exist (auto-create has side effects; will tackle in a follow-up after Designation pre-population).

#### `greythr_bridge/tests/test_mappers.py` — 16 new tests

- ISO date format parsing (both `_parse_date` direct + via greythr_to_frappe)
- Integer employeeId stringification
- Combined `name` → first_name fallback
- Decomposed firstName/lastName takes priority when present
- Full name preserved in custom_greythr_full_name
- Date of birth ISO parsing
- Gender M/F/Other → Male/Female/Other mapping
- Unknown gender values omitted + logged (don't break Frappe Gender Link)
- mobile → cell_number
- personal_email null-preserving (omit not overwrite)
- leftorg=true + leavingDate → status=Left + relieving_date set
- leftorg=true without leavingDate → stays Active + error logged
- leftOrg (camelCase variant) also accepted
- End-to-end smoke test with real captured greytHR response → no blocking errors

Test suite: **159 passing** (was 143), 3 skipped.

### After deploy + migrate + 15-min sync — expected outcome

| Before | After |
|---|---|
| All 332 records have `first_name: null` | first_name populated from greytHR `name` field (full combined name) |
| All 332 records have `custom_greythr_employee_id: null` | Populated with stringified greytHR ID |
| `custom_greythr_last_synced: null` everywhere | Populated with sync timestamp on every touched record |
| Sync log: `records_updated: 340, records_changed_in_db: 0` (the lie) | Sync log: `records_updated: ~300, records_skipped: ~30` (the truth) |
| `gender`, `date_of_birth`, `cell_number` mostly empty | Populated for every record greytHR has data for |
| ~hundreds of ex-employees showing Active | Records with `leftorg: true` + parseable `leavingDate` correctly flip to `status: "Left"` |
| Employee list shows blank name column | Real names visible |
| SSA Employee autocomplete unusable | Works — search by name |
| Workspace Recognition cards' Employee list unusable | Functional |

### Operational caveats HR should know

1. **Status flips to "Left" will happen automatically** for ex-employees who have a parseable leavingDate in greytHR. Frappe HR's Employee `on_update` may trigger side effects (disable linked User, exclude from active employee reports). This is correct behaviour — these employees genuinely left. But the volume may be noticeable on the first sync after this fix.

2. **Edits to greytHR-managed fields in Frappe will be overwritten on next sync.** Reminder of the one-way sync rule: `firstName`/`name`, `email`, `dateOfJoin`, `leavingDate`, `gender`, `dateOfBirth`, `mobile`, `personalEmail` — all owned by greytHR. To correct any of these, edit in greytHR portal; the sync brings it back to Frappe within 15 minutes.

3. **Data-quality issues at greytHR source remain** — 3 records have malformed `employee_number` values (`gds0115` lowercase, `Gds0943274` non-standard, `GSD0033` typo, `GDS034` missing leading zero). Those records still need HR cleanup in greytHR.

### Known gap (deferred to follow-up)

16 other custom fields are referenced in code but not in fixtures (`custom_basic_monthly`, `custom_hra_monthly`, salary breakdown fields used by Phase A offer letters; `custom_zoho_sign_nda_request_id`; `custom_signed_pdf_pushed`; `custom_address`). Phase A offer letters work today, so these fields presumably exist on live site (created via Customize Form, never round-tripped to fixtures) — but the same class of silent-failure could bite us. Separate audit + round-trip work to follow.

### Verification commands after deploy

1. Trigger a manual sync or wait 15 min for the scheduled run
2. Check sync log at `/app/greythr-sync-log` — expect `records_updated > 200`, `records_skipped` small
3. Re-run the diagnostic for HR-EMP-00869:
   ```
   /api/method/greythr_bridge.utils.sync_diagnostics.inspect_sync_for_employee?employee_name=HR-EMP-00869
   ```
   `frappe_record_now.first_name` should now be `"Gandla Sanjeev"`, `custom_greythr_employee_id` should be `"270"`, `status` should be `"Left"` (since leftorg=true + leavingDate parsed).
4. Re-run the audit:
   ```
   /api/method/greythr_bridge.utils.data_quality.list_ghost_employees
   ```
   `summary.ghosts` should drop dramatically (from 332 toward ~0).

### Zero deletions, zero renames

This commit continues the pattern: no Employee or Mapping records deleted, no primary keys changed, no manual data manipulation. The 332 records get enriched in place by the sync once the mapper and fields are correct. Memory rule `never_delete_employee_records.md` honoured.

---

## [Unreleased] — Cleanup pass after mapper rewrite (2026-05-23)

Mapper rewrite was verified working on live (332 records, 209 correctly flipped to Left, 122 of 123 Active enriched with names). This commit fixes three small issues found during verification:

### Fix 1: Audit endpoint NOT-IN-NULL bug

`list_ghost_employees()` was reporting `total_employees: 1` while the live site had 332. Root cause: the audit query used `filters={"first_name": ["not in", ["", None]]}` which SQL evaluates as `WHERE first_name NOT IN ('', NULL)` — always undefined (never true) because of how NOT IN handles NULL. Always returned zero rows.

Fix: rewrite both audit queries to use explicit `or_filters` / `is set`/`is not set` operators that translate to proper SQL `IS NULL`/`IS NOT NULL` handling:
- Ghosts: `or_filters=[["first_name", "is", "not set"], ["first_name", "=", ""]]`
- With-data: `filters=[["first_name", "is", "set"], ["first_name", "!=", ""]]`

Added regression test `test_audit_queries_use_or_filters_not_in_with_null` that asserts the query does NOT use the broken `not in` form.

### Fix 2: client.py token-cache optimistic-locking race

The OAuth token cache used `self.settings.save(ignore_permissions=True)` which triggered Frappe's optimistic locking. Any concurrent write to `greytHR Settings` (sync's `last_employee_sync` update, webhook handlers, another API call refreshing) caused `TimestampMismatchError` — observed in production on 2026-05-23 when running the diagnostic concurrent with a scheduled sync.

`pull_employees.py` had already worked around this for its own Settings write by using `frappe.db.set_value` (direct SQL UPDATE, no version check). The client was never updated to match.

Fix: new `_persist_token(token, expires_at)` helper in `api/client.py` that uses `frappe.db.set_value` to write `cached_token` + `token_expires_at` atomically. Both `_get_token` and `_clear_token_cache` now go through it. In-memory `self.settings` copy is also updated so the same request sees the fresh token without re-reading from DB.

Added regression test `test_token_cache_uses_db_set_value_not_settings_save` that pins the new behaviour.

### Fix 3: Date string vs Python date comparison

After the mapper rewrite, every sync run was triggering save() on every record even when nothing semantically changed. Root cause: Frappe stores Date/Datetime fields as Python `date`/`datetime` objects but the mapper produces ISO strings ("2024-01-02"). Naïve `frappe_employee.get("date_of_birth") != "1994-03-15"` returns True for `date(1994, 3, 15)` because of the type mismatch.

Cost: unnecessary `frappe_employee.save()` call per record per sync (every 15 min). Not data-incorrect, just wasteful.

Fix: new `_values_differ(current, new)` helper in `tasks/pull_employees.py` that coerces both sides to comparable strings before comparing. The `_sync_one` update loop now uses `_values_differ` instead of `!=`.

Added 6 unit tests covering: same date object == ISO string returns False, both None returns False, one None returns True, different strings differ, same strings don't differ, different dates differ.

### Tests

- 167 passing (was 159), 3 skipped
- 8 new tests across `test_data_quality.py`, `test_pull_employees.py`, `test_client.py`

### Operational note for the 1 remaining ghost (HR-EMP-00683)

After deploy, please run:
```
/api/method/greythr_bridge.utils.sync_diagnostics.inspect_sync_for_employee?employee_name=HR-EMP-00683
```

This will tell us whether HR-EMP-00683 has a greytHR mapping (and if so, what greytHR returns for that ID). Three likely outcomes:
1. **No mapping** — record was manually created in Frappe, never seen by sync. Either HR pulls it into greytHR or accepts it as a Frappe-only record.
2. **Broken mapping** (greythr_employee_id is empty or wrong) — bulk-import placeholder, won't ever match a greytHR response. Mapping needs HR cleanup.
3. **Valid mapping but greytHR returns empty data for that ID** — greytHR data quality issue at source.

Either way, no code change needed — single-record diagnosis followed by either greytHR portal edit or accepting the lone ghost.

### Zero destructive operations

All three fixes are read-side or write-pattern changes — no data deleted, no schema changes, no record renames. Constraint from `memory/never_delete_employee_records.md` continues to be honoured.

---

## [Unreleased] — Mapper date-sanity guard for greytHR data quality issues (2026-05-23)

### The last remaining ghost (HR-EMP-00683) traced to greytHR bad data

After the mapper rewrite + 3-fix cleanup, 331 of 332 records were correctly enriched. The lone holdout (HR-EMP-00683 / GDS0022 / Nalluri suresh) wouldn't sync even though its mapping was fresh and the mapper produced rich output. Diagnostic via `inspect_sync_for_employee` revealed why:

greytHR returns this employee with:
- `dateOfJoin: "2017-11-12"`
- `leavingDate: "2017-08-10"` ← **3 months BEFORE the joining date**
- `leftorg: true`

Frappe HR's `Employee.validate` hook enforces `relieving_date >= date_of_joining`. When sync tried to save with `status="Left"` + `relieving_date="2017-08-10"` + `date_of_joining="2017-11-12"`, validation rejected the save. The outer try/except caught the error and incremented `records_failed` — but the record was the only one out of 332 affected, so the failure was easy to miss.

### Fix: defensive sanity check in the mapper

`mappers/employee_mapper.py` — new sanity check after status/leaving-date logic. If `relieving_date < date_of_joining`:
- Drop the impossible `relieving_date`
- Force `status` back to `Active` (Frappe HR allows that)
- Log to `_mapping_errors` with the employeeId and conflicting dates so HR can fix at the greytHR source

Net behaviour: the record gets enriched with everything ELSE (first_name, gender, date_of_joining, custom_greythr_employee_id, etc.) and stays Active. HR can manually mark Left after correcting the dates in greytHR portal.

### Why this fix is future-proof, not just one-record

Any future greytHR record with inverted dates (data entry mistakes happen) would hit the same Frappe validate hook. The sanity check catches the entire class — sync no longer breaks on bad data, just logs and continues. Sync log's `records_failed` count drops to 0 for this class of error.

### Tests

- 170 passing (was 167), 3 skipped
- 3 new tests in `test_mappers.py`:
  - `test_relieving_before_joining_drops_relieving_keeps_active` — exact HR-EMP-00683 reproduction
  - `test_relieving_equal_to_joining_is_allowed` — edge case (joined and left same day)
  - `test_relieving_after_joining_unaffected` — normal case preserved

### Net status after this commit

**Data integrity epic complete.** 332/332 records will be syncable on the next scheduled run:
- ~331 will continue enriching as before
- HR-EMP-00683 will get its name, gender, joining date populated (status stays Active until HR fixes dates in greytHR)
- All other future records with similar greytHR data quality issues will also sync gracefully

Phase 4 (UI fixes), Phase 5 (Data Quality dashboard), Phase 6 (missing employees investigation — now confirmed to be zero) can all resume.

### Operational note for HR

After the next sync (~15 min after deploy), HR-EMP-00683 should have `first_name="Nalluri suresh"` populated. The record will remain Active until either:
1. HR fixes the date order in greytHR (corrects either dateOfJoin or leavingDate so they're sequential), OR
2. HR manually changes status to Left in Frappe HR (knowing that triggers Frappe HR's exit workflows)

The `greytHR Sync Log` for that run will have an `error_summary` entry noting the conflict for HR's awareness.

### Zero deletions, zero schema changes

15-line mapper addition + 3 tests. Memory rule `never_delete_employee_records.md` continues to be honoured.

---

## [Unreleased] — Employee ID alignment with greytHR (2026-05-23)

### Goal

HR and greytHR portal show employee IDs as `GDS0380`. Frappe shows them as `HR-EMP-01009`. No visual correlation between the two systems. Two-commit fix to bring Frappe's primary key into alignment with greytHR's `employee_number`.

### Phase 1 — NEW records use greytHR `employee_number` as Frappe name (shipped: commit `2762016`)

From this commit forward, any new Employee created (via sync OR manual UI) with `employee_number` populated will use that value as the Frappe primary key, instead of the default `HR-EMP-####` auto-generated naming.

**Defense-in-depth: two code paths set `doc.name`:**

1. `tasks/pull_employees.py::_sync_one` — explicitly sets `doc.name = mapped["employee_number"]` BEFORE `doc.insert()` for sync-created records
2. `hooks_handlers.employee.set_name_from_greythr_id` — new `before_insert` hook on Employee (registered in `hooks.py`); covers manual UI creates + any other code path

Both check `doc.name` is not already set (idempotent) and fall through to Frappe HR's default naming series (`HR-EMP-####`) when `employee_number` is empty. This preserves HR's ability to add new hires manually before a greytHR ID is assigned.

**Existing 331 records still use `HR-EMP-####` after Phase 1.** Phase 2 (below) renames them in a separate triggered operation.

### Phase 2 — One-shot rename of existing records (shipped, NOT yet triggered)

New module `tasks/rename_employees_to_greythr_id.py` with two whitelisted endpoints:

- **`plan_rename()`** — read-only categorisation. Returns counts + full lists by category: `to_rename`, `already_correct`, `no_employee_number`, `invalid_pattern`, `collisions`. Safe to call anytime.
- **`run_rename(confirm="yes")`** — enqueues the background job. Requires explicit `confirm=yes` parameter. System Manager only.

**Mechanics (key safeguards):**

- **Per-record commit + rollback:** `frappe.rename_doc` is NOT internally transactional — it runs separate SQL UPDATEs for parent + every FK reference. We commit per-record on success and rollback per-record on failure. One bad record doesn't abort the batch.
- **Auto-disable greytHR sync during rename:** prevents race conditions with the every-15-min `pull_employees` task. Script flips `greytHR Settings.enabled = 0` at start and restores original value at end via `try/finally`. Self-recovering even on crash.
- **Skip-and-continue for bad data:** records with invalid `employee_number` (typo, lowercase, non-GDS format) are skipped, logged with reason, batch proceeds for valid records.
- **Full audit trail:** every `(old, new)` pair (and any failures) persisted in `greytHR Sync Log.details` as JSON. Enables reverse migration in disaster recovery.
- **Progress logging:** every 25 records, current counters are saved to the Sync Log — HR can monitor live in the browser.
- **Background job (`enqueue("long", timeout=1500)`)** — synchronous HTTP would time out for 300+ renames on Frappe Cloud.

### Pre-flight checklist (HR MUST do before triggering `run_rename`)

1. **Take a Frappe Cloud DB backup.** Manual snapshot via bench dashboard. Primary recovery path if anything goes sideways.
2. **Fix any remaining typo `employee_numbers` in greytHR portal.** Today's stragglers:
   - HR-EMP-01012 (Gopi Gali) — greytHR shows `gds0115` → should be `GDS0115` (uppercase)
   - HR-EMP-01010 (Yarabaka Mahitha) — greytHR shows `GSD0033` → should be `GDS0033` (typo)
   - Wait one 15-min sync cycle after fixing so corrected values reach Frappe
3. **Run during a payroll-quiet window** (no Payroll Entry generation in progress)
4. **Call `plan_rename()` first** — review the plan output, confirm counts make sense, no unexpected collisions

### How to use after deploy

```bash
# 1. Review the plan (read-only, safe anytime)
GET /api/method/greythr_bridge.tasks.rename_employees_to_greythr_id.plan_rename

# Expected output approx:
# {
#   "summary": {
#     "total_employees": 331,
#     "to_rename": 329,
#     "already_correct": 0,
#     "no_employee_number": 0,
#     "invalid_pattern": 2,   # gds0115, GSD0033 — fix in greytHR first
#     "collisions": 0
#   },
#   "to_rename": [{from: "HR-EMP-00001", to: "GDS0001"}, ...],
#   ...
# }

# 2. After pre-flight checklist complete, trigger the actual rename
POST /api/method/greythr_bridge.tasks.rename_employees_to_greythr_id.run_rename?confirm=yes

# Returns: {"status": "enqueued", "check_progress_at": "/app/greythr-sync-log"}

# 3. Monitor progress
# Open /app/greythr-sync-log — newest entry with sync_type="Rename Employees to greytHR ID"
# records_processed / records_renamed / records_failed update every 25 records

# 4. After completion, verify
GET /api/method/greythr_bridge.utils.data_quality.list_ghost_employees
# Expected: all records have GDS#### names (employees_with_data list shows
# names matching employee_number)
```

### Failure recovery

| Scenario | Recovery |
|---|---|
| Single rename fails | Logged in `error_summary`, others succeed. Re-run plan_rename + run_rename — it'll skip already-renamed and retry failed. |
| Multiple renames fail | Same as above — re-runnable, idempotent. |
| `_do_rename` crashes mid-batch | Sync auto-re-enabled via `try/finally`. Successful renames persist (per-record commit). Failed/un-attempted records logged. Re-run as needed. |
| Disaster (corruption beyond fix) | Frappe Cloud DB restore from pre-rename backup. |
| Need to undo all renames | Parse `details` JSON from Sync Log; loop `frappe.rename_doc(new, old)` for each pair (one-off script). |

### What does NOT change

- Existing payroll history (Salary Slips, Leave records, Attendance) — `rename_doc` updates the FK references, the historical data itself stays intact
- Historical PDFs already attached to records — they retain old IDs in their text content (immutable artifacts; new PDFs generated after rename use new IDs)
- External bookmarks / emails pointing at `/app/employee/HR-EMP-####` URLs — break after rename (no auto-redirect in Frappe). Probably zero exist in this environment.
- The 7 Phase B letters — they use `frappe.get_doc("Employee", name)` which works regardless of the name format

### Tests

- **187 passing** (was 170), 3 skipped
- 5 new tests for Phase 1 (`test_pull_employees.py`): sync-created uses GDS####, fallback to series, the `before_insert` hook behaviour
- 12 new tests for Phase 2 (`test_rename_employees.py`): role check, plan categorisation, collision detection, idempotency, per-record commit/rollback, sync auto-disable/re-enable, audit trail persistence
- Test fixture hygiene fix in `conftest.py`: also reset `new_doc` and `get_doc` `side_effect` between tests

### Memory rule refinement

Updated `memory/never_delete_employee_records.md` with today's learnings from the HR-EMP-01011 cleanup and the rename design:

- Hard rule clarified: no deletion CODE in sync/webhook/scheduled pipelines (manual UI deletion by HR is OK for confirmed orphans)
- Added the full linked-records impact-check guidance (the 8 doctypes to check, including the `frappe_employee` field-name gotcha for greytHR Employee Mapping)
- Documented that renames carry similar risk to deletions and follow the same safeguards (plan-first, confirm-required, per-record commit, sync auto-disable, audit trail, DB backup, System Manager only)

### Zero destructive operations in this commit

Phase 1 adds naming logic (zero data change). Phase 2 ships the rename tooling but is NOT auto-triggered — HR explicitly invokes after pre-flight. The rename itself is per-record-atomic with rollback. No deletions anywhere.

---

## [Unreleased] — Rename job Sync Log Select-value fixes (2026-05-24)

### Two `_validate_selects` rejections caught the rename job before any rename ran

First trigger of `run_rename?confirm=yes` enqueued `_do_rename` cleanly, but the job crashed inside `_start_rename_log` at `doc.insert()` on the very first DB write. Two stacked Select-validation errors, in sequence:

1. **`sync_type = "Rename Employees to greytHR ID"`** — not in the field's Options on the live `greytHR Sync Log` DocType (originally created via Form Builder in Phase 1, only ever had 6 values: `Pull Employees`, `Pull Salary`, `Push Employee`, `Push Signed PDF`, `Push Salary Revision`, `Update Employee Status`). Fixed on live by HR via the DocType UI (added the new option to the Select Options).
2. **`status = "In Progress"`** — the rename code was the only sync task using this value. `pull_employees` and `pull_salary_structures` both use `Started`. The DocType's `status` Select accepts only `Started`, `Success`, `Partial Success`, `Failed` — `In Progress` is not in the list. Fixed in code by aligning with the existing convention.

Both failures fired during `doc.insert()`'s validation phase, so **no Sync Log row was ever persisted, no Employee record was touched, sync was never disabled** — clean rollback on both attempts. Recoverable by simply re-triggering after the fix.

### Fixes shipped

- ✅ **`greythr_bridge/tasks/rename_employees_to_greythr_id.py:312`** — `doc.status = "Started"` (was `"In Progress"`) in `_start_rename_log`. Plus a 3-line comment documenting the Select enum so the next reader doesn't reintroduce the bug.
- ✅ **`greythr_bridge/tests/test_rename_employees.py`** — new regression test `test_start_rename_log_uses_valid_status_enum` that pins `status == "Started"` and asserts the value is in the valid set `{Started, Success, Partial Success, Failed}`. Would have caught this offline if it had existed.
- ✅ **Live DocType fix (out of band, UI-only):** appended `Rename Employees to greytHR ID` to the `sync_type` field's Options on `greytHR Sync Log`. Not in source — the entire DocType is missing from `greythr_bridge/doctype/` (was created via Form Builder, never exported via `bench export-fixtures`). The `hooks.py` fixtures filter for `module = greytHR` would auto-include it if exported.

### Tests

- **188 passing** (was 187), 3 skipped
- 1 new test in `test_rename_employees.py` covering both the strict Select enum check and the convention-match assertion

### Hygiene gap to address separately

The `greytHR Sync Log`, `greytHR Settings`, and `greytHR Employee Mapping` DocTypes all live only on the live site — they're not in our source repo. Any field-level edit made via Form Builder (like today's `sync_type` Options append) is currently un-replayable from git. A separate task should:

1. SSH into the bench, run `bench --site gdshr.m.frappe.cloud export-fixtures --app greythr_bridge`
2. Commit the resulting `greythr_bridge/doctype/greythr_sync_log/greythr_sync_log.json` (and siblings) to git
3. Future field changes happen via JSON edit + migrate, not via Form Builder

Not blocking the rename; safe to defer.

### Zero data touched

This commit is pure tooling correctness. The two failed attempts left zero side effects (insert validation rolled back). After deploy, re-triggering `run_rename?confirm=yes` should succeed end-to-end.
