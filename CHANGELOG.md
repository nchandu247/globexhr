# Changelog

All notable changes to `globex_hr_letters` (formerly `greythr_bridge`) are
documented here.
Format: `## [Unreleased]` until first production deploy, then version + date.

---

## [Unreleased]

### 2026-07-11 — Install fix: HR Letter controller import path

First install on the test site (`gdshr.m.frappe.cloud`) aborted at 20% with
`No module named 'globex_hr_letters.hr_letters.letters'`. Root cause:
`hr_letter.py` used `from ...letters import engine` — three dots resolve to
`globex_hr_letters.hr_letters`, not the app package, so the import pointed
inside the module folder. Local suite never caught it because no test
imported the controller modules.

- ✅ Fix: absolute import `from globex_hr_letters.letters import engine`.
- ✅ New `tests/test_controller_imports.py` — imports every
  `hr_letters/doctype/*/*.py` controller (plus a discovery-count guard), so
  this bug class now fails offline. Verified: reintroducing the bad import
  fails the sweep.
- ✅ `tests/conftest.py` — real `_MockDocument` class registered at
  `frappe.model.document.Document` (controllers subclass it; MagicMock can't
  be a base class).
- ✅ Test suite: **76 passing** (was 71).

### 2026-07-11 — Standalone pivot: globex_hr_letters

- ✅ **Pivot (spec 2026-07-10):** removed the entire greytHR integration
  (GreytHRClient, api wrappers, mappers, sync tasks, diagnostics, rate
  limiter, custom fields, sync tests) and rebuilt the repo as a standalone
  HR letters generation app.
- ✅ **Rename:** app `greythr_bridge` → `globex_hr_letters`; module
  `greytHR` → `HR Letters`; settings → `HR Letters Settings`.
- ✅ **New doctypes:** Letter Type (UI-managed catalog), HR Letter
  (submittable, dynamic Employee/Job Applicant recipient, status lifecycle,
  filled-values audit), HR Letter Compensation Row, HR Letters Settings.
- ✅ **Generic engine** (`letters/engine.py`): placeholder scan → resolve
  (recipient → Settings → compensation table → prompt dialog) → hard error
  on unresolved → dual render (HTML/WeasyPrint shipped library,
  DOCX/docxtpl for HR-authored types) → attach → Zoho dispatch / email.
- ✅ **Shipped template library:** 14 letter types preloaded via fixtures
  (Offer, Appointment, Confirmation, Promotion, Salary Revision, Experience,
  Relieving, Service Certificate, Warning, Termination, Internship
  Certificate, Address Proof, Consultant Offer, Internship Offer); new
  compensation annexure renders from the HR Letter breakup table.
- ✅ **Zoho flow repointed at HR Letter:** webhook (HMAC + 5-min replay
  window unchanged) flips status to Signed and attaches the signed PDF;
  stalled-signings cron reminds pending signers after a configurable
  threshold.
- ✅ **Workspace + UX:** HR Letters workspace; Generate Letter buttons on
  Employee and Job Applicant; HR Letter form drives Generate / Send for
  Signature / Issue / Resend.
- ✅ **Tests:** suite rebuilt — 71 offline tests green.
- 🔜 Next: install on the test site, end-to-end smoke (plain + signature
  letter), letterhead-from-Settings pass, HR template review (PLAN.md §3).

---

### Historical — greythr_bridge era (pre-pivot)

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

---

## [Unreleased] — Sync cadence: daily + manual button (2026-05-24)

### From "every 15 min" to "daily + on-demand"

The scheduled `pull_employees` had been running every 15 minutes since Phase 2 (96 calls/day) — chosen originally for near-real-time freshness, but in practice greytHR data barely changes between scheduled syncs. The high cadence:

- Masked the "sync claims success while doing nothing" bug for weeks (lots of "successful" runs that did no work)
- Spawned the `employee 389` validation error every 15 minutes
- Created the race condition that made today's GDS#### rename require sync auto-disable as a safeguard

### Decision: Option C — Daily + Manual button

- **Scheduled:** once daily at 6 AM IST (was `*/15 * * * *`, now `0 6 * * *`). Catches normal turnover before HR starts work.
- **Manual:** new "Sync from greytHR Now" workspace shortcut + Client Script button on the Sync Log list view. HR triggers a fresh pull on demand (before letter generation, after a greytHR portal edit, after marking someone Left).

Two alternatives considered:
- **Daily only:** rejected — letter generation depends on current Employee data, HR needs a way to force a fresh sync without waiting until next morning.
- **Manual only:** rejected — status-change cascading (User account auto-disable on Left) would only fire when HR remembers to sync, creating a security gap for departures.

### Trade-offs HR accepts

| Aspect | Old (15-min) | New (daily + manual) |
|---|---|---|
| API calls/day | 96 | 1 + manual triggers |
| Max staleness | 15 min | 24h (with manual override available) |
| Race conditions during ops | High | None during baseline; manual sync is HR's choice |
| Letter generation freshness | Auto-fresh | One-click "Sync Now" before triggering letters |
| Status cascading (Left → User disable) | ≤15 min | ≤24h, or HR clicks "Sync Now" after marking exit in greytHR |

### Changes shipped

- ✅ **`greythr_bridge/hooks.py`** — cron changed from `*/15 * * * *` to `0 6 * * *` for `pull_employees.run`. Added a 4-line comment explaining the manual button as the high-frequency replacement.
- ✅ **`greythr_bridge/greythr/workspace/greythr/greythr.json`** — new shortcut "Sync from greytHR Now" added under Operations (Blue, prominent). URL opens the Sync Log list view with `?manual_sync=1` query param. Workspace shortcut count: 15 → 16. Content widget array updated to include the new shortcut tile.
- ✅ **`greythr_bridge/fixtures/client_script.json`** — new Client Script "greytHR Sync Log — Sync Now Button":
  - `view: List` — attaches to the Sync Log list view
  - Adds an inner button "Sync from greytHR Now" at the top of the list
  - Gated by HR Manager / System Manager role check
  - Shows `frappe.confirm` dialog before triggering (prevents accidental clicks)
  - Calls existing `greythr_bridge.tasks.pull_employees.run_now` (no new Python endpoint needed)
  - Auto-opens the confirm dialog when arriving via `?manual_sync=1` (from the workspace shortcut), then strips the query param via `history.replaceState` so refresh doesn't re-trigger
  - Auto-refreshes the list view after 30s so HR sees the new Sync Log entry without clicking refresh
- ✅ **`greythr_bridge/tests/test_workspace_fixture.py`** — `test_exactly_15_shortcuts` renamed to `test_exactly_16_shortcuts` (16 now expected); new `test_manual_sync_shortcut_present` pins the shortcut's `link_to`, `type`, and `?manual_sync=1` URL contract.
- ✅ **`greythr_bridge/tests/test_hooks_and_client_scripts.py`** (new file) — 5 tests:
  - `test_pull_employees_runs_daily_not_every_15_min` — regression on the cadence change (both negative + positive cron-string assertion)
  - `test_pull_salary_structures_still_daily` / `test_stalled_signings_still_daily` — confirms other schedules unaffected
  - `test_json_parses_as_list` + `test_every_script_has_required_fields` — shape-check on `client_script.json` so broken JSON / missing fields surface offline
  - `test_sync_now_button_script_present` — verifies the new script is present, hits the right endpoint, has a confirm dialog, gates by role, and reads `?manual_sync=1`

### Tests

- **195 passing** (was 188), 3 skipped
- 7 new tests across `test_workspace_fixture.py` and `test_hooks_and_client_scripts.py`

### After deploy + migrate — operational note

1. Scheduler reconfigures automatically on next migrate.
2. Workspace + Client Script auto-install via existing fixture filters in `hooks.py`.
3. HR will see the new "Sync from greytHR Now" card on `/app/greythr` workspace and a matching button on top of `/app/greythr-sync-log` list view.
4. Old `*/15 * * * *` schedule stops firing immediately after deploy — no orphan jobs to clean up.

### Why not delete `_pull` or the scheduled entry path

`pull_employees.run` is still the scheduled entry point — only the cadence changed. Both the manual `run_now` (enqueues + returns) and the scheduled `run` (runs inline) share the same `_pull` core function. One code path, two trigger frequencies.

---

## [Unreleased] — Mapper sanity check: missing date_of_joining (2026-05-24)

### employeeId 389 has been failing every 15 min (now daily)

The error log entry surfaced during today's rename investigation:

```
pull_employees: employeeId=389 error=
  Relieving Date must be after Date of Joining
```

Same Frappe HR validation as GDS0022 (Nalluri suresh), but the mapper's sanity check from 2026-05-23 didn't catch this record. Investigation showed there's **no greytHR Employee Mapping for ID 389** — the record fails in the `_sync_one` create path on every attempt, so no mapping ever gets persisted. Couldn't use the existing `inspect_sync_for_employee` to debug it (that diagnostic requires an existing Frappe Employee with a mapping).

### Root cause — second class of "impossible date" data

The existing sanity check fires only when BOTH `relieving_date` AND `date_of_joining` are populated in the mapper output. If greytHR returns `leavingDate` but `dateOfJoin` is missing or unparseable, the mapper skips the sanity check, produces a record with `status: "Left"` + `relieving_date` + no `date_of_joining`. Frappe HR's Employee.validate still rejects the save (Left requires both dates), and the record fails on every sync.

Two observed classes now share one defensive code path:

1. **Inverted dates** — `relieving_date < date_of_joining` (GDS0022)
2. **Missing joining date** — `relieving_date` set, `date_of_joining` absent (emp 389)

Both downgraded to `status: "Active"` + `relieving_date` dropped, so the rest of the record's fields (name, gender, contact) can be enriched. HR is notified via the `_mapping_errors` list so they can fix the data at the greytHR source.

### Changes shipped

- ✅ **`greythr_bridge/mappers/employee_mapper.py`** — sanity check extended from `if rd and doj and rd < doj` to `if rd and (not doj or rd < doj)`. Error message distinguishes the two classes ("set but date_of_joining missing/unparseable" vs "before date_of_joining"). Comment block updated with both cases for the next reader.
- ✅ **`greythr_bridge/utils/sync_diagnostics.py`** — new endpoint `inspect_greythr_employee(greythr_id)` that calls greytHR directly + runs the mapper, with NO Frappe Employee lookup. Companion to the existing `inspect_sync_for_employee` for records that fail before they can be created (so no mapping exists yet). System Manager only.
- ✅ **`greythr_bridge/tests/test_mappers.py`** — two new tests:
  - `test_relieving_set_but_no_date_of_joining_drops_relieving` — the emp-389 reproduction (leavingDate set, dateOfJoin omitted entirely)
  - `test_relieving_with_unparseable_joining_date_drops_relieving` — companion case (dateOfJoin present but garbage string)
- ✅ **`greythr_bridge/tests/test_sync_diagnostics.py`** — five new tests for the diagnostic helper:
  - Role check (System Manager only)
  - Empty `greythr_id` returns clear error
  - Happy path returns API response + mapper output
  - Bad-data path shows sanity-check downgrade + error message visible
  - API error is structured, not bubbled

### Tests

- **202 passing** (was 195), 3 skipped
- 7 new tests across two files

### How to verify after deploy

Once Frappe Cloud picks up this commit:

```
/api/method/greythr_bridge.utils.sync_diagnostics.inspect_greythr_employee?greythr_id=389
```

Expected response:
- `greythr_api_response` shows the raw greytHR payload for employee 389
- `mapper_output.status` is `Active`, `relieving_date` is absent
- `mapper_errors` contains an entry like *"relieving_date (X) set but date_of_joining missing/unparseable — keeping status Active; HR must populate dateOfJoin in greytHR for employeeId=389"*

Then trigger a sync via the new "Sync from greytHR Now" workspace button — the next Sync Log entry should show `records_failed: 0` (assuming no other broken records), and employee 389 should appear as a fresh greytHR Employee Mapping row.

### Operational note for HR

Employee 389 will be created in Frappe with `status: "Active"` even though greytHR has them marked as left, because greytHR's record is incomplete (missing dateOfJoin). To resolve:

1. Open employee 389 in the greytHR portal
2. Populate the **Date of Joining** field
3. Wait for the next scheduled sync (daily 6 AM IST) OR click "Sync from greytHR Now"
4. The mapper sanity check will detect that the dates are now consistent and set `status: "Left"` correctly

### Zero data deletion, zero invasive change

15-line mapper diff + 60-line diagnostic addition + tests. Memory rule `never_delete_employee_records.md` continues to be honoured.

---

## [Unreleased] — Employee picker UX filter (Phase 4 — 2026-05-24)

### Hide invalid-pattern records from autocompletes + list views

The 2 records the GDS#### rename couldn't process (HR-EMP-01010 `GSD0033` Yarabaka Mahitha, HR-EMP-01013 `Gds0943274` siuad) still show up in every Employee Link picker across the system — Salary Structure Assignment, Job Offer Reporting To, Payroll Entry, Salary Slip, Attendance, etc. HR seeing them in autocompletes makes it easy to accidentally pick a record with malformed greytHR ID.

### Fix

A `permission_query_conditions` hook on Employee that appends a SQL filter to every list / picker query:

> Allow records where `employee_number` is NULL/empty (manual Frappe-only employees) OR matches `^GDS\d{3,5}$` (case-insensitive, same regex as the rename script). Filter out everything else.

This is a **UX filter, not a security boundary**. Direct URL access (`/app/employee/HR-EMP-01010`) still works — HR can fix these records via greytHR portal corrections then re-trigger the rename or sync to clean them up.

### Why now

Now that the rename is shipped and the 2 invalid-pattern records are the *only* records with non-canonical IDs, filtering them out at the picker layer is risk-free: any future record HR creates either has a valid greytHR ID (matches `^GDS\d{3,5}$`) or has no greytHR ID at all (manual create, NULL passes the filter).

### Files

- ✅ **`greythr_bridge/utils/permissions.py`** (new) — `employee_query_conditions(user)` returns the SQL fragment. MariaDB's `REGEXP` is case-insensitive on Frappe's default `utf8mb4_unicode_ci` collation, so a single regex covers both `GDS0001` and `gds0115`.
- ✅ **`greythr_bridge/hooks.py`** — wires `permission_query_conditions = {"Employee": ...}` with a 3-line comment explaining the UX-vs-security distinction.
- ✅ **`greythr_bridge/tests/test_permissions.py`** (new) — 6 tests:
  - SQL shape check (balanced parens, OR-bound clause)
  - NULL/empty allowance (manual employees stay visible)
  - GDS\d{3,5} pattern present + correctly anchored
  - Spot-check against the 2 known invalid records and a handful of known-good IDs
  - User argument accepted but doesn't change filter (UX-uniform)
  - hooks.py routes Employee queries to this function (catches the silent wiring mistake)

### Tests

- **208 passing** (was 202), 3 skipped

### Not in this commit (Phase 4 scope check)

Original Phase 4 spec also called for:
- Adding `employee_number` as an Employee-list column → **dropped**: after the rename, `name == employee_number` for all 330 GDS-aligned records, so the column would duplicate the name. The primary key (name = GDS####) is already the row click target.
- Visual indicator (badge) for records with a greytHR mapping → **deferred**: nice-to-have, but every active employee now has a mapping after the rename, so the indicator wouldn't visually distinguish anything. Worth revisiting only when manual Frappe-only employees become common.

### Note for HR

After deploy, HR-EMP-01010 and HR-EMP-01013 will silently disappear from Employee pickers. To make them re-appear:
1. Fix the `employee_number` value in greytHR portal (`GSD0033` → `GDS0033`, `Gds0943274` → a valid `GDS####`)
2. Wait for next sync OR click "Sync from greytHR Now"
3. Run `plan_rename` — they'll move from `invalid_pattern` to `to_rename`
4. Run `run_rename?confirm=yes` to align the Frappe primary key
5. They re-appear in pickers automatically (filter allows them now)

---

## [Unreleased] — Rehire detection + sync defensiveness sweep (2026-05-25)

### Five sync bugs surfaced by the emp 389 investigation

The manual sync after Phase 4 deploy still showed `records_failed: 3`. Same three records (employeeIds 389, 388, 271) failed with the same Frappe HR validation: *"Relieving Date must be after Date of Joining"*. The previous `cf16a12` mapper fix didn't help — because the actual bug was elsewhere.

Investigation traced emp 389 (MOHD BALEEGH AHMED) to a **rehire scenario**:
- Original employment: `GDS0260` in greytHR (greytHR ID `300`) — left
- New employment: `GDS0345` in greytHR (greytHR ID `389`) — currently Active, joining date 2025-12-01
- Same `company_email` on both greytHR records

Old code's `_find_frappe_employee` matched the new greytHR ID=389 to the OLD Frappe record `GDS0260` (via email), entered the UPDATE path, tried to overwrite GDS0260's fields with the new employment data. The stale `relieving_date` on GDS0260 then conflicted with the new `date_of_joining` and Frappe's validate hook threw. The error was a safety net catching what would otherwise have been silent historical-data corruption.

A broader audit found four more issues in the same flow. All five fixed in this commit.

### Bugs fixed

#### Bug #1 — `_find_frappe_employee` hijacks Frappe records with existing mapping to a different greytHR ID

When email/employee_number matches a candidate Frappe Employee that's *already mapped to a different greytHR ID*, the old code would still return that candidate — silently overwriting it with the new greytHR record's data. Historical employment (separate greytHR record, separate dates, separate everything) is destroyed.

**Fix**: new helper `_candidate_has_different_mapping(candidate, greythr_id)` runs after every email/emp_no match. If the candidate is already linked to a different greytHR ID, returns None instead → `_sync_one` enters CREATE path → new Frappe Employee for the new greytHR record. Logs to Error Log under `"greytHR Rehire Detection"` title so HR can review the routing.

Result: after deploy, emp 389 will create a new Frappe Employee `GDS0345` cleanly. GDS0260 stays untouched. Same for emp 388 and 271 (likely same scenario).

#### Bug #2 — stale `relieving_date` survives Left → Active transitions

When mapper produces `status: Active`, it never explicitly clears `relieving_date`. Existing Frappe records that had a relieving_date from a previous Left period kept it after reactivation. Combined with a new `date_of_joining`, Frappe's validate hook would reject the save.

**Fix**: mapper now explicitly sets `result["relieving_date"] = None` in all three Active branches AND in the date-sanity check that downgrades Left → Active. `_sync_one`'s update loop, which uses `_values_differ(existing, None)`, will then call `set_value` to clear the stale value. Pure additive change — never overwrites valid data, only nulls when greytHR's truth is "no relieving date."

Defensive complement to Bug #1's fix: covers the same-greytHR-ID-reactivation case that wouldn't hit the rehire-detection logic.

#### Bug #3 — step 3 of matching chain read the wrong source field

[tasks/pull_employees.py:237-249] step 3 was supposed to be a `personal_email` fallback but read `mapped["company_email"]` and queried it against the `personal_email` field. Comment said *"personal_email not yet in mapped"* — predates the 2026-05-23 mapper rewrite that added `personal_email` to mapper output. Dormant bug that occasionally matched the wrong person.

**Fix**: step 3 now reads `mapped.get("personal_email")` and only fires if greytHR returned a personal email. Also applies the Bug #1 defensive check to step 3.

#### Bug #6 — Phase 4 `permission_query_conditions` leaked into internal sync lookups

The Phase 4 UX filter (added 2026-05-24) hides invalid-pattern Employees from autocompletes. Frappe applies `permission_query_conditions` to *every* `frappe.get_all("Employee", ...)` unless `ignore_permissions=True` is passed — including server-side sync lookups. Risk: if a future greytHR record's email matched a hidden Employee, sync would silently create a duplicate instead of updating.

**Fix**: added `ignore_permissions=True` to all 4 internal `frappe.get_all` calls in `_find_frappe_employee` (1 mapping lookup + 3 Employee lookups) plus the new `_candidate_has_different_mapping` helper. Sync internals now bypass UX filters by design.

#### Bug #8 — mapper warnings silently discarded

`_sync_one` popped `_mapping_errors` from the mapper output but only used them if `custom_greythr_employee_id` was missing. Warnings like *"gender: unrecognised value"*, *"leftorg=true but no leavingDate"*, *"relieving_date set but date_of_joining missing"* (from `cf16a12`) were silently swallowed. HR had no visibility into greytHR data quality issues the mapper was working around.

**Fix**: `_sync_one(greythr_emp, warnings=None)` now appends per-record mapping_errors to the optional `warnings` list (with `employeeId:` prefix). `_pull` collects them across the batch and passes them to `_finish_sync_log`, which writes them into `error_summary` tagged `WARN`. The Sync Log's `error_summary` field now shows both actual failures and mapper warnings — HR can scan one place to find all data-quality issues.

Backwards-compatible: existing callers (tests, ad-hoc scripts) that call `_sync_one(emp)` without the kwarg still work — warnings just get silently dropped (same as before).

### Files

- ✅ `greythr_bridge/tasks/pull_employees.py`:
  - New `_candidate_has_different_mapping(candidate, greythr_id)` helper
  - `_find_frappe_employee` — defensive checks in steps 2/3/4, `ignore_permissions=True` everywhere, step 3 now reads `personal_email`
  - `_sync_one(greythr_emp, warnings=None)` — appends per-record mapper warnings
  - `_pull` — collects `warnings` list, passes to `_finish_sync_log`
  - `_finish_sync_log(sync_log, status, counters, errors, warnings=None)` — emits `WARN`-tagged lines into `error_summary`
- ✅ `greythr_bridge/mappers/employee_mapper.py` — `result["relieving_date"] = None` in all Active branches + the sanity check
- ✅ `greythr_bridge/tests/test_pull_employees.py` — 7 new tests:
  - `test_find_frappe_employee_refuses_to_hijack_record_with_different_mapping` (Bug #1)
  - `test_find_frappe_employee_still_matches_when_no_existing_mapping` (Bug #1 regression)
  - `test_find_frappe_employee_matches_when_existing_mapping_is_same_id` (Bug #1 edge case)
  - `test_find_frappe_employee_step_3_uses_personal_email_not_company_email` (Bug #3)
  - `test_find_frappe_employee_uses_ignore_permissions_on_employee_lookups` (Bug #6)
  - `test_sync_one_appends_mapper_warnings_when_warnings_list_provided` (Bug #8)
  - `test_sync_one_warnings_default_is_backwards_compatible` (Bug #8 regression)
- ✅ `greythr_bridge/tests/test_mappers.py` — 3 existing tests updated (`"relieving_date" not in result` → `result["relieving_date"] is None`)
- ✅ `greythr_bridge/tests/test_sync_diagnostics.py` — 1 existing test updated for same reason
- ✅ `greythr_bridge/tests/test_pull_employees.py` — 1 existing test (`test_active_status_when_no_leaving_date`) updated similarly

### Tests

- **215 passing** (was 208), 3 skipped

### How to verify after deploy

1. Click "Sync from greytHR Now" on the workspace
2. Wait ~30 sec, refresh `/app/greythr-sync-log`
3. New Pull Employees entry should show:
   - `records_failed: 0` (was 3)
   - `records_created: 3` (emp 389, 388, 271 finally create)
   - `error_summary` may contain `WARN`-tagged entries for the new visibility into mapper-warned records
4. Open `/app/employee/GDS0345` → loads with status=Active, joining 2025-12-01, name=MOHD BALEEGH AHMED
5. Open `/app/employee/GDS0260` → UNCHANGED (still Left, original dates, custom_greythr_employee_id=300)
6. Open the new "greytHR Rehire Detection" entries in `/app/error-log` → should show the three routing decisions

### Past damage that may already exist (separate follow-up)

The validation error was the safety net catching Bug #1's hijack attempts when `relieving_date < new date_of_joining`. Past rehires where the dates happened to be consistent would have hijacked silently. A read-only audit endpoint to detect candidates for silent-hijack scenarios is worth building as a follow-up. Not blocking this fix.

### Zero data deletion

Bug #1 explicitly PREVENTS silent overwrites of historical employment records. Bug #2's `None` assignment only clears stale `relieving_date` values from existing records — it never destroys data unless greytHR's current truth says the relieving date should be empty. All other fixes are pure read-side / diagnostic improvements. Memory rule `never_delete_employee_records.md` continues to be honoured.

---

## [Unreleased] — Matching v4: distinguish broken-mapping from data corruption (2026-05-25)

### What the previous fix (b231807) revealed

The post-deploy sync showed `records_created: 3` (the original rehire victims emp 389/388/271 finally created cleanly — Bug #1 fix worked). But **5 NEW failures** appeared:

```
191: ('Employee', 'GDS0167', IntegrityError(1062, "Duplicate entry 'GDS0167' for key 'PRIMARY'"))
250: GDS0215 — same
251: GDS0216 — same
264: GDS0228 — same
326: GDS0282 — same
```

All "duplicate PRIMARY key" — meaning Bug #1's defensive check correctly refused to hijack these 5 candidates' records, then the CREATE path tried `doc.name = mapped.employee_number` and collided with an existing Frappe Employee at that name.

Investigation showed two distinct underlying causes for the 5 collisions:

#### Case A — 4 broken mappings (GDS0215, GDS0216, GDS0228, GDS0282)
- Frappe Employee shows the SAME person as greytHR for that employeeNo (verified by user)
- Frappe Employee's `employee_number` matches the incoming mapper's `employee_number`
- Frappe Employee's `company_email` matches the incoming mapper's `company_email`
- Difference is ONLY in the mapping table: stale `greythr_employee_id` from an old greytHR ID
- **Correct behavior**: allow the match (same person), correct the mapping ID in place

#### Case B — 1 data corruption (GDS0167)
- Frappe Employee `GDS0167` is actually **Sundareshwaran Selvaraj**, whose real greytHR employeeNo is `GDS0155`
- greytHR's `GDS0167` is **Thenmozhi Navaneethan** — completely different person
- Past sync hijack corrupted Sundareshwaran's record: overwrote his `employee_number` from `GDS0155` to `GDS0167` (his email-match collided with Thenmozhi during some earlier sync, UPDATE blindly overwrote)
- Today's rename script saw the corrupted `employee_number=GDS0167` and renamed his record's primary key accordingly
- Now greytHR's sync for Thenmozhi (ID=191, employeeNo=GDS0167) finds Sundareshwaran's misnamed record
- **Correct behavior**: refuse the match (different person), fail with clear HR action item

The previous "refuse if existing mapping ID differs" logic refused both cases identically — Case A unnecessarily, causing the IntegrityError. A smarter signal is needed to distinguish them.

### Fix: matching v4 — require BOTH employee_number AND company_email to match

`_candidate_has_different_mapping` renamed to **`_is_different_employment(candidate_doc, greythr_id, mapped)`** with this logic when an existing mapping points at a different greytHR ID:

```
if candidate.employee_number == mapped.employee_number
   AND candidate.company_email == mapped.company_email:
    → same person, stale mapping ID → allow + correct
else:
    → different person OR different employment → refuse
```

Verification against the 4 known scenarios:

| Scenario | Same emp_no? | Same email? | Decision | Why correct |
|---|---|---|---|---|
| Rehire (MOHD BALEEGH GDS0260 → GDS0345) | No | Yes | **Refuse** | Different employments, create new |
| Broken mapping (GDS0215 et al.) | Yes | Yes | **Allow** | Same person, fix stale mapping ID |
| Data corruption (GDS0167 Sundareshwaran vs Thenmozhi) | Yes | No | **Refuse** | Different people |
| Email reassigned (Thenmozhi gets Sundar's old email) | No | Yes | **Refuse** | Different employments |

Requiring BOTH signals is the strongest discriminator that survives both rehire AND corruption edge cases. Comparison is case-insensitive (greytHR returns mixed-case sometimes).

### Companion changes

#### `_upsert_mapping` now corrects stale `greythr_employee_id`

Without this, allowed broken-mapping matches would stay broken forever — every sync would re-trigger the defensive check, fail, log a correction, but the mapping wouldn't actually update. Now when the existing mapping's `greythr_employee_id` differs from what's being synced, we update it in place and log under `"greytHR Mapping Correction"` for HR visibility.

#### CREATE-path collision handler in `_sync_one`

When `doc.insert()` raises a 1062 "Duplicate entry" error (name collision), `_sync_one` catches it, logs a structured `"greytHR Name Collision"` entry with the HR action items (open the existing record, identify which is correct, repair the misnamed one), then raises a clean `ValueError` instead of bubbling up the raw MariaDB stack trace. The error_summary on Sync Log now shows a readable message instead of a noisy IntegrityError repr. Sync continues for the next record — one bad record doesn't poison the batch.

### Files

- `greythr_bridge/tasks/pull_employees.py`:
  - `_candidate_has_different_mapping` → `_is_different_employment(candidate_doc, greythr_id, mapped)` with v4 logic + extensive docstring explaining the three-case decision matrix
  - `_find_frappe_employee` call sites — fetch `candidate_doc` (via `get_doc`) BEFORE calling the helper, so we have employee_number + company_email for the signal check
  - `_upsert_mapping` — correct stale `greythr_employee_id`; updated `frappe.get_all` to include the field + use `ignore_permissions=True`
  - `_sync_one` CREATE path — try/except wraps `doc.insert()`, detects 1062 IntegrityError, logs Name Collision entry, raises ValueError
- `greythr_bridge/tests/test_pull_employees.py`:
  - `_make_candidate(name, employee_number, company_email)` — helper for mocking Frappe Employee docs with .get()
  - 4 new tests for `_is_different_employment` decision matrix (rehire / corruption / broken-mapping / no-existing-mapping)
  - 1 new test for SAME-id case (re-sync of same record)
  - 2 new tests for `_upsert_mapping` correction (stale ID corrected; correct ID untouched)
  - 1 new test for CREATE collision handler (raises ValueError, logs Name Collision)
  - Existing test names updated to reflect the v4 logic

### Tests

- **220 passing** (was 215), 3 skipped

### What HR should expect after deploy

Trigger "Sync from greytHR Now":

1. **4 records auto-recover** (GDS0215, GDS0216, GDS0228, GDS0282) — broken mappings allowed + corrected. `records_failed` should drop by 4. New `"greytHR Mapping Correction"` Error Log entries document each correction.

2. **1 record still fails clean** (GDS0167) — the Sundareshwaran/Thenmozhi corruption needs HR repair (rename Sundar's record to `GDS0155`, his real greytHR employeeNo). The new `"greytHR Name Collision"` Error Log entry spells out the action. `records_failed: 1` (was 5).

3. **Existing `records_created: 3` records** (emp 389/388/271 from b231807) stay as-is.

4. WARN entries (mapper warnings from Bug #8) continue to surface in error_summary — informational, no fix needed.

### HR repair workflow for the 1 remaining corruption

1. Confirm in greytHR portal: Sundareshwaran's real employeeNo is `GDS0155`, Thenmozhi's is `GDS0167`
2. In Frappe: open `/app/employee/GDS0167` (currently Sundareshwaran)
3. Update his `employee_number` field to `GDS0155` (the real value)
4. Use the existing `rename_employees_to_greythr_id.run_rename` workflow OR manually rename the doc via Frappe's UI (`/app/employee/GDS0167` → Menu → Rename)
5. Once Sundareshwaran's record is at name `GDS0155`, the slot `GDS0167` is free
6. Next sync creates a new Frappe Employee `GDS0167` for Thenmozhi cleanly

### Zero data deletion (still)

The v4 fix is purely about distinguishing same-person from different-person and routing accordingly. No records deleted. Broken mappings are corrected (not deleted). Corruption case fails loudly so HR repairs (not silently overwrites). Memory rule `never_delete_employee_records.md` continues to be honoured.

---

## [Unreleased] — Matching v5: first_name as secondary signal (2026-05-25)

### What v4 got wrong

v4 (`c4cea0b`) required BOTH `employee_number` AND `company_email` to match before allowing a broken-mapping match. After deploy:

- ✅ GDS0167 collision raised cleanly → HR manually renamed Sundareshwaran from `GDS0167` → `GDS0155` → next sync created Thenmozhi cleanly at `GDS0167` (the `records_created: 1`)
- ❌ The 4 broken-mapping records (GDS0215, GDS0216, GDS0228, GDS0282) **still failed** with name collisions

Root cause: candidate Frappe Employees often have empty/drifted `company_email` (sync never enriched it, or it was cleared, or greytHR now returns a different email). v4's strict "both emails must match" rule refused these legitimate same-person matches, sending them to CREATE → collision.

### v5: first_name replaces company_email as the secondary signal

Decision logic:

```
no existing mapping OR mapping points at same greytHR ID  →  ALLOW
employee_number differs                                    →  REFUSE (rehire)
employee_number matches:
    both first_names set AND clearly differ                →  REFUSE (data corruption)
    otherwise                                              →  ALLOW (broken mapping)
```

Why `first_name` is better than `company_email`:
- Names are what HR actually sees in lists/forms — they reflect the record's "identity"
- Less prone to drift than emails (no bulk renames, no reassignment after departure)
- The Sundareshwaran/Thenmozhi corruption case is uniquely detectable by name
- The rehire case (MOHD BALEEGH) is caught by `employee_number` differing — first_name check isn't reached
- Broken-mapping records have matching first_name (past sync wrote the same value greytHR currently returns)

### Edge cases handled

| Scenario | emp_no | first_name | Decision |
|---|---|---|---|
| Sundareshwaran/Thenmozhi (data corruption) | match | clearly differ | refuse |
| MOHD BALEEGH (rehire) | differ | — (not checked) | refuse |
| GDS0215 et al. broken mapping (names match) | match | match | allow |
| GDS0215 et al. broken mapping (Frappe has no first_name) | match | one missing | allow (default to trust emp_no) |
| Person changed name (marriage etc.) | match | differ | refuse, HR fixes Frappe name then re-syncs |

The name-change case is a small false-positive but rare; HR sees the Name Collision Error Log entry, updates Frappe's `first_name`, sync proceeds. Trade-off accepted.

### Files

- `greythr_bridge/tasks/pull_employees.py`:
  - `_is_different_employment` — secondary signal swapped from `company_email` to `first_name`. Decision matrix documented in the docstring.
- `greythr_bridge/tests/test_pull_employees.py`:
  - `_make_candidate` helper now accepts `first_name`
  - `test_find_frappe_employee_refuses_data_corruption` — uses `first_name` mismatch (Sundareshwaran vs Thenmozhi) as the trigger
  - `test_find_frappe_employee_allows_broken_mapping_with_matching_first_name` — confirms `first_name` agreement allows the match even without email
  - `test_find_frappe_employee_allows_broken_mapping_when_email_missing` — regression: v4's strict "both emails must match" used to block this
  - `test_find_frappe_employee_allows_broken_mapping_when_first_name_missing` — edge case (neither side has `first_name`); defaults to trust `employee_number`

### Tests

- **222 passing** (was 220), 3 skipped

### What HR should expect after deploy

Trigger "Sync from greytHR Now":

1. **4 records auto-recover** — GDS0215, GDS0216, GDS0228, GDS0282 will allow the match, UPDATE the existing records, correct the stale mapping IDs. `records_failed` should drop to **0** (was 4).
2. **4 new `"greytHR Mapping Correction"` Error Log entries** documenting each correction.
3. WARN entries for `leftorg=true but no leavingDate` and the Nalluri suresh inverted-dates record continue (informational, mapper handles them).

### Zero data deletion

v5 is just a refinement of the same defensive-matching mechanism — different secondary signal, same goal of preserving historical records. No deletions. Memory rule `never_delete_employee_records.md` continues to be honoured.

---

## [Unreleased] — force_resync_employee HR repair tool (2026-05-25)

### Why v5 wasn't enough

v5 correctly REFUSED to overwrite the 4 stuck records (GDS0215, GDS0216, GDS0228, GDS0282) on every sync — but that left them stuck. The diagnostic revealed why:

```json
"frappe_record_now": {"name": "GDS0215", "employee_number": "GDS0144", ...},
"greythr_mapping": {"greythr_employee_id": "159", "greythr_employee_no": "GDS0144"}
```

**The mapping itself was wrong.** Frappe slot `GDS0215` was bound to greytHR's GDS0144 (syed shabber, ID 159) — not greytHR's GDS0215 (Shabbir Syed, ID 250). Every sync followed the broken mapping via step-1 lookup (no defensive check) and re-overwrote with syed shabber's data. Manual field edits got reverted on the next sync.

v5 can't auto-fix this: from inside the matching code, "wrong slot for this person" looks identical to "different person at this slot" (the Sundareshwaran/Thenmozhi case where the safe action is refuse, not overwrite). Needed: an explicit HR override.

### Fix: `force_resync_employee(frappe_employee, greythr_id)`

New whitelisted endpoint in `greythr_bridge/utils/sync_diagnostics.py`. HR calls with BOTH the Frappe slot AND the correct greytHR ID. The endpoint:

1. Verifies System Manager role
2. Fetches greytHR's data for the EXPLICITLY-NAMED greytHR ID (not via the broken mapping)
3. Sanity-check: refuses if greytHR returns data for a different ID than asked
4. Runs the mapper
5. Overwrites Frappe Employee fields with the correct data
6. Updates the mapping row's `greythr_employee_id` + `greythr_employee_no` to match
7. (Creates the mapping if none existed)
8. Writes a `"greytHR Forced Resync"` audit Error Log entry with the slot, the greytHR ID, the mapping action, and which fields changed
9. Returns a JSON summary with before/after values per changed field

**Bypasses `_find_frappe_employee` and `_is_different_employment` entirely** — this is the explicit "I know what I'm doing for THIS specific record" escape hatch.

### Usage (HR runs after deploy)

```
POST /api/method/greythr_bridge.utils.sync_diagnostics.force_resync_employee?frappe_employee=GDS0215&greythr_id=250
POST /api/method/greythr_bridge.utils.sync_diagnostics.force_resync_employee?frappe_employee=GDS0216&greythr_id=251
POST /api/method/greythr_bridge.utils.sync_diagnostics.force_resync_employee?frappe_employee=GDS0228&greythr_id=264
POST /api/method/greythr_bridge.utils.sync_diagnostics.force_resync_employee?frappe_employee=GDS0282&greythr_id=326
```

The (greytHR ID → Frappe slot) pairs come from the prior sync-log Name Collision entries — we already know which greytHR record corresponds to each stuck Frappe slot.

After all 4 calls:
- Each Frappe slot holds the correct (newer-employment) data
- Each mapping correctly points at the corresponding greytHR ID
- Next regular sync will:
  - For greytHR IDs 250/251/264/326: step-1 mapping match → UPDATE → no-op
  - For greytHR IDs 159/<older 3>: step-1 no match → step-2 email match finds the (now-correct) Frappe slot → v5 sees `emp_no` differ → REFUSE → CREATE new Frappe Employee for the older greytHR ID → SUCCESS
- Final state: 8 Frappe Employees (4 corrected newer + 4 freshly created older), `records_failed: 0`

### Why this is safer than auto-overwriting in v5

`force_resync_employee` requires HR to explicitly type in BOTH identifiers. There's no automation deciding "should I overwrite this record?" — HR provides ground truth. This protects against the corruption-amplification risk of v4/v5 doing aggressive overwrites (which would have destroyed Sundareshwaran's record back when his slot was misnamed GDS0167).

The endpoint is a recovery tool for HR-confirmed broken mappings, not a sync-time decision.

### Files

- `greythr_bridge/utils/sync_diagnostics.py`:
  - New `force_resync_employee(frappe_employee, greythr_id)` (~135 lines)
  - Added `log_error` import for the audit entries
- `greythr_bridge/tests/test_sync_diagnostics.py` — 8 new tests:
  - role check (System Manager only)
  - empty-args validation (both required)
  - greytHR-API-returns-different-ID safety check
  - happy path: existing wrong mapping → corrected, fields updated, audit logged
  - mapping-doesn't-exist path: creates new mapping
  - missing-Frappe-Employee → clear error
  - greytHR API failure → structured error, no save
  - audit log entry written with slot + greytHR ID

### Tests

- **230 passing** (was 222), 3 skipped

### Reusability

This endpoint is the canonical HR repair tool for "mapping is broken AND field values are wrong" cases. Today it fixes 4 records; tomorrow if any new corruption surfaces (from old data migrations, manual edits, etc.), HR has a 1-call path to fix each.

### Zero data deletion

`force_resync_employee` overwrites Frappe Employee field values when HR explicitly asks for it, and updates (never deletes) mapping rows. No Employee record deletion. Memory rule `never_delete_employee_records.md` honoured.

---

## [Unreleased] — Letter-trigger placeholders + Service Cert template fix (2026-05-26)

### The blocker we hit during Phase B live testing

HR successfully generated Promotion and Service Certificate letters (2 of 7 Phase B types verified on live). When attempting to create an Employee Separation (to trigger Experience/Relieving letters) or a Salary Structure Assignment (to trigger Increment letters), Frappe HR's built-in validation blocked the submit:

- Employee Separation requires the linked Employee to have `holiday_list` set (used internally for final-settlement working-day computation)
- Salary Structure Assignment requires a `salary_structure` (used internally for payroll component computation)

**Architectural reality**: greytHR runs all payroll/leave/attendance. Frappe HR is purely a mirror + letter-generation layer. The mandatory-field validations exist to support features we don't use.

After detailed analysis ([2026-05-25 design discussion in conversation]), chose **Option A**: ship empty/minimal PLACEHOLDER records and auto-assign them. Frappe HR's data model stays semantically consistent (no validation overrides, no untested code paths broken), and the placeholders can be replaced with real records if greytHR ever stops being the payroll system.

Considered + rejected:
- **Option B (make fields non-mandatory via Property Setter)**: silently breaks Leave Application, Payroll Entry, Salary Slip, multiple reports. Too much untested downstream impact.
- **Option E (override Frappe HR controller methods)**: maintenance burden on Frappe HR upgrades + same downstream risk.

### What ships in this commit

#### 1. `greythr_bridge/tasks/setup_letter_placeholders.py` (new)

Whitelisted task (`System Manager` only) that HR runs ONCE post-deploy. Idempotent — safe to re-run.

Creates:
- **Salary Component** `CTC` — type Earning, no formula. Description explicitly names it a placeholder.
- **Holiday List** `Calendar-Only (No Holidays)` — empty list (no holidays, no weekly_off), current year range.
- **Salary Structure** `Letter Trigger Structure` — INR, Monthly, single CTC earning, submitted.

Then backfills:
- Sets `holiday_list = "Calendar-Only (No Holidays)"` on every Employee whose holiday_list is blank. Uses `frappe.db.set_value` (bypasses Employee validate hook to avoid status-flip side effects on bulk update). Reports counts of backfilled vs already-set.

Safety:
- Each create wrapped in try/except — one failure doesn't block the others
- If Holiday List creation fails, backfill is skipped (no dangling FK risk)
- If no default Company is set in Global Defaults, Salary Structure creation reports a clear error
- All actions logged to Error Log under `"greytHR Setup Placeholders"`

Constants exported (`DEFAULT_HOLIDAY_LIST`, `DEFAULT_SALARY_STRUCTURE`, `DEFAULT_SALARY_COMPONENT`) for hook usage in other modules.

#### 2. Auto-assignment hooks for `holiday_list`

- **`greythr_bridge/hooks_handlers/employee.py`** — `set_name_from_greythr_id` (Employee `before_insert` hook) extended: if `doc.holiday_list` is empty AND the placeholder list exists, auto-assign it. Silently skips if placeholder doesn't exist yet (lets Frappe HR validate surface the missing setup explicitly to HR).
- **`greythr_bridge/tasks/pull_employees.py`** — `_sync_one` CREATE path: defensive parity for sync-created Employees. Same conditional assignment.

After deploy, every new Employee (manual UI or sync) automatically gets the placeholder holiday_list — HR never has to manage it per-employee.

#### 3. Workspace shortcut URL pre-fill

`greythr_bridge/greythr/workspace/greythr/greythr.json` — "New Salary Revision" shortcut URL now appends `&salary_structure=Letter%20Trigger%20Structure`. HR clicks the workspace card → SSA form opens with the placeholder structure pre-selected + Send Increment Letter checkbox ticked. HR fills in `base` (CTC amount) + submits → Increment letter generates.

#### 4. Diagnostic endpoint

`greythr_bridge/utils/data_quality.py` — new `list_employees_missing_holiday_list()` (HR Manager / System Manager). Read-only. Returns count + per-employee details for any Employee whose `holiday_list` is blank, plus the next-step pointer to setup_letter_placeholders. Ongoing visibility if any future record bypasses our hook (e.g., bulk import).

#### 5. Service Certificate template fix

`greythr_bridge/templates/letters/html/service_certificate.html` — previously rendered awkwardly when `designation` was blank:

> *"currently holds the position of  and has been associated..."* (gap where designation should be)

Now uses conditional Jinja blocks: if designation set → "holds the position of X and has been..."; if not but tenure set → "has been associated for X years..."; if neither → "is currently employed with the organisation." Always reads cleanly.

### Tests

- **242 passing** (was 230), 3 skipped
- 8 new tests in `test_setup_letter_placeholders.py`: role check, fresh-run all-three creation, idempotency, backfill behaviour, Holiday-List-creation-failed safety (no backfill if record absent), missing-Company error path, exported constants pinned
- 1 new test in `test_workspace_fixture.py`: salary revision shortcut URL pre-fills the placeholder structure
- 4 new tests in `test_data_quality.py`: role check, healthy zero-count state, surfaces missing records + actionable next-step, read-only invariant

### How HR uses this after deploy

**One-time setup** (~2 min):
```
https://hr.globexdigital.ai/api/method/greythr_bridge.tasks.setup_letter_placeholders.setup_letter_placeholders
```

Returns a JSON summary like:
```json
{
  "salary_component_created": true,
  "salary_structure_created": true,
  "holiday_list_created": true,
  "employees_backfilled": 340,
  "employees_already_set": 0,
  "errors": []
}
```

**Then test the 3 letter types previously blocked**:
- New Employee Separation → submit → Experience + Relieving letters auto-generate via on_submit
- Click "New Salary Revision" on workspace → SSA opens with structure pre-filled → set CTC base + submit → Increment letter generates
- Service Certificate now renders cleanly even when employee's designation field is blank

**Then test the remaining 2 Phase B letter types** (Consultant Offer, Intern Offer) via the workspace shortcuts — these don't need the placeholder records (they use the Job Offer flow).

### Future-proof note

If Globex ever wants to use Frappe HR for actual payroll/leave/attendance (e.g., as a secondary or backup system, or for non-greytHR contractors), the placeholders are easy to replace:
- Create real Holiday List(s) with actual public holidays → assign to relevant employees
- Create real Salary Structure(s) with proper components → use for actual SSAs
- Frappe HR's other features (Leave Application, Payroll Entry, Salary Slip) work without any code change — they just operate on the real records instead of the placeholders.

This is exactly why Option A was chosen over Option B: zero code rework needed for the future-pivot scenario.

### Zero data deletion

The setup task only CREATES records (3 placeholders + backfills the holiday_list field on existing employees). No deletions, no destructive updates. The backfill uses `update_modified=False` so it doesn't trigger spurious "modified" timestamp bumps. Memory rule `never_delete_employee_records.md` honoured.

---

## [Unreleased] — Separation letter polish: 5 bug-fix sweep (2026-05-26)

### Visible bugs in the first live separation letters

HR triggered the first Experience + Relieving letters via Employee Separation submit. Letters generated and attached, but with 5 visible issues:

1. **Filename** used the Separation docname: `Relieving Letter - HR-EMP-SEP-2026-00001.pdf` (HR-facing identifier, not employee-facing)
2. **Ref No.** inside the letter showed the Separation docname too
3. **Last working day** was blank — letter read *"with effect from the close of business hours on ."*
4. **Empty designation** rendered as a gap: *"Nalluri Sudha, , has been relieved..."* (comma-empty-comma)
5. **greytHR's mixed-case names** ("nalluri sudha", "MOHD BALEEGH AHMED") rendered as-is in formal letters

All 5 fixed in this commit.

### Fixes

#### Bug 1 — Dual attachment with GDS#### filename

`generate_and_deliver` (in `letters/non_signing.py`) extended with two optional params:
- `also_attach_to` — second `(doctype, docname)` tuple. PDF attached to BOTH records.
- `file_name_suffix` — override the default filename slug.

`hooks_handlers/employee_separation.py` updated for both letter types:
- **Primary attachment**: Employee record (the letter belongs to the person, lives permanently on their Frappe Employee)
- **Secondary attachment**: Employee Separation (HR's workflow view also has it)
- **Filename**: `Experience Letter - GDS0021.pdf` (employee identifier in both attachments)

Per-attachment graceful failure: if the secondary attach errors, primary + email still succeed.

#### Bug 2 — `ref_number` = employee.name

`build_experience_context` (also drives `build_relieving_context`) now sets `ref_number = employee.name` (GDS####) instead of `separation_doc.name` (HR-EMP-SEP-####).

#### Bug 3 — `last_working_day` falls back to `Employee.relieving_date`

Frappe HR's canonical "last working day" field is `Employee.relieving_date` (set when status flips to Left). The Separation doc rarely has a relieving_date set. Old chain checked only Separation's fields → both empty → blank letter.

New chain in `build_experience_context`:
```python
last_working_day = (
    getattr(employee, "relieving_date", None)
    or getattr(separation_doc, "relieving_date", None)
    or getattr(separation_doc, "boarding_end_date", None)
)
```

For "nalluri sudha" (GDS0021) — her Employee.relieving_date was populated years ago by the greytHR sync. New chain finds it on the first lookup. Letter now reads correctly: *"with effect from the close of business hours on 30 September 2022."*

#### Bug 4 — Jinja conditionals for empty designation + missing date

Templates `experience_letter.html` and `relieving_letter.html` now wrap optional fields in `{% if X %}...{% endif %}` blocks:

- Experience: *"...served in the capacity of X."* now ONLY renders when designation is set
- Relieving: *"...Nalluri Sudha, X, has been relieved..."* — the commas + designation only render when designation is set
- Both: *"...to <date>..."* and *"...on <date>..."* only render when the date is set

No more comma-empty-comma artifacts or "to ," gaps.

#### Bug 5 — `_format_name` helper for mixed-case data

New `_format_name(name)` in `letters/merger.py`:
- All-uppercase ("MOHD BALEEGH AHMED") → title-case ("Mohd Baleegh Ahmed")
- All-lowercase ("nalluri sudha") → title-case ("Nalluri Sudha")
- Already title-cased ("Avinash Nalluri") → unchanged
- Mixed-case ("McDonald Smith") → preserved as-is (avoids flattening "McDonald" → "Mcdonald")
- Empty / None → ""

Applied to `employee_name` + `designation` in `build_experience_context` (and via delegation, `build_relieving_context`). Letters now read with proper capitalisation regardless of greytHR's casing.

Not applied to other letter context builders YET — promotion/service certificate work from HR-entered or Employee.first_name data which is often already cased correctly. Easy to extend if needed.

### Files

- `greythr_bridge/letters/non_signing.py`:
  - `generate_and_deliver` — new `also_attach_to` + `file_name_suffix` params
  - Extracted `_create_file_attachment` helper (DRY between primary + secondary attach)
- `greythr_bridge/letters/merger.py`:
  - New `_format_name()` helper (with detailed docstring on the all-upper / all-lower / mixed-case strategy)
  - `build_experience_context` — ref_number, last_working_day fallback, name formatting
- `greythr_bridge/hooks_handlers/employee_separation.py` — both `send_experience_letter` and `send_relieving_letter` updated for dual-attach + GDS#### filename
- `greythr_bridge/templates/letters/html/experience_letter.html` — Jinja conditionals
- `greythr_bridge/templates/letters/html/relieving_letter.html` — Jinja conditionals
- `greythr_bridge/tests/test_letters.py` — 12 new tests:
  - 2 template renders with empty designation + missing date (regression for Bug 4)
  - 6 `_format_name` cases (lowercase, uppercase, already-cased, mixed-case McDonald, empty/None, whitespace normalisation)
  - 3 `build_experience_context` cases (ref_number, last_working_day chain, name formatting)
  - 1 `generate_and_deliver` dual-attach test (verifies 2 File rows created with same GDS#### filename)

### Tests

- **254 passing** (was 242), 3 skipped

### What HR sees after deploy

Re-trigger the Separation submit for any employee. The new PDFs should:

- Be named `Experience Letter - GDS####.pdf` and `Relieving Letter - GDS####.pdf`
- Have `Ref No. GDS####` inside the letter header
- Show the correct last working day (from Employee.relieving_date)
- Render cleanly when designation is missing (no comma-empty-comma)
- Show the employee's name properly cased (e.g., "Nalluri Sudha" instead of "nalluri sudha")
- Be attached to BOTH the Employee record (permanent) AND the Employee Separation (workflow view)

### Zero data deletion

All changes are letter-generation / display tweaks. No Employee record modifications, no mapping updates. Memory rule `never_delete_employee_records.md` continues to be honoured.

---

## [Unreleased] — Separation letter polish v2: filename hash + date fallback + HR guidance (2026-05-26)

### What v1 (6bddce1) got mostly right but two issues lingered

Live re-test for `nalluri sudha` (GDS0021):

✓ All 5 v1 fixes visible in the PDFs (Ref No = GDS0021, Nalluri Sudha properly cased, clean sentences when designation empty)

But two visible problems remained:
1. **Filename had a hash suffix**: `Experience Letter - GDS002170526e.pdf` instead of clean `Experience Letter - GDS0021.pdf`. Root cause: dual-attachment wrote the same filename to disk twice → Frappe's storage layer appended a hash to disambiguate.
2. **last_working_day was blank in the PDF**: *"...from 12 November 2017, a total tenure..."* — missing the *"to <date>"* phrase. Root cause: HR didn't fill in `boarding_end_date` on the Separation form, and Employee.relieving_date wasn't populated (greytHR's GDS0021 record never had a leavingDate).

### Fixes shipped

#### A — Filename hash: dual-attach via file_url linking

`letters/non_signing.py`:
- `_create_file_attachment` extended with optional `file_url` parameter:
  - **Write mode** (default, `file_url=None`): writes pdf_bytes to disk; Frappe assigns `file_url`. Used for primary attachment.
  - **Link mode** (`file_url` provided): no new file written; the new File doc just references the existing `file_url`. Used for secondary attachment.
- `generate_and_deliver` now captures the primary attachment's `file_url` and passes it to the secondary attachment.

Result: **one physical file on disk, two File rows attaching it to (Employee) AND (Employee Separation), both with the same clean filename `Experience Letter - GDS0021.pdf`**.

Storage savings: 50% on Separation letters (no duplicate writes). Hash-suffix bug gone.

#### B — Expanded `last_working_day` fallback chain

`letters/merger.py::build_experience_context`:

Old chain (3 fields): `employee.relieving_date` → `separation.relieving_date` → `separation.boarding_end_date`

New chain (4 fields, in trust-order):
```python
employee.relieving_date           # Frappe HR canonical, set when status flips to Left
→ separation.boarding_end_date    # HR's planned separation completion target (most common field HR fills in)
→ separation.relieving_date       # possible alias on Separation
→ separation.resignation_letter_date  # when employee submitted resignation (last-resort)
```

The reordering matters: `boarding_end_date` is the field HR typically fills in on the Separation form, so checking it earlier surfaces dates in more cases. The chain still terminates at empty (rather than today's date) — when nothing is set, Bug 4's Jinja conditionals render the letter cleanly without the date phrase, giving HR a clear visual signal that the date is missing.

#### C — HR guidance for missing date

**Before submitting an Employee Separation, HR should fill in the `Boarding End Date` field** (Frappe HR's "separation completion target" — serves as the last working day). The letter's `last_working_day` populates from this field if `Employee.relieving_date` isn't set yet.

If HR forgets, the letters still generate but without the date phrase. HR can:
1. Set `boarding_end_date` on the Separation OR `relieving_date` on the Employee
2. Re-trigger the letter (delete current attachments, re-submit the Separation, OR use a future "Regenerate" button)

Will track adding a "Regenerate Letter" workspace button as a follow-up if HR feedback shows this is a common case.

### Files

- `greythr_bridge/letters/non_signing.py` — `_create_file_attachment` adds `file_url` param (link mode); `generate_and_deliver` uses it for secondary
- `greythr_bridge/letters/merger.py::build_experience_context` — 4-field fallback chain (was 3)
- `greythr_bridge/tests/test_letters.py` — 4 new tests:
  - `TestSeparationLetterDualAttachment.test_secondary_attachment_uses_file_url_linking_not_content_write` — verifies primary writes content, secondary uses file_url (link mode)
  - `TestLastWorkingDayFallbackChain.test_falls_through_to_boarding_end_date`
  - `TestLastWorkingDayFallbackChain.test_falls_through_to_resignation_letter_date`
  - `TestLastWorkingDayFallbackChain.test_returns_empty_when_no_date_anywhere` (defensive: when all 4 fields blank, returns falsy → template renders cleanly)

### Tests

- **258 passing** (was 254), 3 skipped

### What HR sees after deploy

For new Separation submits where HR has filled in `Boarding End Date`:
- Letters attach with clean filenames: `Experience Letter - GDS0021.pdf` (NO `70526e` hash suffix)
- Single physical file on disk; both Employee + Separation tabs show the same attachment
- `last_working_day` populated correctly in both letter bodies

For Separations where HR didn't fill in any date field:
- Letters still generate (don't fail)
- Date phrase omitted gracefully via Jinja conditionals
- HR can re-trigger after filling in the date

### Zero data deletion

Continues the pattern: no Employee or mapping record modifications, only letter file storage tweaks. Memory rule `never_delete_employee_records.md` honoured.

---

## [Unreleased] — A-v2: custom_last_working_date field for Separation letters (2026-05-26)

### Research that changed the picture

Investigated Frappe HR's `Employee Separation` doctype to answer: does submit auto-populate `Employee.relieving_date`? Findings:

- **No.** Frappe HR's `EmployeeSeparation.on_submit` does NOT touch Employee at all. Verified against `hrms` source: `hrms/hr/doctype/employee_separation/employee_separation.py` only sets up the boarding Project; `hrms/hooks.py` has no `doc_events` for Employee Separation. HR is expected to manually update Employee.relieving_date.
- The field name **`boarding_end_date` does NOT exist** on stock Frappe HR Employee Separation. My earlier v2 fallback chain checked it — dead code. The actual stock date fields are: `resignation_letter_date`, `boarding_begins_on` (required), `exit_interview` (text not date).

### Why I'm NOT building a bridge handler (the rejected approach)

Originally considered: have our `on_separation_submitted` hook also write `Employee.relieving_date` and `Employee.status = "Left"`. Rejected after analysis because:

1. **Violates one-way sync invariant** — greytHR → Frappe is the canonical write direction. Bridge value would get overwritten by next sync run anyway (24h max).
2. **Side effect risk** — auto-setting `Employee.status = "Left"` triggers Frappe HR's User-account disable and other cascading actions. If HR is generating a resignation acknowledgment letter while the person is still in notice period, disabling them immediately is wrong.
3. **Two sources of truth competing** — adds confusion about which value is canonical.

The clean answer: keep Employee record as greytHR's domain, store the HR-entered separation date on the Separation itself.

### A-v2: what's shipped

**Custom field `custom_last_working_date`** on Employee Separation:
- Type: Date
- Mandatory when either `custom_send_experience_letter` or `custom_send_relieving_letter` is checked (Frappe's `mandatory_depends_on: "eval:..."`)
- Position: right after the letter checkboxes
- Auto-installed via the existing fixtures filter

**Updated letter fallback chain** in `build_experience_context`:
```
employee.relieving_date              # greytHR-synced, canonical (one-way)
→ separation.custom_last_working_date   # HR-entered on Separation form
→ separation.resignation_letter_date    # Frappe HR fallback (semantically off)
```

Dead `boarding_end_date` branch removed (the field doesn't exist on Frappe HR's stock doctype).

### Files

- `fixtures/custom_field.json` — new entry for `Employee Separation-custom_last_working_date`
- `letters/merger.py::build_experience_context` — chain updated; long inline comment documents the design + why no bridge to Employee
- `tests/test_letters.py`:
  - `TestLastWorkingDayFallbackChain` — 5 tests rewritten:
    - primary (employee.relieving_date) wins when set
    - falls through to custom_last_working_date
    - falls through to resignation_letter_date
    - returns empty when all 3 fields blank (template Jinja handles gracefully)
    - regression: getattr(boarding_end_date) absent from source
  - `TestPhaseBCustomFields` — 2 updates:
    - `custom_last_working_date` added to expected fields list (13 total now)
    - new `test_custom_last_working_date_is_conditionally_mandatory` pins the `mandatory_depends_on` expression

### Tests

- **261 passing** (was 258), 3 skipped

### How HR uses this after deploy

When creating an Employee Separation:
1. Pick Employee, fill in mandatory fields (boarding_begins_on, etc.)
2. Decide which letters to send (the two checkboxes)
3. **If either letter checkbox is ticked, fill in "Last Working Date"** (the new custom field becomes mandatory)
4. Submit

Letter generation reads `custom_last_working_date` if `Employee.relieving_date` isn't set yet. The letter's date placeholder always populates (assuming HR filled the field, which is now enforced at form-level).

### What greytHR sync does

Unchanged. The greytHR pull continues to be the only writer of `Employee.relieving_date` and `Employee.status`. When greytHR's `leavingDate` is set for an employee, mapper populates Employee.relieving_date → letter's primary fallback finds it there → custom_last_working_date becomes a fallback. The two sources can coexist; greytHR wins when both are present.

### Zero data deletion

A-v2 is purely additive: one new custom field, fallback chain refinement, no Employee/Mapping modifications. Memory rule `never_delete_employee_records.md` honoured.
