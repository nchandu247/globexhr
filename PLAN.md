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

## 3. Product decisions — locked 2026-07-13 (owner: nchandu)

| # | Decision |
|---|---|
| A1 | Offer terms (designation, joining date, CTC, location, notice/probation) live in Frappe HR's **Job Offer** doctype — typed once per candidate, reused by Offer + Appointment letters. |
| A2 | Signed offer → Job Applicant auto-marked **Accepted**; Employee onboarded **manually on joining day** (no auto-conversion). |
| B3 | Employee records keep the **internal Frappe ID** (no renaming). greytHR ID lives in `employee_number` and letters print it via a dedicated placeholder. Insert-time rename hook to be retired. |
| B4 | greytHR ID format: **GDS + 3–6 digits**. Invalid ID → **validation error at save** (replaces today's silent list-hiding). |
| B5 | Employee letters (Confirmation, Experience, Relieving…) **refuse to generate until greytHR ID is filled**. |
| C6 | Candidate letters linked to the later Employee record **matched by email**. |
| D7 | Promotion, Salary Revision, Relieving **stay e-signed** — Zoho tags added to all three templates (2026-07-13). |
| D8 | Declined/Expired become real HR Letter **statuses** + **email alert** to HR (not just popup). |
| D9 | Cancelling a sent letter **recalls the Zoho request**. |
| E10 | Letterhead / company identity **editable from Settings** — no developer, no deploy. |
| E11 | Outgoing mail: **hr@globexdigital.ai** Email Account, SPF/DKIM configured (verify on site). |
| E12 | Every issued/signed letter **CCs the HR mailbox**. |
| F13 | Employees will NOT log into this app (greytHR handles employee self-service). Letters remain HR-facing. |
| F14 | **Multiple legal entities** — per-company letterhead required. |
| F15 | Ref numbering: Indian fiscal-year style **GDS/HR/2026-27/001**. |
| F16 | DPDP retention policy required — **duration TBD** (owner to confirm). |
| F17 | Catalog additions: **Bonafide/NOC, Probation Extension, Full & Final Settlement** — plus a **USA letter pack** (scope TBD). |

## 4. Roadmap (phases; each gets its own plan doc before build)

0. **Unblock deploy/go-live** — CI deps + Zoho tags in 3 templates (✅
   2026-07-13); re-register Zoho console webhook to
   `globex_hr_letters.webhooks.zoho_sign.callback`; verify Email Account;
   E2E smoke (one plain + one signature letter) on gdshr.
1. **greytHR ID handling** — B3/B4/B5: retire rename hook, validate format
   (GDS\d{3,6}) at save with error, drop the silent list filter,
   `greythr_employee_id` placeholder, generation guard on employee letters.
   Fix amend `no_copy` (stale status/zoho_request_id) while in the doctype.
2. **Job Offer integration** — A1/A2: engine reads offer terms from the
   candidate's Job Offer; signed-offer webhook sets applicant Accepted +
   ToDo for HR.
3. **Zoho unhappy paths** — D8/D9: Declined/Expired statuses, recall on
   cancel, email notifications, replay-window fail-closed, persist
   request_id before submit.
4. **Company identity from Settings + multi-entity** — E10/F14: templates
   read `company_*`/logo/signature from Settings; Company link on HR Letter;
   per-company letterhead records.
5. **Fiscal-year ref numbering** — F15: custom autoname
   GDS/HR/{fy}/{####}; decide amend-suffix handling.
6. **Catalog expansion** — F17: Bonafide/NOC, Probation Extension, F&F
   Settlement templates + fixtures; USA letter pack once scoped.
7. **Candidate→Employee continuity** — C6: email-match linkage; Employee
   "View Letters" includes candidate-era letters.
8. **Hardening** — silent-blank guards (empty Settings/comp table),
   delivery idempotency + resend button, E12 CC, tests for
   dispatch/webhook/delivery paths, retention job (F16).

## 4b. Still open (blocking their phases only)

- **USA letter pack scope** — which types (offer? employment verification?),
  which legal entity/letterhead, at-will language, USD/date formats.
- **Legal entity list** — names + letterheads for F14.
- **Retention duration** — F16.

## 5. Conventions

See `CLAUDE.md`. Highlights: Zoho only via `api/zoho_sign.py`; secrets only in
HR Letters Settings; no PII in logs (DPDP); idempotent operations; explicit
`queue=` on every enqueue; webhook HMAC + timestamp mandatory; never render
with silent blanks; never delete Employee records.
