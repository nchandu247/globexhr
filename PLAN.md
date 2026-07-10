# globex_hr_letters — Build Plan

> **How to use this file:** When starting any Claude Code session, read
> `PLAN.md` and `CLAUDE.md` first, then check the last `CHANGELOG.md` entry.
> The approved design lives at
> `docs/superpowers/specs/2026-07-10-globex-hr-letters-design.md` — that spec
> is the source of truth for architecture decisions.

---

## 0. Project Identity

**Name:** `globex_hr_letters`
**Type:** Custom Frappe app installed alongside Frappe HR on Frappe Cloud
**Purpose:** Standalone HR letters generation application — UI-managed letter
catalog, prebuilt professional template library, Zoho Sign e-signature flow.
**History:** This repo began life as `greythr_bridge` (Frappe HR ↔ greytHR
sync). On 2026-07-10 the project pivoted: all greytHR integration was removed
and the letters pipeline became the whole product. Old phase plans and specs
under `docs/superpowers/specs/2026-05-*` are historical context only.

## 1. Architecture (as built)

- **Letter Type** (master) + **HR Letter** (submittable transaction with
  dynamic recipient link: Employee or Job Applicant) + **HR Letter
  Compensation Row** (child) + **HR Letters Settings** (single: Zoho creds,
  company letterhead, signatory, thresholds).
- **Engine** (`letters/engine.py`): scan template placeholders → resolve
  (recipient doc → Settings → compensation table → HR-filled values) → hard
  error on unresolved → render → attach → dispatch.
- **Render engines:** HTML + WeasyPrint for the shipped library (pixel-perfect
  letterhead/watermark, Zoho text tags embedded); DOCX + docxtpl for
  HR-authored custom types (signature DOCX goes to Zoho, which converts;
  plain DOCX needs LibreOffice).
- **Lifecycle:** Draft → Generate → Generated → Send for Signature (Zoho,
  webhook flips to Signed, signed PDF attached) or Issue (emailed, Issued).
  Cancel + amend for corrections after submit.
- **Shipped catalog:** 14 Letter Types in `fixtures/letter_type.json` wired to
  templates in `templates/letters/html/`.

## 2. Status — done

- greytHR integration fully removed; app renamed `globex_hr_letters`,
  module `HR Letters`.
- Doctypes, engine, dual render, webhook (HMAC + replay window), stalled
  signings, workspace, Employee/Job Applicant "Generate Letter" buttons.
- 14-template HTML library; compensation annexure driven by the child table.
- 71 offline tests green (engine, Zoho client, webhook, workspace guards,
  permissions, placeholders setup).

## 3. Next steps (in order)

1. **Install on the test site** — uninstall `greythr_bridge`, install
   `globex_hr_letters`, migrate; verify fixtures loaded (14 Letter Types),
   workspace renders, health_check passes.
2. **End-to-end smoke on site** — generate one plain letter (Service
   Certificate) and one signature letter (Offer with compensation rows)
   against a test Employee/Job Applicant; verify PDF quality, prompts,
   attachments, Zoho round-trip.
3. **Letterhead from Settings** — templates currently hardcode the Globex
   letterhead in `_base.html`; optionally switch to `company_*` placeholders
   once real values are in Settings.
4. **Template polish round** — HR reviews all 14 rendered PDFs; wording and
   layout tweaks.
5. **Production readiness** — Zoho production credentials, webhook registered,
   HR role permissions reviewed, go-live.

## 4. Deferred (explicitly out of scope for v1)

- Auto-trigger hooks (e.g. Offer Letter on Job Offer submit) — thin
  `doc_events` handlers creating HR Letters via the same engine.
- Bulk letter generation (multiple employees at once).
- Direct email delivery preferences / templates per letter type.
- Any external HR/payroll system integration.

## 5. Conventions

See `CLAUDE.md`. Highlights: Zoho only via `api/zoho_sign.py`; secrets only in
HR Letters Settings; no PII in logs (DPDP); idempotent operations; explicit
`queue=` on every enqueue; webhook HMAC + timestamp mandatory; never render
with silent blanks; never delete Employee records.
