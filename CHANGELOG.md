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
