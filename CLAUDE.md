# CLAUDE.md — Coding Conventions for globex_hr_letters

> Read this file at the start of every Claude Code session. Read `PLAN.md` for full context. Check `CHANGELOG.md` to see what's last been done.

This is a Frappe custom app (Globex Digital Solutions Pvt Ltd) — a standalone **HR letters generation application** running alongside Frappe HR on Frappe Cloud. HR manages a Letter Type catalog, generates letters for Employees or Job Applicants (candidates), and routes signature letters through Zoho Sign. There is **no external HR/payroll integration** — Employee data is entered manually in Frappe HR.

Design source of truth: `docs/superpowers/specs/2026-07-10-globex-hr-letters-design.md`.

---

## Hard rules — never break these

1. **Never modify Frappe HR or Frappe Framework core.** All extensions live in `globex_hr_letters`. If a customization seems to need core changes, stop and use a hook/fixture/custom field instead.
2. **All Zoho Sign API calls go through `globex_hr_letters.api.zoho_sign`.** Never call the Zoho Sign REST API directly from tasks, hooks, webhooks, or the engine.
3. **All credentials live in the `HR Letters Settings` single DocType** with `Password` fields (encrypted at rest). Never hardcode secrets in source. Never read secrets from `frappe.conf` or environment variables.
4. **All letter operations are idempotent.** The HR Letter document name is the idempotency key. `dispatch_signature` skips when `zoho_request_id` is already set — keep that pattern.
5. **All async work goes through `frappe.enqueue` with the correct queue type.**
   - `queue="short"` — webhook-triggered jobs (must start within seconds)
   - `queue="default"` — signature dispatch, email delivery, everything else
   HTTP webhook handlers must return within 5 seconds. Never block a webhook with synchronous work.
6. **All errors go through `frappe.log_error(message, title)`** (or `utils/logging.log_error`). Never use `print()` or bare `pass` on exceptions. Log document names, IDs, and operation names only — never recipient names, emails, mobile numbers, placeholder values, PDFs, tokens, or webhook payloads. DPDP Act compliance requirement.
7. **Never render a letter with silent blanks.** An unresolved placeholder is a hard error listing the missing names. The prompt dialog exists for exactly this.
8. **Custom DocTypes live in the `HR Letters` module** (`Letter Type`, `HR Letter`, `HR Letter Compensation Row`, `HR Letters Settings`).
9. **Every function that calls Zoho Sign has a unit test.** Use the `responses` library to mock HTTP. Tests must run offline in CI (`frappe` is mocked in `tests/conftest.py`).
10. **Every commit batch updates `CHANGELOG.md`.**
11. **Zoho Sign webhook security is not negotiable:** HMAC-SHA256 verification + 5-minute timestamp replay window, from day one, no "for now" exceptions.
12. **`on_status_change` does not exist in Frappe.** To react to a status change, use `on_update` and compare `doc.status` vs `doc.get_doc_before_save().status`.
13. **Never delete Employee records** or bulk-modify them destructively — at any project stage. Non-destructive mitigations only.

---

## File map

```
api/             — zoho_sign.py (all Zoho Sign HTTP), exceptions.
letters/         — engine.py (placeholder resolution + generation flow),
                   merger.py (render primitives: HTML/WeasyPrint + DOCX/docxtpl),
                   delivery.py (attach + email), pdf_convert.py, pdf_check.py.
hr_letters/      — module folder: doctype/ (Letter Type, HR Letter, Compensation
                   Row, Settings) and workspace/ (v16 per-module convention).
hooks_handlers/  — Document event handlers (Employee naming). NOT hooks.py.
webhooks/        — Zoho Sign callback. @frappe.whitelist(allow_guest=True).
tasks/           — stalled_signings (daily cron), setup_letter_placeholders.
templates/letters/html/ — shipped HTML template library (_base.html + letters).
fixtures/        — letter_type.json (shipped catalog), client_script.json.
utils/           — retry, idempotency, logging wrappers, permissions.
tests/           — pytest, offline, frappe mocked in conftest.py.
```

## Where things wire up

| What | Where |
|---|---|
| Scheduled jobs | `hooks.py` → `scheduler_events` |
| Document event handlers | `hooks.py` → `doc_events` |
| Shipped Letter Types | `fixtures/letter_type.json` (auto-loaded) |
| Generate Letter buttons | `fixtures/client_script.json` (Employee, Job Applicant) |
| HR Letter form buttons | `hr_letters/doctype/hr_letter/hr_letter.js` |
| Webhook URL | `/api/method/globex_hr_letters.webhooks.zoho_sign.callback` |
| Secrets + letterhead | `HR Letters Settings` DocType |
| App version | `globex_hr_letters/__init__.py` → `__version__` |

## The letter flow (memorise this)

```
HR Letter (Draft) → [Generate] → placeholders resolved:
  recipient doc → Settings → compensation table → prompt dialog → hard error
  → render (HTML/WeasyPrint or DOCX/docxtpl) → PDF attached → Generated
  → requires_signature: [Send for Signature] → Zoho Sign → webhook → Signed
  → else: [Issue] → emailed to recipient → Issued
```

- HTML templates live in `templates/letters/html/`, extend `_base.html`, and embed Zoho text tags (`{{S:R1*}}`/`{{S:R2*}}`) inside `{% raw %}` for signature letters.
- Signature DOCX letters upload the rendered DOCX to Zoho (Zoho converts to PDF) — no LibreOffice needed. Plain DOCX letters require LibreOffice on the bench.
- Offer/Appointment letters address **Job Applicant** (candidates are not Employees yet).

## Anti-patterns — refuse these even if asked

| Don't do this | Do this instead |
|---|---|
| Call Zoho Sign API directly | Go through `api/zoho_sign.py` |
| Put credentials in `frappe.conf` / env vars | `HR Letters Settings` (Password fields) |
| Silently catch exceptions | `frappe.log_error` and re-raise or surface |
| Skip webhook HMAC / timestamp check | Both mandatory, no exceptions |
| Synchronous work in webhook handler | `frappe.enqueue(queue="short")`, return 200 |
| `frappe.enqueue` without `queue=` | Always specify |
| Raw SQL inserts | `frappe.get_doc` / `frappe.new_doc` (ORM) |
| Render with a blank placeholder | Hard error + prompt dialog |
| Hardcode a letter type in code | Add a Letter Type record + template |
| Log recipient PII / placeholder values | Document names + operation names only |
| Skip tests for Zoho-touching code | `responses`-mocked test, offline |
| Delete Employee records | Never — hard rule |

## Useful bench commands

```bash
# Health check for the render pipeline
bench --site hr-globexdigital execute globex_hr_letters.letters.merger.health_check

# Run all app tests (CI runs plain pytest — frappe is mocked)
pytest globex_hr_letters/tests/ -v

# Migrate after pulling new code
bench --site hr-globexdigital migrate

# Export fixtures after editing Letter Types / Client Scripts via UI
bench --site hr-globexdigital export-fixtures --app globex_hr_letters
```

## When in doubt

- **Read `PLAN.md`** and the design spec. If they don't answer it, ask — don't guess.
- Frappe-framework questions: search https://docs.frappe.io and https://discuss.frappe.io first.
- If suggesting a deviation from these conventions, flag it explicitly.

## Session etiquette

At the start of each session: state the last CHANGELOG entry and the next task, and wait for confirmation. At the end: update `CHANGELOG.md`, make sure all tests pass, commit with a descriptive message, note what's unfinished.
