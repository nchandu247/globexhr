# globex_hr_letters

Custom Frappe app for Globex Digital Solutions Pvt Ltd.
Standalone HR letters generation application: a UI-managed letter catalog, a
prebuilt library of professional letter templates, and Zoho Sign e-signature
workflows — running alongside Frappe HR.

## Overview

- **Letter Type catalog** — HR manages letter types entirely in the UI. 14
  professional templates ship preloaded (Offer, Appointment, Confirmation,
  Promotion, Salary Revision, Experience, Relieving, Service Certificate,
  Warning, Termination, Internship Certificate, Address Proof, Consultant
  Offer, Internship Offer).
- **HR Letter** — one record per letter issued, with a full status lifecycle
  (Draft → Generated → Sent for Signature → Signed / Issued) and audit trail.
- **Dual render engine** — shipped templates are pixel-perfect HTML rendered
  via WeasyPrint (letterhead, watermark, brand CSS); HR can add custom types
  by uploading a DOCX with `{{placeholders}}`.
- **Smart placeholder resolution** — recipient fields (Employee or Job
  Applicant) auto-fill, company/letterhead fields come from Settings, the
  compensation annexure comes from a breakup table, and anything else is
  prompted at generation time. Unresolved placeholders are a hard error —
  no silent blanks.
- **Zoho Sign** — signature letters route through Zoho Sign with HMAC-verified
  webhooks; the signed PDF is attached back automatically. A daily job nudges
  stalled signatures.

See `docs/superpowers/specs/2026-07-10-globex-hr-letters-design.md` for the
approved design, and `PLAN.md` for the build plan.

## Requirements

- Python 3.10+
- Frappe 15+ with Frappe HR (`hrms`) installed
- WeasyPrint system deps (libcairo/pango) on the bench
- Zoho Sign business account (India DC) — only for signature letters

## Installation

```bash
# On your Frappe bench
bench get-app https://github.com/nchandu247/globexhr.git
bench --site <site> install-app globex_hr_letters
bench --site <site> migrate
```

## Configuration

1. In Frappe, open **HR Letters Settings**
2. Fill in the company letterhead block (name, address, signatory name /
   designation / email, signature image)
3. For signature letters, fill the Zoho Sign block (client id, client secret,
   refresh token, webhook secret) and register the webhook URL in the Zoho
   Sign console:
   `https://<site>/api/method/globex_hr_letters.webhooks.zoho_sign.callback`
4. Health check: `bench --site <site> execute globex_hr_letters.letters.merger.health_check`

## Generating a letter

1. Open an Employee (or Job Applicant) → **Generate Letter**, or create a new
   **HR Letter** from the HR Letters workspace
2. Pick the Letter Type → **Generate** — the dialog prompts for any values the
   system can't auto-fill (e.g. work location, effective date)
3. Review the attached PDF → **Send for Signature** (Zoho Sign) or **Issue**
   (emails the PDF to the recipient)

## Running Tests

```bash
pip install -r requirements.txt
pytest globex_hr_letters/tests/ -v
```

Tests run fully offline — Frappe is mocked and no real API calls are made.

## Development

See `PLAN.md` for the build plan, `CLAUDE.md` for coding rules used in every
Claude Code session, and `CHANGELOG.md` for what has changed.
