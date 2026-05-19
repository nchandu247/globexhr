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
- ⬜ **End-to-end test:** Blocked until Phase 4 (letter templates) is complete —
  _generate_pdf() requires Print Format records to exist.
