# greythr_bridge — Build Plan for Claude Code

> **How to use this file:** Save this as `PLAN.md` at the root of your project repository. When starting any Claude Code session, the first thing to say is: *"Read PLAN.md and CLAUDE.md before doing anything. Then tell me which phase we're in and what's next."* This keeps every session grounded in the same context.

---

## 0. Project Identity

**Name:** `greythr_bridge`
**Type:** Custom Frappe app installed alongside Frappe HR on Frappe Cloud
**Purpose:** Two-way integration between Frappe HR (system for letters + onboarding workflow) and greytHR (system of record for employee master, payroll, statutory data)
**Company:** Globex Digital Solutions Pvt Ltd
**License:** Proprietary (internal use only — does not get distributed)
**Repo:** `https://github.com/nchandu247/globexhr` (private)

---

## 1. Context — Read This First

We use **greytHR Essential plan** for payroll. It does not include letter generation or
onboarding modules on our tier. Rather than upgrade greytHR (expensive at our headcount,
scales linearly with employees), we are adopting **Frappe HR** as the application HR uses
for offer letters, appointment letters, onboarding workflows, and all employee documents.
Frappe HR runs on **Frappe Cloud** at $25/month on a Private Bench.

The custom app we're building, `greythr_bridge`, sits inside the same Frappe install.
It does three things:
1. **Pulls** employee master data from greytHR into Frappe HR (so HR doesn't re-enter data)
2. **Pushes** letters and new joiners from Frappe HR back to greytHR (so greytHR remains the source of truth)
3. **Orchestrates** e-signature flows via Zoho Sign (so letters get legally signed before going to greytHR)

We are a ~150-employee company growing to 500+ in the next 12 months, based in India.
We must comply with the DPDP Act (data residency in India, consent, right to erasure)
and the IT Act 2000 (e-signature validity).

### ⚠️ Pre-build verifications (do these before writing any Phase 1 code)

1. **greytHR Essential plan API coverage** — Confirm with greytHR support that the
   following endpoints are available on our plan tier:
   - `POST /employee/v2/employees` (create new employee — needed for Phase 6)
   - `POST /payroll/v2/salary/revision/employees/{id}` (push salary revision — Phase 6)
   - `POST /employee/v2/employee-docs/{id}/{category}` (upload signed PDF — Phase 6)
   If any of these are Enterprise-only, the Phase 6 push direction needs to be redesigned
   before Phase 1 client code is written. Record the outcome here: `______________`

2. **Zoho Sign India data residency** — Signed offer letters contain candidate PII. Confirm
   that the Zoho Sign account is provisioned on the India data center (in.zoho.com).
   If the account was created on a non-India server, create a new account before Phase 5.
   Record the data center in use here: `______________`

### What success looks like
- Time-to-issue an offer letter drops from days to under 4 hours
- HR time per letter drops from ~30 minutes to under 5 minutes
- Zero data drift between Frappe HR and greytHR
- All signed letters end up in greytHR's Document Center automatically
- Onboarding cases are tracked end-to-end with no manual coordination
- PII is stored only in India-resident systems (Frappe Cloud AWS Mumbai + Zoho Sign India DC); DPDP consent is captured and honoured

---

## 2. Architecture & Conventions

### 2.1 Architecture diagram

```
                    HR users (browser)
                          │
                          ▼ https://hr.globexdigital.ai
        ┌─────────────────────────────────────────────────┐
        │   Frappe Cloud — Private Bench ($25/mo site)    │
        │                                                 │
        │  ┌──────────────────────────────────────────┐   │
        │  │  Frappe HR (upstream, NEVER modified)    │   │
        │  └──────────────────────────────────────────┘   │
        │                                                 │
        │  ┌──────────────────────────────────────────┐   │
        │  │  greythr_bridge (THIS APP)               │   │
        │  │   • doctype/greythr_settings/            │   │
        │  │   • api/ (client + endpoint wrappers)    │   │
        │  │   • tasks/ (scheduled jobs)              │   │
        │  │   • hooks_handlers/ (doc event handlers) │   │
        │  │   • webhooks/ (incoming from Zoho Sign)  │   │
        │  │   • utils/ (retry, rate limiter, log)    │   │
        │  └──────────────────────────────────────────┘   │
        └─────────┬──────────────────────┬────────────────┘
                  │ REST + OAuth 2.0     │ REST
                  ▼                      ▼
        ┌─────────────────────┐   ┌────────────────┐
        │   greytHR Cloud     │   │   Zoho Sign    │
        └─────────────────────┘   └────────────────┘
```

### 2.2 Iron-clad conventions

**These are not suggestions. Follow them in every file, every commit.**

1. **NEVER modify Frappe HR or Frappe Framework core code.** All extensions go in
   `greythr_bridge`. If a customization seems to require core changes, stop and ask —
   there is always a hook or fixture that achieves the same result.

2. **All greytHR API calls go through `greythr_bridge.api.client.GreytHRClient`.**
   Never call `requests.get(...)` to greytHR from anywhere else. The client handles auth,
   retries, rate-limiting, and logging — duplication breaks observability.

3. **All Zoho Sign API calls go through `greythr_bridge.api.zoho_sign`.**
   Never call the Zoho Sign REST API directly from tasks, hooks, or webhooks.

4. **All credentials live in the `greytHR Settings` DocType.** Never hardcode
   `client_id`, `client_secret`, `zoho_api_key`, `zoho_sign_webhook_secret`, or any other
   secret in source. The DocType uses Frappe's `Password` field type, which is encrypted
   at rest. Never read secrets from `frappe.conf` or environment variables.

5. **All sync operations are idempotent.** Running `pull_employees` twice in a row must
   produce the same result. Running `push_signed_pdf` twice for the same letter must not
   create a duplicate in greytHR — use the Frappe document name as the idempotency key.

6. **All async work goes through Frappe's job queue (`frappe.enqueue`) with the correct
   queue type.** HTTP webhook handlers must return within 5 seconds — all real work gets
   enqueued before returning 200. Use queue types deliberately:
   - `queue="short"` — webhook-triggered jobs (must start within seconds)
   - `queue="long"` — bulk sync jobs (pull_employees for 500 employees, pull_salary)
   - `queue="default"` — everything else
   Never block a webhook handler with synchronous work.

7. **All errors are logged to Frappe's Error Log via `frappe.log_error(message, title)`.**
   Never use `print()` or bare `pass` on exceptions. Log only: employee IDs, document
   names, operation names, HTTP status codes, API call durations, sync counts.
   Never log: full employee records, candidate PII (name, email, mobile, Aadhaar, PAN),
   signed PDFs, OAuth tokens, or webhook payloads in full. This is both an operational
   hygiene rule and a DPDP Act compliance requirement.

8. **All custom DocTypes are prefixed with `greytHR`** to avoid name collisions with
   Frappe HR (e.g. `greytHR Settings`, `greytHR Sync Log`, `greytHR Mapping`).

9. **Custom fields on Frappe HR core DocTypes are prefixed with `custom_`**
   (e.g. `custom_greythr_employee_id`). Added via Customize Form, exported as fixtures.

10. **Every function that calls greytHR or Zoho Sign has a unit test.** Use the `responses`
    library to mock HTTP calls. Tests must run fully offline — no real API calls in CI.

11. **Every PR (or commit batch) has a `CHANGELOG.md` entry.** Even if you're the only
    developer — future-you will thank you.

12. **All greytHR HTTP calls are rate-limited to 10 requests/second.** The rate limiter
    lives inside `GreytHRClient._request()` via `@rate_limited` from `utils/rate_limiter.py`.
    Never call greytHR in a tight loop without going through the client.

13. **Read this file at the start of every Claude Code session.** Mention which phase
    you're in and what's next.

### 2.3 Naming

| Thing | Convention | Example |
|---|---|---|
| Python module | `snake_case` | `pull_employees.py` |
| Python class | `PascalCase` | `GreytHRClient` |
| Python function | `snake_case` | `fetch_employees(page=1)` |
| Frappe DocType | `Title Case With Spaces` | `greytHR Sync Log` |
| Frappe field | `snake_case` | `employee_number` |
| Custom Field on core DocType | prefix with `custom_` | `custom_greythr_employee_id` |
| Webhook URL | `/api/method/greythr_bridge.webhooks.<name>.callback` | `.../zoho_sign.callback` |

**Important Frappe hook naming note:** Frappe's `Employee` DocType does not emit an
`on_status_change` event. To react to a status change, use the `on_update` hook and
compare `doc.status` against `doc.get_doc_before_save().status` inside the handler.
Never register `on_status_change` in `hooks.py` — it will silently never fire.

### 2.4 Minimal scaffold for Phase 0

`pyproject.toml`:
```toml
[project]
name = "greythr_bridge"
authors = [{ name = "Globex Digital Solutions Pvt Ltd", email = "hr@globexdigital.ai" }]
description = "Bridge between Frappe HR and greytHR Cloud"
requires-python = ">=3.10"
readme = "README.md"
dynamic = ["version"]
dependencies = ["ratelimit"]

[build-system]
requires = ["flit_core >=3.4,<4"]
build-backend = "flit_core.buildapi"

[tool.flit.module]
name = "greythr_bridge"
```

`greythr_bridge/__init__.py`:
```python
__version__ = "0.0.1"
```

`greythr_bridge/hooks.py` (minimum):
```python
app_name = "greythr_bridge"
app_title = "greytHR Bridge"
app_publisher = "Globex Digital Solutions Pvt Ltd"
app_description = "Integration between Frappe HR and greytHR"
app_email = "hr@globexdigital.ai"
app_license = "Proprietary"
required_apps = ["frappe/hrms"]  # does not require ERPNext
```

`greythr_bridge/modules.txt`:
```
greytHR Bridge
```

`requirements.txt`:
```
responses
pytest
ratelimit
```

`.gitignore`:
```
__pycache__/
*.pyc
*.pyo
.env
.DS_Store
*.egg-info/
dist/
.pytest_cache/
```

`.github/workflows/ci.yml` (stub — expands in Phase 1 once tests exist):
```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: pytest greythr_bridge/tests/ -v
```

---

## 3. Data Model

We need a small number of custom DocTypes inside `greythr_bridge`, plus a few **custom
fields** added to Frappe HR's existing DocTypes.

### 3.1 New DocTypes (created in `greythr_bridge`)

#### `greytHR Settings` (Single DocType — only one record ever exists)

| Field | Type | Purpose |
|---|---|---|
| `enabled` | Check | Master kill-switch for the integration |
| `api_base_url` | Data | `https://api.greythr.com` — base URL for all data endpoint calls |
| `tenant_domain` | Data | `globex.greythr.com` — used to construct OAuth URL (`https://{tenant_domain}/uas/v1/oauth2/client-token`) and as `x-greythr-domain` header on every data call |
| `client_id` | Data | OAuth Client ID |
| `client_secret` | Password | OAuth Client Secret (encrypted at rest) |
| `cached_token` | Password | OAuth bearer token (encrypted; auto-refreshed) |
| `token_expires_at` | Datetime | When cached token expires |
| `zoho_sign_api_key` | Password | Zoho Sign API key |
| `zoho_sign_account_id` | Data | Zoho Sign account ID |
| `zoho_sign_webhook_secret` | Password | HMAC secret for verifying Zoho Sign webhook callbacks — set in Zoho Sign console and mirrored here |
| `zoho_sign_template_ids` | JSON | Map of letter type → Zoho Sign template ID, e.g. `{"offer_letter": "abc123", "nda": "xyz789"}` |
| `default_signatory` | Link → User | Default authorised signatory for letters |
| `dry_run` | Check | If on, log API calls but don't make them (for testing) |
| `last_employee_sync` | Datetime | Timestamp of last successful employee pull |
| `last_salary_sync` | Datetime | Timestamp of last successful salary structure pull |

Permissions: only **System Manager** can read or write.

#### `greytHR Sync Log` (one record per sync operation)

| Field | Type | Purpose |
|---|---|---|
| `sync_type` | Select | `Pull Employees`, `Pull Salary`, `Push Employee`, `Push Signed PDF`, `Push Salary Revision`, `Update Employee Status` |
| `status` | Select | `Started`, `Success`, `Partial Success`, `Failed` |
| `started_at` | Datetime | |
| `completed_at` | Datetime | |
| `records_processed` | Int | |
| `records_created` | Int | |
| `records_updated` | Int | |
| `records_failed` | Int | |
| `records_skipped` | Int | Records skipped due to validation errors (not hard failures) |
| `resume_cursor` | Data | Last successfully processed page/cursor — allows a failed bulk run to resume rather than restart |
| `queue_job_id` | Data | Frappe background job ID — use to trace the log entry back to the RQ job |
| `error_summary` | Long Text | Truncated error messages if any |
| `details` | JSON | Full per-record details for debugging |
| `triggered_by` | Select | `Scheduled`, `Manual`, `Hook`, `Webhook` |
| `related_doctype` | Data | If triggered by a Frappe doc event |
| `related_docname` | Data | |

Indexed by `sync_type` and `started_at`.

Permissions: **System Manager** can read/write. **HR Manager** can read (so HR can
check sync status without touching settings).

#### `greytHR Employee Mapping` (links Frappe Employee ↔ greytHR Employee)

| Field | Type | Purpose |
|---|---|---|
| `frappe_employee` | Link → Employee | Unique |
| `greythr_employee_id` | Data | Unique; from greytHR's `id` field |
| `greythr_employee_no` | Data | greytHR employee number (human-readable) |
| `first_synced_at` | Datetime | |
| `last_synced_at` | Datetime | |
| `last_pushed_at` | Datetime | When this employee was last written to greytHR |
| `sync_status` | Select | `In Sync`, `Drift Detected`, `Push Pending`, `Push Failed` |
| `last_sync_error` | Small Text | Most recent error message for this employee — visible to HR Manager so they can filter `sync_status=Push Failed` and see exactly why without digging into logs |

### 3.2 Custom Fields on Frappe HR DocTypes

Added via Frappe's "Customize Form" feature, then exported as fixtures (see Phase 0).

| DocType | Field | Type | Purpose |
|---|---|---|---|
| `Employee` | `custom_greythr_employee_id` | Data, read-only | greytHR's internal ID, set by bridge |
| `Employee` | `custom_greythr_last_synced` | Datetime, read-only | Last sync timestamp |
| `Employee` | `custom_pushed_to_greythr` | Check, read-only | True once employee exists in greytHR |
| `Employee` | `custom_appointment_letter_generated` | Check, read-only | True once Appointment Letter has been sent for e-signature after joining (Phase 7) |
| `Job Offer` | `custom_zoho_sign_request_id` | Data, read-only | Set when Offer Letter sent to Zoho Sign |
| `Job Offer` | `custom_zoho_sign_nda_request_id` | Data, read-only | Set when NDA sent to Zoho Sign |
| `Job Offer` | `custom_zoho_sign_signed_at` | Datetime, read-only | Timestamp when candidate completed signing — populated by webhook handler |
| `Job Offer` | `custom_signed_pdf_pushed` | Check, read-only | True once signed PDF is in greytHR |
| `Salary Structure Assignment` | `custom_pushed_to_greythr` | Check, read-only | True once revision is pushed |

---

## 4. Code Structure

```
greythr_bridge/
├── README.md                              # Stubbed in Phase 0; completed in Phase 10.
│                                          # Covers: install, configure, run tests, deploy.
├── CHANGELOG.md                           # Every change logged here
├── PLAN.md                                # THIS FILE
├── CLAUDE.md                              # Compact conventions for Claude Code sessions
├── pyproject.toml                         # Frappe app metadata + dependencies
├── license.txt                            # Proprietary — Globex Digital Solutions Pvt Ltd
├── requirements.txt                       # responses, pytest, ratelimit, ...
│
├── greythr_bridge/
│   ├── __init__.py                        # __version__ = "0.0.1"
│   ├── hooks.py                           # Frappe wiring (events, schedulers, fixtures)
│   ├── modules.txt                        # Frappe module list
│   ├── patches.txt                        # DB migrations
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── client.py                      # GreytHRClient — OAuth, HTTP, rate-limit,
│   │   │                                  # retry, dry_run. All greytHR calls go here.
│   │   ├── employee.py                    # GET/POST /employee/v2/...
│   │   ├── payroll.py                     # GET/POST /payroll/v2/...
│   │   ├── docs.py                        # POST /employee/v2/employee-docs/...
│   │   ├── zoho_sign.py                   # Zoho Sign REST wrapper:
│   │   │                                  #   send_for_signature(), get_signed_document(),
│   │   │                                  #   resend_signing_request()
│   │   └── exceptions.py                  # GreytHRError, GreytHRAuthError,
│   │                                      # GreytHRRateLimitError, GreytHRServerError,
│   │                                      # GreytHRClientError, ZohoSignError
│   │
│   ├── mappers/
│   │   ├── __init__.py
│   │   ├── employee_mapper.py             # greytHR JSON ↔ Frappe Employee
│   │   ├── salary_mapper.py               # greytHR salary ↔ Frappe Salary Structure
│   │   └── job_offer_mapper.py            # Frappe Job Offer → greytHR new employee
│   │
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── pull_employees.py              # Scheduled — every 15 min
│   │   ├── pull_salary_structures.py      # Scheduled — daily 2 AM
│   │   ├── push_new_joiner.py             # Enqueued — triggered by Zoho Sign webhook
│   │   ├── push_signed_pdf.py             # Enqueued — triggered by Zoho Sign webhook
│   │   └── reconcile_drift.py             # Scheduled — daily 3 AM (detects mismatches)
│   │
│   ├── hooks_handlers/                    # Named to avoid confusion with hooks.py.
│   │   ├── __init__.py                    # These are registered under doc_events in hooks.py.
│   │   ├── job_offer.py                   # on_submit → send NDA then Offer for e-signature
│   │   │                                  # on_update_after_submit → resend if needed
│   │   ├── employee.py                    # on_update: compare doc.status vs
│   │   │                                  # doc.get_doc_before_save().status to detect
│   │   │                                  # status changes. NOT on_status_change
│   │   │                                  # (that event does not exist in Frappe).
│   │   └── salary_assignment.py           # on_submit → enqueue push_salary_revision
│   │
│   ├── webhooks/
│   │   ├── __init__.py
│   │   └── zoho_sign.py                   # @frappe.whitelist(allow_guest=True)
│   │                                      # Verifies HMAC + timestamp, enqueues real work,
│   │                                      # returns 200 within 5 seconds.
│   │
│   ├── doctype/
│   │   ├── greythr_settings/
│   │   │   ├── greythr_settings.json
│   │   │   ├── greythr_settings.py
│   │   │   └── greythr_settings.js
│   │   ├── greythr_sync_log/
│   │   │   ├── greythr_sync_log.json
│   │   │   └── greythr_sync_log.py
│   │   └── greythr_employee_mapping/
│   │       ├── greythr_employee_mapping.json
│   │       └── greythr_employee_mapping.py
│   │
│   ├── fixtures/                          # Exported customisations — auto-loaded on install
│   │   └── custom_field.json              # All custom_ fields on Employee, Job Offer, SSA
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── retry.py                       # @retry decorator — exponential backoff for 5xx
│   │   ├── rate_limiter.py                # 10 req/sec token bucket for greytHR API calls
│   │   ├── idempotency.py                 # Idempotency key helpers (Frappe docname-based)
│   │   └── logging.py                     # Wrappers around frappe.log_error;
│   │                                      # strips PII before logging
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                    # pytest fixtures, mocks, responses activation
│       ├── test_client.py                 # GreytHRClient: token fetch, cache, 401 retry,
│       │                                  # 500 retry, 4xx no-retry, rate limit, dry_run
│       ├── test_pull_employees.py         # Mapper + task: create, update, skip, error paths
│       ├── test_push_signed_pdf.py        # Idempotency, missing attachment, greytHR error
│       ├── test_zoho_sign.py              # send_for_signature, HMAC verify, expiry/resend
│       ├── test_mappers.py                # Pure unit tests — no HTTP mocking needed
│       └── fixtures/                      # Sample API responses (static JSON files)
│           ├── employee_list_response.json
│           ├── employee_detail_response.json
│           ├── salary_repository_response.json
│           └── zoho_sign_callback_payload.json
```

---

## 5. Phase-by-Phase Build Plan

Each phase has clear deliverables and a verification step. **Do not move to the next phase until the current phase is verified working.**

---

### Phase 0 — Scaffolding (Week 1)

**Goal:** Empty app deployed; greytHR API verified; HR sees Frappe HR.

#### Tasks

- [ ] 0.0 **Pre-build verifications** (block everything else on these):
  - Confirm with greytHR support that `POST /employee/v2/employees`,
    `POST /payroll/v2/salary/revision/employees/{id}`, and
    `POST /employee/v2/employee-docs/{id}/{category}` are available on the Essential plan.
    **Must be tested with the correct auth combo** (`ACCESS-TOKEN` header +
    `x-greythr-domain: globex.greythr.com` — not `Authorization: Bearer`). Earlier
    attempts with the wrong auth pattern may have produced false results.
    Record outcome here: `______________`
  - Confirm Zoho Sign account is on the India data center (in.zoho.com).
    Record DC here: `______________`
- [ ] 0.1 Sign up for Frappe Cloud free trial; create site `hr-globexdigital` on Private
       Bench, $25/mo, AWS Mumbai region
- [ ] 0.2 Install Frappe HR (the `hrms` app) at site creation
- [ ] 0.3 Run Frappe HR setup wizard: company = "Globex Digital Solutions Pvt Ltd",
       country = India, currency = INR, fiscal year start = April 1
- [ ] 0.4 Set system timezone to `Asia/Kolkata`, date format to `dd-mm-yyyy`
- [ ] 0.5 In greytHR Admin portal: create API user; note Client ID + Secret;
       store in password manager (not in source)
- [ ] 0.6 Test greytHR OAuth from laptop with `curl`; confirm employee list returns data
- [ ] 0.7 Configure custom domain `hr.globexdigital.ai` in Frappe Cloud; verify SSL works
- [ ] 0.8 Invite HR team members as Frappe users with HR Manager role
- [ ] 0.9 Create GitHub repo `greythr_bridge` (private); commit minimal scaffold per
       Section 2.4, including `.gitignore` and `.github/workflows/ci.yml` stub so CI
       is live before the first test is written
- [ ] 0.9b Create stub `README.md` with: purpose, install steps, how to run tests,
       how to configure greytHR Settings. Placeholder sections are fine — the point is
       the file exists so `pyproject.toml` doesn't fail and future developers aren't lost.
- [ ] 0.10 Add GitHub repo to Frappe Cloud bench; deploy; install on site

#### Verification
- `bench --site hr-globexdigital list-apps` shows `greythr_bridge`
- App appears under "Installed Apps" in site dashboard
- `curl` against greytHR API returns 200 with employee data
- `README.md` exists and has at least stub sections for install + test

---

### Phase 1 — Settings + API Client (Week 2)

**Goal:** A bullet-proof `GreytHRClient` that handles auth, retries, rate-limiting,
and logging. Nothing else moves forward until this is solid.

#### Tasks
- [ ] 1.1 Create `greytHR Settings` DocType (single) with all fields per Section 3.1
- [ ] 1.2 Create `greytHR Sync Log` DocType per Section 3.1
- [ ] 1.3 Implement `api/exceptions.py` with:
       `GreytHRError`, `GreytHRAuthError`, `GreytHRRateLimitError`,
       `GreytHRServerError`, `GreytHRClientError`, `ZohoSignError`
- [ ] 1.4 Implement `utils/retry.py`: `@retry` decorator with exponential backoff
       (1s, 2s, 4s; max 3 attempts; only retries on 5xx and connection errors —
       never on 4xx, never on auth errors).
       Implement `utils/rate_limiter.py`: token bucket at 10 req/sec using the
       `ratelimit` library. Exposed as `@rate_limited` decorator applied inside
       `GreytHRClient._request()`.
- [ ] 1.5 Implement `api/client.py` — see detailed spec below
- [ ] 1.6 Add bench-callable: `bench --site hr-globexdigital execute
       greythr_bridge.api.client.test_connection` that prints the first employee's name
- [ ] 1.7 Write tests (`tests/test_client.py`) covering:
       - Successful token fetch and cache hit (no second OAuth call)
       - Stale token: 401 → clear cache → re-fetch token → retry → success
       - Stale token: 401 → re-fetch → 401 again → raises `GreytHRAuthError` (no loop)
       - 500 response: retries 3× with backoff → raises `GreytHRServerError`
       - 429 response: raises `GreytHRRateLimitError` immediately (no retry)
       - 4xx (non-401): raises `GreytHRClientError` immediately (no retry)
       - `dry_run=True`: no HTTP call made, returns `{}`
       - Rate limiter: rapid burst of 15 calls takes ≥1.5 seconds
       - 200 + `text/html` Content-Type → clear cache → retry → success (silent auth rejection self-heal)
       - 200 + `text/html` → retry → `text/html` again → raises `GreytHRAuthError` (no infinite loop)
- [ ] 1.8 Run tests in CI (GitHub Actions); they must pass before merge

#### `GreytHRClient` detailed spec

> **greytHR auth is non-standard.** Two different hosts, non-Bearer token header.
> Read the docstring carefully before editing this class.

```python
# greythr_bridge/api/client.py
import frappe
import requests
from datetime import datetime, timedelta
from .exceptions import (
    GreytHRAuthError, GreytHRRateLimitError,
    GreytHRServerError, GreytHRClientError
)
from ..utils.retry import retry
from ..utils.rate_limiter import rate_limited

class GreytHRClient:
    """
    HTTP client for greytHR REST API.

    Auth contract (greytHR-specific, non-standard):
      - OAuth token: POST to https://{tenant_domain}/uas/v1/oauth2/client-token
        using HTTP Basic auth header (Base64 of client_id:client_secret), NOT body params.
        The data API host (api.greythr.com) and the OAuth host (tenant_domain) are DIFFERENT.
      - Data calls: ACCESS-TOKEN: <raw_token> header — NO "Bearer" prefix.
      - x-greythr-domain: {tenant_domain} header required on every data call.
      - Accept: application/json required — omitting it can trigger 403.
      - Silent failure trap: greytHR returns 200 + text/html when auth is rejected.
        Always validate Content-Type; treat HTML response as auth failure and retry once.

    Other responsibilities:
      - Cache token in greytHR Settings DocType (TTL from expires_in; ~45 days in practice)
      - Auto-refresh on 401 or silent HTML rejection (one retry only — no loop)
      - Retry 5xx with exponential backoff (3 attempts, 1s/2s/4s)
      - Surface 4xx immediately (no retry)
      - Rate-limit to 10 req/sec via @rate_limited decorator
      - Respect 'dry_run' flag from settings (log but don't call)

    Usage:
      client = GreytHRClient()
      employees = client.get("/employee/v2/employees", params={"page": 1, "size": 50})
    """

    def __init__(self):
        self.settings = frappe.get_single("greytHR Settings")
        if not self.settings.enabled:
            raise GreytHRClientError("greytHR integration is disabled in Settings")

    def _get_token(self) -> str:
        """Return a valid token, refreshing from greytHR OAuth if expired or missing."""
        now = datetime.now()
        expires_at = self.settings.token_expires_at
        if self.settings.cached_token and expires_at and expires_at > now + timedelta(minutes=5):
            return self.settings.get_password("cached_token")

        # OAuth endpoint is on the TENANT host, not api.greythr.com.
        # Credentials go in an HTTP Basic auth header — NOT in the POST body.
        resp = requests.post(
            f"https://{self.settings.tenant_domain}/uas/v1/oauth2/client-token",
            data={"grant_type": "client_credentials"},
            auth=(
                self.settings.client_id,
                self.settings.get_password("client_secret"),
            ),
            timeout=15,
        )
        if resp.status_code != 200:
            raise GreytHRAuthError(f"Token fetch failed: {resp.status_code}")

        token_data = resp.json()
        self.settings.cached_token = token_data["access_token"]
        self.settings.token_expires_at = now + timedelta(
            seconds=token_data.get("expires_in", 3_888_000)  # default ~45 days
        )
        self.settings.save(ignore_permissions=True)
        return token_data["access_token"]

    def _clear_token_cache(self):
        """Invalidate cached token so the next call fetches a fresh one."""
        self.settings.cached_token = None
        self.settings.token_expires_at = None
        self.settings.save(ignore_permissions=True)

    @rate_limited(calls=10, period=1)
    @retry(exceptions=(GreytHRServerError, requests.ConnectionError), tries=3, backoff=2)
    def _request(self, method: str, path: str, _auth_retry: bool = True, **kwargs) -> dict:
        """
        One HTTP call with auth, rate-limiting, error mapping, and auth auto-retry.

        greytHR quirks handled here:
          - ACCESS-TOKEN header (not Authorization: Bearer)
          - x-greythr-domain required on every data call for tenant routing
          - 200 + text/html = silent auth rejection — must check Content-Type
        """
        if self.settings.dry_run:
            frappe.logger().info(f"[DRY RUN] {method} {path} kwargs={list(kwargs.keys())}")
            return {}

        url = self.settings.api_base_url + path
        headers = kwargs.pop("headers", {})
        headers.update({
            "ACCESS-TOKEN":     self._get_token(),   # raw token — no Bearer prefix
            "x-greythr-domain": self.settings.tenant_domain,
            "Accept":           "application/json",
        })

        resp = requests.request(method, url, headers=headers, timeout=30, **kwargs)

        # greytHR silent failure: stale/missing token returns 200 with HTML login page
        if "text/html" in resp.headers.get("Content-Type", ""):
            if _auth_retry:
                self._clear_token_cache()
                return self._request(method, path, _auth_retry=False, **kwargs)
            raise GreytHRAuthError(
                "Got HTML response after token refresh — check client_id, "
                "client_secret, and tenant_domain in greytHR Settings"
            )

        if resp.status_code == 401:
            if _auth_retry:
                self._clear_token_cache()
                return self._request(method, path, _auth_retry=False, **kwargs)
            raise GreytHRAuthError("401 after token refresh — check credentials")

        if resp.status_code == 429:
            raise GreytHRRateLimitError("greytHR rate limit hit — back off and retry")

        if 500 <= resp.status_code < 600:
            raise GreytHRServerError(f"{resp.status_code}: {resp.text[:200]}")

        if 400 <= resp.status_code < 500:
            raise GreytHRClientError(f"{resp.status_code}: {resp.text[:200]}")

        return resp.json() if resp.content else {}

    def get(self, path: str, params: dict = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict = None, files: dict = None) -> dict:
        return self._request("POST", path, json=json, files=files)

    def put(self, path: str, json: dict = None) -> dict:
        return self._request("PUT", path, json=json)


@frappe.whitelist()
def test_connection():
    """Bench-callable smoke test: prints first employee ID from greytHR."""
    client = GreytHRClient()
    result = client.get("/employee/v2/employees", params={"page": 1, "size": 1})
    employees = result.get("data", [])
    if employees:
        # Log ID only — never log name or email (PII)
        print(f"OK — first employeeId: {employees[0].get('employeeId', 'unknown')}")
    else:
        print("OK — connection works, no employees returned")
```

#### Verification
- `bench --site hr-globexdigital execute greythr_bridge.api.client.test_connection`
  prints first employee name
- `pytest greythr_bridge/tests/test_client.py` — all 8 test cases pass
- Set `dry_run=True` in greytHR Settings, re-run — logs show `[DRY RUN]`, no real call made
- Set `dry_run=False`, use a wrong `client_secret` — see `GreytHRAuthError` in Error Log

---

### Phase 2 — Pull Employees (Week 3)

**Goal:** Every 15 minutes, employee changes in greytHR appear in Frappe HR.
New joiners, departures, transfers — all reflected automatically.

#### Pre-tasks — decisions required before any code is written

- [ ] **Decision: `fitToBeRehired`** — The separation endpoint returns a `fitToBeRehired`
  boolean. HR must decide whether to capture this in Frappe HR (useful for rehire
  screening; some teams keep it strictly internal). If yes: add `custom_fit_to_rehire`
  (Check, read-only) to Employee via Customize Form, export as fixture, and add to
  Section 3.2's custom field table before the mapper is written.
  Decision: `______________`

- [ ] **Decision: `onboardingStatus`** — greytHR already tracks `onboardingStatus` per
  employee (from the work details endpoint). Phase 7 must decide now whether Frappe HR's
  onboarding status is canonical (ignore greytHR's field) or mirrored (sync it into a
  custom field). If mirrored: add `custom_greythr_onboarding_status` (Data, read-only)
  to Employee before Phase 2 starts.
  Decision: `______________`

- [ ] **Verify `email` field** — The employee list returns an `email` field. Based on
  observed data this appears to be personal email. Confirm whether greytHR also returns a
  separate work/official email field (e.g. `workEmail`, `officialEmail`). Inspect a full
  employee record in the API docs or via a live call (keys only — no values in chat).
  The matching priority chain in task 2.5 depends on this.
  Answer: `______________`

#### Tasks
- [ ] 2.1 Create `greytHR Employee Mapping` DocType per Section 3.1
- [ ] 2.2 Add custom fields to Employee DocType via Customize Form:
       `custom_greythr_employee_id`, `custom_greythr_last_synced`,
       `custom_pushed_to_greythr`. Export as fixture.
- [ ] 2.3 Implement `mappers/employee_mapper.py`:
       `greythr_to_frappe(greythr_employee: dict) -> dict`
       Returns field dict for Frappe Employee. Never raises — returns partial dict
       with a `_mapping_errors` key listing any fields that couldn't be mapped,
       so the caller can decide whether to skip or proceed.
- [ ] 2.4 Implement `api/employee.py` with these functions:
       - `list_employees(page, size, updated_after=None)` — `/employee/v2/employees`
         (main employee list; `leavingDate` is present here — no separate call needed
         to detect separations for status sync)
       - `get_employee(employee_id)` — `/employee/v2/employees/{id}`
       - `list_employee_work_details(page, size)` — `/employee/v2/employees/work`
         (confirmation dates, probation, notice period, `onboardingStatus`)
       - `list_employee_separations(page, size)` — `/employee/v2/employees/separation`
         (leaving reason, exit interview, settlement — feeds Phase 6 letter generation)

       **Before implementing the `updated_after` filter:** verify it is supported
       by the greytHR `/employee/v2/employees` endpoint by checking the API docs at
       https://api-docs.greythr.com. If unsupported, the task must fetch all employees
       and diff locally — record the outcome here: `______________`

- [ ] 2.5 Implement `tasks/pull_employees.py`:
   - Fetch `updated_after` from `greytHR Settings.last_employee_sync`
   - Page through `/employee/v2/employees`; store current page in `resume_cursor`
     on the Sync Log so an interrupted run can resume rather than restart
   - For each employee, use this matching priority (stop at first match):
     1. Existing `greytHR Employee Mapping` by `greythr_employee_id`
     2. Frappe Employee with matching `company_email`
     3. Frappe Employee with matching `personal_email`
     4. Frappe Employee with matching `employee_number`
     5. No match → create new Frappe Employee + new mapping
   - If two Frappe employees match the same email: log to `error_summary` with
     both employee names, increment `records_skipped`, do not update either —
     HR must resolve the duplicate manually
   - If existing: update only fields that have changed (compare before saving)
   - If employee is absent from greytHR response entirely (not just "Exited"):
     set Frappe Employee status to "Left" and add a note to `last_sync_error`
     on the mapping record; do not delete the Frappe Employee
   - On `status=Failed`: send a Frappe notification to all users with
     System Manager role summarising the failure (sync type, error count, log link)
   - Update `last_employee_sync` to start-of-run timestamp on full success only
   - Write one `greytHR Sync Log` record per run with all counters populated

- [ ] 2.6 Wire scheduler in `hooks.py`:
```python
scheduler_events = {
    "cron": {
        "*/15 * * * *": ["greythr_bridge.tasks.pull_employees.run"],
    }
}
```
- [ ] 2.7 Add bench-callable for manual triggering:
       `bench --site hr-globexdigital execute greythr_bridge.tasks.pull_employees.run_now`
- [ ] 2.8 Tests — all must pass offline with mocked HTTP:
       - New employee in greytHR → Frappe Employee created + mapping created
       - Existing employee (matched by email) → only changed fields updated
       - Duplicate email across two Frappe employees → both skipped, logged
       - Employee absent from greytHR → status set to "Left", not deleted
       - Missing required field in greytHR response → `records_skipped` +1, rest continue
       - greytHR returns 500 on page 2 → run fails, `resume_cursor` saved at page 1
       - `dry_run=True` → no Frappe documents created or updated

#### Critical mapper rules
- **Matching priority:** `greythr_employee_id` mapping → `company_email` →
  `personal_email` → `employee_number`. Use the first match found. Log ambiguity;
  never guess.
- **Never overwrite Frappe-side fields with no greytHR equivalent** — `bio`, `image`,
  appraisal fields, and any `custom_` fields not owned by this bridge.
- **Status mapping:**
  - greytHR `"Active"` → Frappe `"Active"`
  - greytHR `"Resigned"` or `"Exited"` → Frappe `"Left"` + set `relieving_date`
  - Employee absent from greytHR response entirely → Frappe `"Left"` + note in
    `last_sync_error`; do not delete the Frappe record
- **Date format:** greytHR returns `dd-MM-yyyy`; Frappe expects `YYYY-MM-DD`.
  Convert in the mapper — never in the task or the client.
- **Name fields:** greytHR returns `name` (full string), `firstName`, `middleName`,
  `lastName` as separate fields. Map the decomposed fields directly (`firstName` →
  `first_name`, `lastName` → `last_name`). Do not parse the combined `name` string.
- **`email` field:** Map to `personal_email` on Frappe Employee until the pre-task
  verification confirms otherwise. If a separate work email field is discovered,
  map that to `company_email`.
- **`leavingDate` on the employee list:** The main `/employee/v2/employees` endpoint
  already includes `leavingDate`. A non-null value means the employee has separated —
  the mapper detects "Left" status here directly. The separation endpoint provides richer
  data (`leavingReason`, `exitInterviewDate`, `fitToBeRehired`) needed for letter
  generation in Phase 6 but is NOT required for status sync.
- **Salary:** Do not pull CTC into the Employee record. CTC syncs separately in Phase 3.

#### Verification
- `run_now` → all 150 employees appear in Frappe HR
- Add a test employee in greytHR UI → wait 15 min → appears in Frappe HR
- Update an employee in greytHR → change propagates on next scheduled run
- Introduce a deliberate email duplicate → both skipped, Sync Log shows `records_skipped=1`
- Check `greytHR Sync Log` — entries are complete, counters are accurate

---

### Phase 3 — Pull Salary Structures (Week 4)

**Goal:** CTC components from greytHR available in Frappe HR for use in offer letters
and salary certificates. Read-only mirror — greytHR remains the source of truth.

#### Tasks
- [ ] 3.1 Implement `api/payroll.py`: `get_salary_repository()`,
       `get_employee_salary(employee_id)`
- [ ] 3.2 Implement `mappers/salary_mapper.py`:
       Convert greytHR salary components → Frappe `Salary Component` records.
       Handle standard Indian components: Basic, HRA, Special Allowance, PF (employer
       + employee), ESI, PT, TDS, LTA, Medical. For components with no Frappe equivalent,
       create a Salary Component with `component_type="Earning"` or `"Deduction"` as
       appropriate; log the new component name so HR can review.
       Field mapping from greytHR salary repository:
       `name` → `salary_component`, `description` → `description`,
       `taxable` → `is_tax_applicable`, `type` → `component_type`.
       The `parent` and `children` fields define a tree (3 top-level nodes confirmed).
       The mapper must do a recursive walk to flatten the tree before creating Frappe
       records — do not assume a flat list.
- [ ] 3.3 Implement `tasks/pull_salary_structures.py`:
   - Ensure all salary components from greytHR exist as Frappe `Salary Component` records
   - For each employee with a salary structure in greytHR:
     - Check if a `Salary Structure Assignment` already exists with the same CTC and
       `from_date`
     - If identical: skip (idempotent)
     - If CTC or components have changed: create a **new** `Salary Structure Assignment`
       with `from_date` = today (do not modify the existing SSA — Frappe treats each SSA
       as a point-in-time revision; the history must be preserved)
     - Set `custom_pushed_to_greythr=False` on the new SSA (it came from greytHR,
       so "pushed" doesn't apply; the field marks outbound pushes in Phase 6)
   - Update `last_salary_sync` on success
   - Write one `greytHR Sync Log` record per run
- [ ] 3.4 Wire scheduler in `hooks.py`: daily at 2 AM IST (`0 20 * * *` UTC)
- [ ] 3.5 Add a "Sync Salary from greytHR" button on the Employee form (Client Script or
       Server Script — not a file-based JS unless unavoidable). Visible only to HR Manager
       and System Manager roles. Calls `pull_salary_structures.run_for_employee(employee)`
       via a whitelisted server method.

#### Verification
- Salary components appear in Frappe HR's Salary Component list
- For any employee, Salary Structure Assignment shows current CTC from greytHR
- Manually change an employee's salary in greytHR; run task; new SSA record created with
  today's `from_date`; old SSA record untouched
- Daily run logs a clean entry in Sync Log

---

### Phase 4 — Letter Templates (Week 5)

**Goal:** All letter templates exist in Frappe as `Print Format` records with correct
merge fields. No application code — this is configuration. HR must sign off on each
template before it is considered done.

#### Tasks
- [ ] 4.1 Collect current letter templates from HR (Word/PDF); get sign-off on which
       are in active use vs. draft
- [ ] 4.2 Get company letterhead image (high-res PNG, transparent background) from
       Globex Digital design team
- [ ] 4.3 Get authorised signatory signature images (one per signatory who will countersign)
- [ ] 4.4 Upload letterhead and signatures to Frappe HR File Manager;
       set correct RBAC (HR Manager read, System Manager write)
- [ ] 4.5 For each letter type, create a `Print Format` (Frappe HR → Setup → Print Format).
       All formats use Jinja syntax. See merge field map in task 4.6.

  | Letter | Bound DocType | Trigger |
  |---|---|---|
  | Offer Letter | `Job Offer` | on_submit (Phase 5) |
  | NDA | `Job Offer` | on_submit, before Offer Letter (Phase 5) |
  | Appointment Letter | `Job Offer` | on_joining_date (Phase 7) |
  | Confirmation Letter | `Employee` | Manual / probation passed |
  | Increment Letter | `Salary Structure Assignment` | on_submit (Phase 6) |
  | Promotion Letter | `Employee Promotion` | on_submit |
  | Transfer Letter | `Employee Transfer` | on_submit |
  | Experience Letter | `Employee Separation` | on_submit |
  | Relieving Letter | `Employee Separation` | on_submit |
  | Salary Certificate | `Employee` | Manual request |
  | Address Proof | `Employee` | Manual request |

  **NDA sequencing note:** The NDA must be countersigned by the company and presented
  to the candidate *before* the offer letter goes out. In the Phase 5 flow, the NDA
  signing request is sent first; only after the NDA webhook confirms completion does
  the Offer Letter signing request get triggered.

- [ ] 4.6 Merge field reference — use these Jinja variables in all templates:

  | Variable | Source field | Notes |
  |---|---|---|
  | `{{ doc.applicant_name }}` | `Job Offer.applicant_name` | |
  | `{{ doc.designation }}` | `Job Offer.designation` | |
  | `{{ doc.offer_date }}` | `Job Offer.offer_date` | Format: dd-MM-yyyy |
  | `{{ doc.date_of_joining }}` | `Job Offer.date_of_joining` | |
  | `{{ doc.salary_structure }}` | `Job Offer.salary_structure` | |
  | `{{ doc.company }}` | `Job Offer.company` | "Globex Digital Solutions Pvt Ltd" |
  | `{{ doc.custom_ctc }}` | Custom field on Job Offer | Add via Customize Form |
  | `{{ frappe.utils.formatdate(doc.offer_date, "dd MMMM yyyy") }}` | — | Human-readable dates |
  | `{{ signature_image }}` | Passed via Print Format context | Signatory image URL |

  Document all additional merge fields needed per template in a companion sheet before
  implementation — discovering a missing field mid-build requires a Customize Form
  change + fixture export.

- [ ] 4.7 **Print Format versioning:** once a template is in production, never edit it
       in place. Instead, duplicate the Print Format, increment the version in the name
       (e.g. `Offer Letter v2`), and update the template reference in Settings. Old
       versions are kept for reference — documents signed under v1 must always be
       re-generatable using v1.

- [ ] 4.8 Configure RBAC for letter generation:
       - HR Manager: can generate all letters, submit Job Offers
       - HR User: can draft letters, cannot submit
       - Employee (self-service): can request Salary Certificate and Address Proof only
       - System Manager: full access

- [ ] 4.9 Legal review of each template (one-time engagement with employment lawyer, ~₹25K)

- [ ] 4.10 Export Print Formats as fixtures:
       `bench --site hr-globexdigital export-fixtures --app greythr_bridge`

- [ ] 4.11 **DPDP note:** Offer letters and other letters contain candidate/employee PII.
       Ensure generated PDFs are stored as Frappe File attachments with `is_private=True`
       so they are not publicly accessible. Verify this in Frappe's File Manager after
       generating a test PDF.

#### Verification
- For each letter type, generate a PDF for a sample employee; compare to HR's expected output
- All merge fields populate correctly
- PDFs are stored as private attachments (not publicly accessible via URL)
- HR Manager role can generate letters; HR User cannot submit

---

### Phase 5 — E-Signature Integration (Weeks 6–7)

**Goal:** When HR submits a Job Offer, the NDA is sent for company countersignature
first, then the Offer Letter is sent to the candidate via Zoho Sign. The signed PDF
lands back in Frappe and triggers the Phase 6 push to greytHR.

#### Tasks
- [ ] 5.1 Sign up for Zoho Sign business account on India DC (in.zoho.com — see Phase 0
       pre-build verification); get API key + account ID; store in `greytHR Settings`
- [ ] 5.2 In Zoho Sign console: create webhook pointing to
       `https://hr.globexdigital.ai/api/method/greythr_bridge.webhooks.zoho_sign.callback`
       Copy the webhook HMAC secret into `greytHR Settings.zoho_sign_webhook_secret`
- [ ] 5.3 Implement `api/zoho_sign.py`:
  ```python
  def send_for_signature(
      pdf_bytes: bytes,
      document_name: str,
      signers: list[dict],   # [{"name": ..., "email": ..., "order": 1}, ...]
      metadata: dict,        # arbitrary key/value passed back in webhook payload
      expiry_days: int = 30,
  ) -> str:
      """
      Upload PDF to Zoho Sign, create signing request with ordered signers.
      Returns the Zoho Sign request_id.

      signers list determines order — order=1 signs first (company signatory),
      order=2 signs after (candidate). Both must sign for completion.
      """

  def get_signed_document(request_id: str) -> bytes:
      """Download the completed signed PDF as bytes."""

  def resend_signing_request(request_id: str) -> None:
      """Resend the signing email to pending signers on an existing request."""
  ```

- [ ] 5.4 Implement `hooks_handlers/job_offer.py`:
   - `on_offer_submitted(doc, method)`:
     1. Generate NDA PDF via Print Format
     2. Call `send_for_signature` with signers = [company signatory (order=1), candidate (order=2)]
        metadata = `{"doctype": "Job Offer", "docname": doc.name, "letter_type": "nda"}`
     3. Store NDA `request_id` in `custom_zoho_sign_nda_request_id`
     4. **Do not send the Offer Letter yet** — that is triggered by the NDA completion webhook

- [ ] 5.5 Implement `webhooks/zoho_sign.py`:
  ```python
  @frappe.whitelist(allow_guest=True)
  def callback():
      """
      Zoho Sign sends a POST here when any signing event occurs.

      Security:
        1. Verify HMAC-SHA256 signature using zoho_sign_webhook_secret
        2. Verify timestamp in payload is within 5 minutes of now (replay protection)
        3. Return 200 immediately after enqueuing — never do real work here

      Flow:
        - If letter_type == "nda" and status == "completed":
            enqueue send_offer_letter_job (queue="short")
        - If letter_type == "offer_letter" and status == "completed":
            enqueue download_and_push_job (queue="short")
        - If status == "declined":
            update Job Offer status to "Declined"; notify HR Manager
        - If status == "expired":
            update Job Offer; notify HR Manager to resend
      """
  ```

- [ ] 5.6 Add "Resend Signing Request" button on Job Offer form:
       Visible to HR Manager when `custom_zoho_sign_request_id` is set and
       `custom_signed_pdf_pushed=False`. Calls `resend_signing_request(request_id)`.
       Logs the resend action to `greytHR Sync Log`.

- [ ] 5.7 Add scheduled task to detect stalled signing requests:
       Runs daily; finds Job Offers where `custom_zoho_sign_request_id` is set,
       `custom_signed_pdf_pushed=False`, and `custom_zoho_sign_signed_at` is null
       and offer is older than 28 days. Sends a Frappe notification to HR Manager
       listing each stalled offer so they can resend or cancel.

- [ ] 5.8 Tests (all offline with mocked HTTP):
       - NDA submission triggers send_for_signature with correct signer order
       - Webhook HMAC verification: valid → process; invalid signature → return 400
       - Webhook replay: timestamp >5 min old → return 400
       - NDA completion webhook → Offer Letter sending enqueued
       - Offer Letter completion webhook → download + push enqueued
       - Signing declined → Job Offer status updated, HR notified
       - Resend button → `resend_signing_request` called with correct request_id

#### Critical
- Webhook **MUST** verify HMAC signature + timestamp — no exceptions
- Webhook **MUST** return 200 within 5 seconds — all real work goes to `queue="short"`
- If NDA or Offer signing fails/declines, the Job Offer stays at "Approved" and HR can
  resend — the system never auto-cancels a submitted offer

#### Verification
- Submit an offer; receive NDA signing email; company signatory signs;
  candidate receives Offer Letter email; candidate signs on test device;
  signed Offer Letter PDF appears as private attachment on the Job Offer
- Tamper with HMAC in test → webhook returns 400, no Frappe records changed
- Let a test request sit 28 days (or mock the date) → HR Manager receives stale offer notification

---

### Phase 6 — Push to greytHR (Week 8)

**Goal:** Once a Job Offer is fully signed, the new employee is created in greytHR and
the signed PDF lands in greytHR's Document Center automatically.

**Prerequisite:** Confirm the three push endpoints are available on the Essential plan
(task 0.0). Do not build this phase if they are not — the architecture needs redesign.

#### Tasks
- [ ] 6.1 Implement `mappers/job_offer_mapper.py`:
       `frappe_offer_to_greythr_employee(offer: JobOffer) -> dict`
       Maps Job Offer fields to greytHR's new employee payload. Raise `GreytHRClientError`
       with a clear message if any required greytHR field is missing from the offer.

- [ ] 6.2 Implement `tasks/push_new_joiner.py`:
   - Check `greytHR Employee Mapping` — if a mapping already exists for this
     `frappe_employee`, the employee was already pushed; skip and return (idempotent)
   - POST `/employee/v2/employees` with mapped payload
   - On success: store returned `greythr_employee_id` in the mapping table;
     set `custom_greythr_employee_id` and `custom_pushed_to_greythr=True` on Employee
   - On 409 Conflict (employee already exists in greytHR): fetch the existing employee's
     ID from greytHR by employee number, create the mapping record, do not re-create —
     log this as a warning, not an error
   - On failure: set `sync_status=Push Failed` and `last_sync_error` on mapping record;
     send notification to System Manager

- [ ] 6.3 Implement `tasks/push_signed_pdf.py`:
   - Check `custom_signed_pdf_pushed` on Job Offer — if True, return immediately
   - Read the signed PDF private attachment from Job Offer
   - POST `/employee/v2/employee-docs/{greythr_employee_id}/offer_letter` with PDF bytes
   - On success: set `custom_signed_pdf_pushed=True` on Job Offer
   - On failure: log to Sync Log; notify System Manager; do not retry automatically —
     the resend button in Phase 5 covers manual retry

- [ ] 6.4 Wire both tasks into the Zoho Sign webhook callback chain (Phase 5):
       After Offer Letter signing confirmed → enqueue `push_new_joiner` (queue="short")
       → on success, enqueue `push_signed_pdf` (queue="short")
       Keep these as two separate enqueued jobs so a PDF push failure doesn't undo
       the employee creation

- [ ] 6.5 Implement `hooks_handlers/salary_assignment.py`:
       `on_submit`: if `custom_pushed_to_greythr=False`, enqueue
       `push_salary_revision(salary_assignment_name)` with `queue="short"`

- [ ] 6.6 Implement `tasks/push_salary_revision.py` (called from 6.5):
       - Check `custom_pushed_to_greythr` on SSA — if True, return (idempotent)
       - POST `/payroll/v2/salary/revision/employees/{greythr_employee_id}`
       - On success: set `custom_pushed_to_greythr=True`

- [ ] 6.7 Tests (all offline):
       - New joiner push → mapping created, custom fields updated
       - Push when mapping already exists → skipped, no duplicate API call
       - greytHR returns 409 Conflict → mapping created from existing ID, logged as warning
       - PDF push → `custom_signed_pdf_pushed=True`
       - PDF push when already pushed → skipped
       - Salary revision push → `custom_pushed_to_greythr=True`

#### Verification
- Sign a test offer end-to-end; employee appears in greytHR within 30 seconds of signature
- Signed PDF downloadable from greytHR Document Center
- Run the full push a second time for the same offer → nothing changes (idempotent)
- Submit a salary revision in Frappe → appears in greytHR salary history

---

### Phase 7 — Onboarding Workflow (Weeks 9–10)

**Goal:** Configure Frappe HR's `Employee Onboarding` DocType to match the Globex Digital
onboarding flow. Wire the Appointment Letter trigger that Phase 4 defines but Phase 5/6
don't own.

**Note:** The detailed onboarding stage flow is documented in a separate memo.
Attach or link that memo here before starting this phase: `______________`

#### Tasks
- [ ] 7.1 Create `Employee Onboarding Template` records for each role type at Globex Digital
       (Engineering, Sales, Operations, Support, etc.)
- [ ] 7.2 For each template, define activities with owners (HR, IT, Admin, Manager)
       and SLA durations
- [ ] 7.3 Configure `Job Applicant` portal pages for candidate self-service
       (document upload: Aadhaar, PAN, degree certificates, bank details; form completion)
- [ ] 7.4 Wire `on_offer_accepted` event to auto-create an `Employee Onboarding` record
       from the relevant template
- [ ] 7.4b Wire Appointment Letter trigger:
       When `Employee.date_of_joining` is reached (daily scheduled check), if
       `custom_appointment_letter_generated=False`, generate the Appointment Letter PDF,
       send for signature via Zoho Sign (same multi-signer flow as Phase 5),
       and set `custom_appointment_letter_generated=True`.
- [ ] 7.5 Configure email notifications for each onboarding stage transition

#### Verification
- Walk through one full onboarding from offer → joining day with a test candidate
- Appointment Letter is sent and signed on the joining date
- Confirm tasks auto-assign to right owners; HR can see overall pipeline

---

### Phase 8 — Branding, Polish, Optional Integrations (Week 10)

#### Tasks
- [ ] 8.1 Upload Globex Digital logo to Frappe HR
- [ ] 8.2 Apply company colour scheme via Frappe theme settings
- [ ] 8.3 Customise email templates with Globex Digital branding
- [ ] 8.4 Brand the candidate-facing portal pages
- [ ] 8.5 (Optional) WhatsApp notifications via Gupshup/Twilio — onboarding nudges
- [ ] 8.6 (Optional) DigiLocker integration for Aadhaar/PAN verification
- [ ] 8.7 (Optional) BGV vendor webhook (SpringVerify / AuthBridge)

---

### Phase 9 — Security Audit + UAT (Week 11)

#### Tasks
- [ ] 9.1 Self-check against OWASP ASVS Level 1 before external audit
- [ ] 9.2 RBAC audit — verify the following role boundaries hold in a test environment:
       - HR Manager: can generate + submit offers; cannot read greytHR Settings
       - HR User: can draft; cannot submit
       - System Manager: full access
       - Employee self-service: Salary Certificate + Address Proof only
       - No role can read `client_secret`, `cached_token`, or `zoho_sign_webhook_secret`
         via the API or UI
- [ ] 9.3 DPDP Act compliance tasks:
   - [ ] 9.3a Define and document data retention policy: how long is employee PII retained
         after an employee exits? Recommended: 7 years (statutory minimum for payroll records
         under Indian labour law); delete or anonymise after that period.
   - [ ] 9.3b Implement right-to-erasure process: document the manual steps for anonymising
         a departed employee's PII in both Frappe HR and greytHR on request.
         (Full automated erasure is not in scope — document the runbook procedure.)
   - [ ] 9.3c Consent audit: confirm that greytHR's data processing agreement covers
         the transfer of employee PII to Frappe HR. If not, add a consent acknowledgement
         to the employee onboarding form.
   - [ ] 9.3d Verify all generated PDFs are stored as `is_private=True` in Frappe File;
         verify no PII appears in Frappe Error Log or greytHR Sync Log details fields.
- [ ] 9.4 Engage Indian infosec firm for external audit (~₹40K, 5-day engagement).
       Specific areas:
       - Auth flow (Frappe + custom code)
       - Zoho Sign webhook HMAC + replay protection
       - Credential storage (greytHR Settings DocType)
       - PII in logs
       - File upload validation
- [ ] 9.5 HR runs UAT with 5 realistic test cases:
       1. New hire: offer → NDA → e-sign → onboarding → joining → appointment letter
       2. Existing employee: salary increment → letter → pushed to greytHR
       3. Resignation: experience + relieving letters → pushed to greytHR
       4. Salary certificate self-service request
       5. Bulk increment letters for 20 employees from HR upload
- [ ] 9.6 Fix all audit findings; re-test; get sign-off

---

### Phase 10 — Soft Launch + Full Rollout (Weeks 12+)

#### Tasks
- [ ] 10.1 First 5 real joiners onboarded through new system; HR lead monitors each one
- [ ] 10.2 Daily check-in for first 2 weeks — fix anything that surprises
- [ ] 10.3 Full HR team migrated by end of Week 14
- [ ] 10.4 Deprecate manual letter generation in Word
- [ ] 10.5 Complete `README.md` (stubbed in Phase 0) with final operational details
- [ ] 10.6 Write `RUNBOOK.md` covering:
       - How to manually trigger a sync run
       - How to resend a Zoho Sign request
       - What to do when greytHR API is down (sync lag; no data loss)
       - How to resolve an employee duplicate detected by the mapper
       - How to handle a failed PDF push
       - How to rotate the greytHR client secret
       - How to rotate the Zoho Sign webhook secret
       - DPDP erasure request procedure (from 9.3b)

---

## 6. Testing Strategy

### 6.1 Unit tests (`pytest`)

Every module in `api/`, `mappers/`, `tasks/`, `webhooks/` has tests. Rules:

- Mock all external HTTP with the `responses` library — no real API calls in CI
- Tests run fully offline; CI has no network access to greytHR or Zoho Sign
- One test file per module (see Section 4 file map)
- Test both the happy path and every named error path in the spec

Minimum test coverage per module:

| Module | Must cover |
|---|---|
| `api/client.py` | Token fetch, cache hit, 401 retry (once only), 500 backoff, 4xx no-retry, 429 no-retry, dry_run, rate limit burst |
| `mappers/employee_mapper.py` | All status mappings, date conversion, missing optional fields, missing required fields |
| `tasks/pull_employees.py` | Create, update, skip (duplicate email), absent employee, page 2 failure + cursor saved |
| `tasks/push_new_joiner.py` | Success, already mapped (skip), 409 conflict resolution |
| `tasks/push_signed_pdf.py` | Success, already pushed (skip), missing attachment |
| `webhooks/zoho_sign.py` | Valid HMAC, invalid HMAC → 400, replay (stale timestamp) → 400, NDA completion, offer completion, decline, expiry |
| `api/zoho_sign.py` | send_for_signature (multi-signer), get_signed_document, resend |

### 6.2 PII and logging tests

Add at least one test per module that asserts no PII appears in log output:

```python
def test_pull_employees_does_not_log_pii(caplog):
    # Run pull with a mock response containing real-looking PII
    # Assert that caplog.text does not contain the candidate name, email, or mobile
    assert "Priya Sharma" not in caplog.text
    assert "priya@example.com" not in caplog.text
```

This is a DPDP compliance requirement, not just hygiene.

### 6.3 Integration tests (manual, pre-deploy)

Run these manually against the real greytHR API before each deploy to production.
Use `dry_run=True` in greytHR Settings to avoid mutating data:

- `bench execute greythr_bridge.api.client.test_connection` — confirms OAuth works
- `bench execute greythr_bridge.tasks.pull_employees.run_now` with `dry_run=True` —
  confirms pagination and mapper handle real API response shapes without error
- After a real deploy, run once with `dry_run=False` on a staging site first

### 6.4 UAT scenarios (HR runs these in Week 11)

1. **New hire (full flow):** NDA sent → company countersigns → Offer Letter sent →
   candidate e-signs → employee created in greytHR → signed PDF in greytHR Document Center
   → Onboarding record auto-created → Appointment Letter sent on joining date
2. **Salary increment:** salary revision in greytHR → pulled into Frappe → Increment Letter
   generated → e-signed → pushed to greytHR salary history
3. **Resignation:** Experience Letter + Relieving Letter generated → pushed to greytHR
4. **Salary certificate self-service:** employee requests via portal → HR approves →
   PDF generated and emailed
5. **Bulk increments:** 20 employees, salary changes in greytHR → all pull correctly →
   bulk letter generation → no data drift in Sync Log
6. **Duplicate email scenario:** introduce a deliberate duplicate → verify system skips
   both, logs clearly, HR can resolve

---

## 7. Operational Concerns

### 7.1 Logging

- Use `frappe.logger().info/warning/error` for runtime events
- Use `frappe.log_error(message, title)` for exception cases (visible in Error Log DocType)
- **NEVER log:** full employee records, candidate PII (name, email, mobile, Aadhaar, PAN),
  signed PDFs, OAuth tokens, or webhook payloads in full
- **DO log:** employee IDs, document names, operation names, HTTP status codes,
  API call durations, sync counts
- Use `utils/logging.py` wrappers — they strip PII before passing to `frappe.log_error`

### 7.2 Failure notifications

When any sync operation writes `status=Failed` to `greytHR Sync Log`, automatically send
a Frappe notification to all users with the System Manager role. Notification must include:
- Sync type and trigger (Scheduled / Manual / Webhook)
- Error count
- Direct link to the Sync Log record

Implement this as a method on `greythr_sync_log.py` called at the end of every task.
Do not rely on HR or IT to check the Sync Log manually.

### 7.3 Monitoring

- **Frappe Cloud:** uptime + basic metrics included
- **UptimeRobot (free tier):** external monitoring for:
  - `https://hr.globexdigital.ai` (the HR portal)
  - `https://hr.globexdigital.ai/api/method/greythr_bridge.webhooks.zoho_sign.callback`
    (the Zoho Sign webhook endpoint — if this is down, signed PDFs won't land)
- **Daily review** of `greytHR Sync Log` for the first month; weekly thereafter
- **Zoho Sign dashboard:** check for stuck/expired signing requests weekly

### 7.4 greytHR downtime handling

If greytHR API is unreachable:
- `pull_employees` will fail; the Sync Log will record `status=Failed`; System Manager
  is notified (per 7.2). No data is lost — the next scheduled run will catch up using
  `updated_after` from the last successful sync timestamp.
- Outbound pushes (new joiner, signed PDF) will fail and set `sync_status=Push Failed`
  on the mapping record. HR can trigger a retry via the manual resend button once
  greytHR recovers.
- Do not build automatic retry loops with `time.sleep` — use the scheduler and manual
  buttons. Tight retry loops under an outage make things worse.

### 7.5 Data retention (DPDP Act)

- Employee PII is retained for 7 years after the employee's exit date (minimum statutory
  requirement under Indian labour law for payroll records)
- After 7 years, anonymise rather than delete (to preserve audit trails):
  replace PII fields with `[ANONYMISED]`, delete attached documents
- Right-to-erasure requests are handled manually per the procedure in `RUNBOOK.md`
- Do not build automated erasure tooling in this version — document the procedure

### 7.6 Backups

- Frappe Cloud auto-backs up daily, retained 30 days
- Configure offsite backup to S3 or Backblaze B2 weekly via Frappe Cloud settings
- Quarterly restore drill: spin up a staging site from backup, verify all greytHR
  Settings fields are intact (encrypted passwords survive restore)

### 7.7 Secret rotation

When rotating greytHR `client_secret` or Zoho Sign `webhook_secret`:
1. Update the value in `greytHR Settings` (the encrypted Password field)
2. Clear `cached_token` and `token_expires_at` so the next API call fetches a fresh token
3. Update the secret in the external system (greytHR Admin / Zoho Sign console)
4. Run `test_connection` to confirm the new secret works
5. Full rotation procedure is in `RUNBOOK.md`

### 7.8 Upgrades

- Frappe HR upgrades quarterly are recommended
- Always test on a staging site first (Frappe Cloud supports multiple sites per bench)
- Pin the `hrms` version in the bench config to avoid surprise breaking changes
- Monitor [discuss.frappe.io](https://discuss.frappe.io) for breaking change announcements

---

## 8. Anti-Patterns — Things to Refuse Even If Asked

If any of the left-column things are suggested, push back with the right-column response.

| Don't do this | Do this instead |
|---|---|
| Modify Frappe HR core | Add a Custom Field via `customize_form`; export as fixture |
| Call greytHR API directly from anywhere except `client.py` | Go through `GreytHRClient` |
| Call Zoho Sign API directly from anywhere except `api/zoho_sign.py` | Go through the `zoho_sign` module |
| Store OAuth tokens or secrets in a global variable | Store in `greytHR Settings` (Password field, encrypted) |
| Put credentials in `frappe.conf` or environment variables | `greytHR Settings` DocType only |
| Silently catch exceptions | `frappe.log_error` and re-raise or surface to user |
| Skip Zoho Sign webhook HMAC verification "for now" | Verify from day one — no exceptions |
| Skip webhook timestamp check "for simplicity" | Check timestamp within 5 minutes — replay protection is not optional |
| Do synchronous work in a webhook handler | `frappe.enqueue` with `queue="short"` and return 200 immediately |
| Use `frappe.enqueue` without specifying `queue=` | Always specify: `short` for webhook-triggered, `long` for bulk sync |
| Write directly to MariaDB or use raw SQL for inserts | `frappe.get_doc` / `frappe.new_doc` (Frappe ORM only) |
| Register `on_status_change` in `hooks.py` for Employee | Use `on_update` and compare `doc.status` vs `doc.get_doc_before_save().status` |
| Create a new Salary Structure Assignment in place of an existing one | Create a new dated SSA; never modify a submitted SSA |
| Log a full employee record or webhook payload for debugging | Log the employee ID and operation name only |
| Log candidate name, email, mobile, Aadhaar, or PAN anywhere | These are PII — DPDP violation. Log IDs only. |
| "We don't need tests for this small function" | Every function that touches greytHR or Zoho Sign API has a test |
| Build a tight retry loop with `time.sleep` for API outages | Use the scheduler, Sync Log, and manual retry buttons |
| Add a JS file when a Server Script or Client Script would do | Prefer Frappe UI-managed scripts; file-based JS only when necessary |

---

## 9. Definition of Done — Per Phase

Each phase isn't done until ALL of the following are true:

1. All checkboxes in the phase are checked
2. All unit tests pass in CI (GitHub Actions)
3. Manual verification step described in the phase passes on the real site
4. `CHANGELOG.md` updated with a one-line entry describing what changed
5. `README.md` updated if there is anything operational to know
6. No PII appears in Frappe Error Log or Sync Log after running the phase's tasks
7. HR has seen and confirmed the change (for phases 4 and above)

---

## 10. How To Start A Claude Code Session For This Project

Open a session in the project directory. First message:

> Read `PLAN.md` and `CLAUDE.md`. Look at the latest entry in `CHANGELOG.md` to figure out which phase we last worked on. Tell me which phase we're in, what's complete, and what's the next concrete task. Don't start coding yet — wait for me to confirm.

Then once confirmed:

> OK, let's do task X.Y. Stick to the conventions in PLAN.md Section 2.2.

When a phase is complete:

> Phase N is verified working. Update `CHANGELOG.md`. Then summarise what's in the next phase. Don't start coding yet.

### Session etiquette

At the start of each session, say:

> I've read PLAN.md and CLAUDE.md. The last CHANGELOG entry is "<entry>". We're currently in Phase <N>. The next task is <X.Y>: <task name>. Ready to proceed when you confirm.

At the end of each session, before stopping:
- Update `CHANGELOG.md`
- Confirm all tests pass
- Commit with a message referencing phase and task number (e.g. `Phase 2.5: implement pull_employees task`)
- Note in chat what's left unfinished so the next session picks up cleanly

---

## 11. CLAUDE.md (Companion File)

The `CLAUDE.md` at the project root is the compact version loaded every session.
Keep it in sync whenever conventions change. Current content:

```markdown
# CLAUDE.md — Coding Conventions for greythr_bridge

This is a Frappe custom app (Globex Digital Solutions Pvt Ltd) that integrates
Frappe HR with greytHR Cloud.

## Hard rules
1. Never modify Frappe HR or Frappe Framework core
2. All greytHR API calls go through `greythr_bridge.api.client.GreytHRClient`
3. All Zoho Sign calls go through `greythr_bridge.api.zoho_sign`
4. All credentials live in `greytHR Settings` DocType (Password fields, encrypted at rest)
5. All sync operations are idempotent
6. All async work goes through `frappe.enqueue` — specify queue type:
   `short` (webhook-triggered), `long` (bulk sync), `default` (everything else)
7. All errors go through `frappe.log_error` — log IDs only, never PII
8. Custom DocTypes start with `greytHR`
9. Custom fields on core DocTypes start with `custom_`
10. Every function that calls greytHR or Zoho Sign has a unit test (use `responses` library)
11. All greytHR HTTP calls are rate-limited to 10 req/sec via `@rate_limited` in client
12. `on_status_change` does not exist in Frappe — use `on_update` + before/after diff

## File map
- `api/`            — HTTP wrappers: `client.py`, `employee.py`, `payroll.py`,
                      `docs.py`, `zoho_sign.py`, `exceptions.py`
- `mappers/`        — Convert between greytHR JSON and Frappe records (no I/O)
- `tasks/`          — Scheduled + enqueued jobs
- `hooks_handlers/` — Document event handlers (registered via hooks.py doc_events)
- `webhooks/`       — Incoming webhooks (Zoho Sign callback)
- `doctype/`        — greytHR Settings, greytHR Sync Log, greytHR Employee Mapping
- `fixtures/`       — Exported custom fields (auto-loaded on install)
- `utils/`          — retry, rate_limiter, idempotency, logging helpers
- `tests/`          — pytest tests with mocked HTTP (must run offline)

## Where things live
- Scheduled job wiring: `hooks.py` → `scheduler_events`
- Document event wiring: `hooks.py` → `doc_events`
- Custom field definitions: `fixtures/custom_field.json`
- All secrets: `greytHR Settings` DocType — never in source

## When in doubt
Read PLAN.md. If the answer isn't there, ask — don't guess.
```

---

## 12. Final Note

This plan is a living document. Update it when conventions change, when greytHR API
behaviour differs from what's specced, or when a phase surfaces something unexpected.
Every session should start from this document — not from memory.

The two pre-build verifications in Section 1 (greytHR Essential plan API coverage and
Zoho Sign India data residency) are the highest-priority items before any code is written.
If either verification fails, the Phase 6 architecture needs to be revisited before
Phase 1 begins.

Start with **Phase 0 — Scaffolding**. Do not jump ahead.
