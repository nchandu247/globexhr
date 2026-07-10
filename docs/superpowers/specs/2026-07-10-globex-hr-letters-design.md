# Design: globex_hr_letters — Standalone HR Letters Generation App

**Date:** 2026-07-10
**Status:** Approved by user (brainstorming session)
**Supersedes:** greytHR integration scope of `greythr_bridge` (PLAN.md)

## 1. Summary

Transform the `greythr_bridge` Frappe app, in place, into **`globex_hr_letters`** — an
independent HR letters generation application. All greytHR Cloud integration is removed.
The app keeps the existing letters pipeline (docxtpl DOCX merge → LibreOffice → PDF) and
the Zoho Sign e-signature flow, and replaces hardcoded per-document letter handlers with a
generic, UI-managed letter catalog plus a shipped library of professional standard templates.

## 2. Decisions (from brainstorming)

| # | Topic | Decision |
|---|-------|----------|
| 1 | Platform | Remains a Frappe app running alongside Frappe HR (`required_apps = ["frappe/hrms"]`) |
| 2 | Repo | Transform this repo in place; keep git history |
| 3 | Deployment | Site is not live (test data only) — no data-migration patches needed; fresh install |
| 4 | E-signature | Keep Zoho Sign flow (module, webhook, stalled-signings task) |
| 5 | Employee data | Manual entry in Frappe HR; no external sync |
| 6 | App identity | Full rename: app `globex_hr_letters`, title "Globex HR Letters", module `HR Letters` |
| 7 | Letter catalog | Generic `Letter Type` doctype — HR adds letter types via UI, no code |
| 8 | Templates | DOCX upload with `{{placeholders}}`; app ships a prebuilt professional library |
| 9 | Placeholder data | Hybrid: Employee fields auto-resolve → Settings/letterhead fields → prompt HR for the rest |
| 10 | Architecture | Approach A: `Letter Type` (master) + `HR Letter` (transaction) |

## 3. What is removed vs kept

### Removed (greytHR coupling)
- `api/client.py` (`GreytHRClient`), `api/employee.py`, `api/payroll.py`, greytHR-specific exceptions
- `mappers/` — `employee_mapper.py`, `salary_mapper.py`
- `tasks/pull_employees.py`, `tasks/pull_salary_structures.py`, `tasks/rename_employees_to_greythr_id.py`
- `utils/sync_diagnostics.py`, `utils/data_quality.py`, `utils/rate_limiter.py`
- `custom_greythr_*` custom fields from `fixtures/custom_field.json`
- greytHR credentials/fields from the Settings doctype
- Scheduler entries for `pull_employees` and `pull_salary_structures`
- All greytHR-related tests (`test_client.py`, `test_pull_employees.py`, `test_mappers.py`,
  `test_sync_diagnostics.py`, `test_data_quality.py`, `test_rename_employees.py`, `test_salary_mapper.py`)
- Hardcoded letter trigger handlers in `hooks_handlers/` (`job_offer.py`,
  `salary_structure_assignment.py`, `employee_separation.py`) and their `doc_events` —
  replaced by the generic engine. Auto-triggers can return later as thin hooks that create
  an `HR Letter` through the same engine.
- `NOTES_greythr_api.md`

### Kept and renamed (app `greythr_bridge` → `globex_hr_letters`, module `greytHR` → `HR Letters`)
- `letters/` — `merger.py` (docxtpl), `pdf_convert.py` (LibreOffice), `pdf_check.py`,
  `dispatch.py`, `non_signing.py` (refactored to serve the generic engine)
- `api/zoho_sign.py` and `webhooks/zoho_sign.py` — HMAC verification and 5-minute
  timestamp replay protection stay mandatory
- `tasks/stalled_signings.py` — repointed at `HR Letter` status
- `utils/` — `retry.py`, `idempotency.py`, `logging.py`, `permissions.py` (kept: the
  malformed-employee_number list filter is still a useful guard with manual data entry)
- Settings doctype → **`HR Letters Settings`** (single): Zoho Sign credentials (Password
  fields), company letterhead (logo, registered address, signatory name, signatory
  designation, signature image), default sender email
- `templates/letters/` assets (letterhead images, `hr_signature.png`)
- Employee `before_insert` naming hook — generalized: name Employee by `employee_number`
  when present, else default series (no greytHR reference)
- pytest + `responses` offline test infrastructure and CI workflow

### Documentation
- `CLAUDE.md` and `PLAN.md` rewritten for the new scope. Surviving rules: all Zoho Sign
  calls via `api/zoho_sign.py`; all secrets in the Settings single doctype (never
  `frappe.conf`/env); `frappe.log_error` with no PII (DPDP); idempotent operations keyed by
  document name; `frappe.enqueue` always with explicit `queue=`; every function touching an
  external API has an offline test; webhook handlers return within 5 seconds;
  no `on_status_change` (does not exist in Frappe); never modify Frappe core.
- Naming conventions change: custom DocTypes no longer use the `greytHR` prefix; they live
  in the `HR Letters` module. Custom fields on core doctypes keep the `custom_` prefix.
- `CHANGELOG.md` continues.

## 4. Data model

### Letter Type (master, HR-manageable)
| Field | Type | Notes |
|---|---|---|
| letter_type_name | Data (unique) | e.g. "Offer Letter" |
| category | Select | Onboarding / Employment / Compensation / Exit / Disciplinary / Certificate |
| template | Attach | .docx with `{{placeholders}}` |
| requires_signature | Check | on → Zoho Sign flow; off → plain issue with signature image |
| signatory_source | Select | From Settings / Custom. Custom reveals name, designation and signature-image fields on the Letter Type itself |
| description | Small Text | purpose and usage guidance |
| is_active | Check | inactive types hidden from pickers |

### HR Letter (transaction, submittable)
| Field | Type | Notes |
|---|---|---|
| employee | Link → Employee | required |
| letter_type | Link → Letter Type | required |
| status | Select | Draft / Generated / Sent for Signature / Signed / Issued / Cancelled |
| letter_date | Date | date printed on the letter |
| filled_values | JSON | prompt-collected placeholder values (audit; not logged) |
| generated_pdf | Attach | output PDF |
| zoho_request_id | Data | set when signature flow used |
| issued_on / issued_by | Datetime / Link → User | audit |

- Naming series: `HR-LTR-YYYY-####`.
- Idempotency key: the HR Letter document name (consistent with existing convention).

## 5. Generation flow

```
HR Letter (Draft) → [Generate]
  1. Load Letter Type's .docx template
  2. Scan placeholders (docxtpl get_undeclared_template_variables)
  3. Resolve in order: Employee fields → HR Letters Settings/letterhead fields
  4. Unresolved placeholders → dialog prompts HR; values stored in filled_values
  5. Render (docxtpl) → convert (LibreOffice) → attach PDF → status = Generated
  6a. requires_signature: dispatch via api/zoho_sign.py (frappe.enqueue, queue="default")
      → status = Sent for Signature → Zoho webhook callback → status = Signed,
      signed PDF attached
  6b. else: stamp signature image → status = Issued
```

Rules:
- Placeholder namespaces: bare Employee fieldnames (e.g. `{{employee_name}}`,
  `{{designation}}`) resolve from the Employee doc; `{{company_*}}` resolves from
  HR Letters Settings; anything else is prompted.
- A placeholder that is neither resolvable nor supplied is a **hard error** — never render
  with silent blanks.
- Regeneration allowed only in Draft/Generated. After Sent for Signature, use Frappe-native
  cancel + amend.
- Errors go to `frappe.log_error` (IDs and operation names only — no placeholder values,
  no PII). Status is left unchanged and the user sees the error.
- `stalled_signings` cron nudges letters stuck in Sent for Signature beyond a threshold
  (default 3 days, configurable in Settings).
- Zoho webhook: unchanged security posture — HMAC signature verification, 5-minute
  timestamp window, `frappe.enqueue(queue="short")`, immediate 200 response.

## 6. Prebuilt template library

Shipped as fixtures (Letter Type records) plus DOCX files under `templates/letters/`,
written to standard Indian corporate letter conventions (letterhead, reference number,
date, subject, salutation, body, signatory block):

| # | Letter Type | Category | Signature |
|---|---|---|---|
| 1 | Offer Letter | Onboarding | Zoho Sign |
| 2 | Appointment Letter | Onboarding | Zoho Sign |
| 3 | Confirmation Letter | Employment | plain |
| 4 | Promotion Letter | Employment | Zoho Sign |
| 5 | Salary Revision Letter | Compensation | Zoho Sign |
| 6 | Experience Letter | Exit | plain |
| 7 | Relieving Letter | Exit | Zoho Sign |
| 8 | Service Certificate | Certificate | plain |
| 9 | Warning Letter | Disciplinary | plain |
| 10 | Termination Letter | Exit | Zoho Sign |
| 11 | Internship Certificate | Certificate | plain |
| 12 | Address Proof Letter | Certificate | plain |

HR can edit any shipped template (download DOCX, modify, re-upload) or create new
Letter Types entirely via the UI.

## 7. Workspace and UX

- Rename the existing `greythr` module workspace to **HR Letters** (per-module-folder
  convention required in Frappe v16 — not a fixture, to avoid the orphan-Workspace purge).
- Shortcuts: New HR Letter, HR Letters list, Letter Types, HR Letters Settings.
- Employee form button "Generate Letter" (Client Script) → opens new HR Letter with
  employee prefilled.

## 8. Testing

- Framework unchanged: pytest + `responses`, fully offline, existing CI workflow.
- Surviving tests: Zoho Sign client, webhook (HMAC/timestamp), letters render/convert.
- New tests: placeholder scanning + resolution order (Employee → Settings → prompt),
  hard-error on unresolved placeholder, HR Letter status lifecycle, signature vs plain
  dispatch paths, stalled-signings against HR Letter.
- Deleted: all greytHR API/mapper/sync tests.

## 9. Migration / rollout

Site is not live. Rollout = uninstall `greythr_bridge` from the test site, install
`globex_hr_letters` fresh. No data patches. Existing test Employee records are untouched
(hard rule: never delete Employee records at any stage).

## 10. Out of scope (explicitly deferred)

- Auto-trigger hooks (e.g. generate Offer Letter on Job Offer submit) — the engine
  supports adding these later as thin `doc_events` handlers creating HR Letter records.
- Bulk letter generation (multiple employees at once).
- Email delivery of issued letters to employees.
- Any external HR/payroll system integration.
