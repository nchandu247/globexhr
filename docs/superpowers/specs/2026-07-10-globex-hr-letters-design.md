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
| 8 | Templates | Dual render engine per Letter Type: shipped library uses HTML + WeasyPrint (pixel-perfect branding, watermark, Zoho text tags); HR-authored custom types use DOCX upload with `{{placeholders}}` (LibreOffice conversion) |
| 9 | Placeholder data | Hybrid: Employee fields auto-resolve → Settings/letterhead fields → prompt HR for the rest |
| 10 | Architecture | Approach A: `Letter Type` (master) + `HR Letter` (transaction) |
| 11 | Recipient | `HR Letter` supports Employee **or** Job Applicant (dynamic link) — offer/appointment letters are issued to candidates before an Employee record exists |
| 12 | Compensation annexure | Offer/revision letters carry a CTC breakup child table on HR Letter, rendered via template `{% for %}` loop |

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
- `letters/` — `merger.py` (both render paths: docxtpl→LibreOffice for DOCX types, and
  `merge_to_pdf_via_html` HTML→WeasyPrint with `_base.html` letterhead/watermark/brand CSS
  and embedded Zoho Sign text tags), `pdf_convert.py`, `pdf_check.py`, `dispatch.py`,
  `non_signing.py` (refactored to serve the generic engine)
- `templates/letters/html/` — `_base.html`, `_styles.css`, existing letter templates
  (basis for the shipped library)
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
| render_engine | Select | HTML (WeasyPrint) / DOCX (LibreOffice). Shipped library = HTML; HR-created types default to DOCX |
| html_template | Data | template filename under `templates/letters/html/` (HTML engine only) |
| template | Attach | .docx with `{{placeholders}}` (DOCX engine only) |
| recipient_kind | Select | Employee / Job Applicant — which doctype this letter is addressed to |
| uses_compensation_table | Check | template contains a `{% for row in compensation %}` annexure |
| requires_signature | Check | on → Zoho Sign flow; off → plain issue with signature image |
| signatory_source | Select | From Settings / Custom. Custom reveals name, designation and signature-image fields on the Letter Type itself |
| description | Small Text | purpose and usage guidance |
| is_active | Check | inactive types hidden from pickers |

### HR Letter (transaction, submittable)
| Field | Type | Notes |
|---|---|---|
| recipient_type | Select | Employee / Job Applicant (defaulted from Letter Type.recipient_kind) |
| recipient | Dynamic Link → recipient_type | required; candidate letters link Job Applicant |
| letter_type | Link → Letter Type | required |
| compensation | Table (child: HR Letter Compensation Row) | component, monthly_amount, annual_amount; shown only when Letter Type.uses_compensation_table |
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
  1. Load Letter Type template (HTML file or attached .docx per render_engine)
  2. Scan placeholders (Jinja2 meta for HTML; docxtpl
     get_undeclared_template_variables for DOCX)
  3. Resolve in order: recipient doc fields (Employee or Job Applicant)
     → HR Letters Settings/letterhead fields
     → compensation child table (when Letter Type.uses_compensation_table)
  4. Unresolved placeholders → dialog prompts HR; values stored in filled_values
  5. Render:
     - HTML engine → WeasyPrint PDF (letterhead/watermark/CSS from _base.html;
       Zoho text tags embedded when requires_signature)
     - DOCX engine → docxtpl → LibreOffice PDF
     → attach PDF → status = Generated
  6a. requires_signature: dispatch via api/zoho_sign.py (frappe.enqueue, queue="default")
      → status = Sent for Signature → Zoho webhook callback → status = Signed,
      signed PDF attached
  6b. else: stamp signature image → status = Issued
```

Rules:
- Placeholder namespaces: bare recipient fieldnames (e.g. `{{employee_name}}`,
  `{{applicant_name}}`, `{{designation}}`) resolve from the linked Employee or
  Job Applicant doc; `{{company_*}}` resolves from HR Letters Settings;
  `compensation` resolves from the child table; anything else is prompted.
- Zoho signature-field placement: HTML templates embed invisible text tags
  (`{{S:R1*}}` etc.) so Zoho auto-creates fields. DOCX signature-required custom
  types must include the same text tags in the document (documented for HR); the
  generate step warns if a signature-required DOCX template contains no tag.
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

Shipped as fixtures (Letter Type records) plus HTML templates under
`templates/letters/html/` (extending `_base.html` — letterhead, watermark, brand CSS,
footer), written to standard Indian corporate letter conventions (letterhead, reference
number, date, subject, salutation, body, signatory block):

| # | Letter Type | Category | Recipient | Signature | CTC table |
|---|---|---|---|---|---|
| 1 | Offer Letter | Onboarding | Job Applicant | Zoho Sign | yes |
| 2 | Appointment Letter | Onboarding | Job Applicant | Zoho Sign | yes |
| 3 | Confirmation Letter | Employment | Employee | plain | — |
| 4 | Promotion Letter | Employment | Employee | Zoho Sign | — |
| 5 | Salary Revision Letter | Compensation | Employee | Zoho Sign | yes |
| 6 | Experience Letter | Exit | Employee | plain | — |
| 7 | Relieving Letter | Exit | Employee | Zoho Sign | — |
| 8 | Service Certificate | Certificate | Employee | plain | — |
| 9 | Warning Letter | Disciplinary | Employee | plain | — |
| 10 | Termination Letter | Exit | Employee | Zoho Sign | — |
| 11 | Internship Certificate | Certificate | Employee | plain | — |
| 12 | Address Proof Letter | Certificate | Employee | plain | — |

Offer/Appointment/Salary Revision templates include a compensation annexure page
(component-wise monthly + annual breakup with gross and CTC totals) rendered from the
HR Letter compensation child table.

Shipped templates are HTML (pixel-perfect output; edited by developers). HR creates or
customizes additional letter types via DOCX upload entirely in the UI.

## 7. Workspace and UX

- Rename the existing `greythr` module workspace to **HR Letters** (per-module-folder
  convention required in Frappe v16 — not a fixture, to avoid the orphan-Workspace purge).
- Shortcuts: New HR Letter, HR Letters list, Letter Types, HR Letters Settings.
- Employee form button "Generate Letter" (Client Script) → opens new HR Letter with
  recipient prefilled. Same button on Job Applicant form for candidate letters
  (offer/appointment).

## 8. Testing

- Framework unchanged: pytest + `responses`, fully offline, existing CI workflow.
- Surviving tests: Zoho Sign client, webhook (HMAC/timestamp), letters render/convert.
- New tests: placeholder scanning + resolution order (recipient → Settings →
  compensation → prompt), hard-error on unresolved placeholder, HR Letter status
  lifecycle, signature vs plain dispatch paths, both render engines (HTML/WeasyPrint and
  DOCX/LibreOffice), Job Applicant recipient resolution, compensation-table rendering
  with totals, missing-Zoho-tag warning for signature-required DOCX types,
  stalled-signings against HR Letter.
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
