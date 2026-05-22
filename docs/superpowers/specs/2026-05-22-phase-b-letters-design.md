# Phase B — Seven Letter Templates — Design Spec

**Date:** 2026-05-22
**Author:** Chandu + Claude (Opus 4.7)
**Status:** Draft — awaiting user review
**Scope:** Build all 7 remaining letter types (Consultant Offer, Intern Offer, Increment, Promotion, Experience, Relieving, Service Certificate) on the HTML+CSS+WeasyPrint infrastructure proven in Phase A. Atomic deploy.
**Builds on:** [2026-05-21-weasyprint-offer-letter-design.md](2026-05-21-weasyprint-offer-letter-design.md)

---

## 1. Goals

Ship all 7 letter types in a single coordinated deploy:

- ✅ Reuse Phase A's HTML+CSS+WeasyPrint pipeline — no infrastructure rebuilds
- ✅ Each letter has its own HTML template, context builder, and handler
- ✅ Auto-trigger letters that have clear submit events; manual trigger letters that need HR judgment
- ✅ Smart e-sign split: offer-type letters via Zoho Sign (need countersign), other letters as PDF-only (HR signature embedded)
- ✅ All 7 source DOCX templates remain in `templates/` as reference but never rendered — HTML supersedes
- ✅ Phase A's offer_letter.html stays untouched

**Non-goals:**

- Removing the DOCX-rendering code entirely (separate cleanup commit)
- Multi-language support
- HR-editable templates via Frappe Print Format DocType
- Greytrh push-back of signed/generated PDFs (Phase 6)
- Bulk letter generation (single-record-at-a-time only)

---

## 2. Letter inventory

| # | Letter | DocType | Trigger | E-sign | Status update |
|---|---|---|---|---|---|
| 1 | Consultant Offer Letter | Job Offer (`custom_offer_type` = Consultant) | Auto on submit | Yes (Zoho) | status → Accepted on webhook |
| 2 | Intern Offer Letter | Job Offer (`custom_offer_type` = Intern) | Auto on submit | Yes (Zoho) | status → Accepted on webhook |
| 3 | Increment Letter | Salary Structure Assignment | Auto on submit | No — PDF only | none |
| 4 | Promotion Letter | Employee | Manual button | No — PDF only | none |
| 5 | Experience Letter | Employee Separation (`custom_send_experience_letter` checked) | Auto on submit | No — PDF only | none |
| 6 | Relieving Letter | Employee Separation (`custom_send_relieving_letter` checked) | Auto on submit | No — PDF only | none |
| 7 | Service Certificate | Employee | Manual button | No — PDF only | none |

---

## 3. Architecture

```
greythr_bridge/
├── letters/
│   ├── merger.py                            [+ 7 new context builders + merge_to_pdf_via_html stays]
│   ├── non_signing.py                       [NEW: generate + attach + email helper for PDF-only letters]
│   └── dispatch.py                          [NEW: picks template based on Job Offer type]
├── templates/letters/html/
│   ├── _base.html                           [UNCHANGED — Phase A]
│   ├── _styles.css                          [+ a few new classes for non-signing letters: hr-sig-image]
│   ├── img/
│   │   ├── logo.png                         [Phase A]
│   │   └── hr_signature.png                 [NEW: user provides — see Section 9]
│   ├── offer_letter.html                    [UNCHANGED — Phase A]
│   ├── consultant_offer_letter.html         [NEW]
│   ├── intern_offer_letter.html             [NEW]
│   ├── increment_letter.html                [NEW]
│   ├── promotion_letter.html                [NEW]
│   ├── experience_letter.html               [NEW]
│   ├── relieving_letter.html                [NEW]
│   └── service_certificate.html             [NEW]
├── hooks_handlers/
│   ├── job_offer.py                         [MODIFIED: dispatcher picks Full-time/Consultant/Intern]
│   ├── salary_structure_assignment.py       [NEW]
│   ├── employee_separation.py               [NEW]
│   └── employee.py                          [NEW: manual button hooks for Promotion + Service Cert]
├── hooks.py                                 [MODIFIED: register new doc_events — see below]
└── fixtures/
    ├── custom_field.json                    [+ new fields: see Section 5]
    └── client_script.json                   [NEW: Promotion + Service Cert buttons]
```

### `hooks.py` doc_events additions (explicit)

```python
doc_events = {
    "Job Offer": {
        "on_submit": "greythr_bridge.hooks_handlers.job_offer.on_offer_submitted",
    },
    # NEW for Phase B:
    "Salary Structure Assignment": {
        "on_submit": "greythr_bridge.hooks_handlers.salary_structure_assignment.on_ssa_submitted",
    },
    "Employee Separation": {
        "on_submit": "greythr_bridge.hooks_handlers.employee_separation.on_separation_submitted",
    },
}
```

(No `Employee` doc_event needed — Promotion + Service Cert are manual buttons, not on_submit.)

**Reuse principle:** `build_offer_context()` from Phase A stays. New context builders share helpers (`fmt_inr`, `fmt_date`, `_get_applicant_email`).

**Independence principle (Gap 11 fix):** `build_consultant_offer_context()` is INDEPENDENT — not derived from `build_offer_context()` — because consultants have different fields (no PF/ESI/Annexure A salary table). Same for Intern. Both new builders share the formatting helpers but assemble their own minimal context dict.

---

## 4. Detailed per-letter design

### 4.1 Consultant Offer Letter

- **Trigger:** Job Offer `on_submit` → handler branches on `custom_offer_type == "Consultant"`
- **Context builder:** `build_consultant_offer_context(doc)` in merger.py — INDEPENDENT of `build_offer_context` (per Gap 11 fix). Builds its own minimal context: `candidate_name`, `title`, `designation`, `engagement_start_date` (reuses `custom_date_of_joining` field — semantically "start date" for consultants), `engagement_duration_months`, `professional_fees_monthly`, `work_location`, `gst_clause`. Does NOT include PF/ESI/Annexure A salary keys.
- **DOJ field reuse:** `custom_date_of_joining` is still mandatory on Job Offer; consultants read it as "Engagement Start Date" in the letter content. No field change needed.
- **HTML template:** `consultant_offer_letter.html` — same structure as Phase A but content reflects consultancy relationship:
  - No "employment" language — uses "engagement"
  - No salary table (Annexure A); instead a "Professional Fees" section with monthly retainer
  - GST clause (consultant invoices with GST)
  - Termination by either party with 30-day notice (not "60 days notice period")
  - No Benefits / Leave sections
- **Zoho Sign:** Yes — `merge_to_pdf_via_html("consultant_offer_letter.html", ...)` → upload to Zoho with `{{S:R1*}}` and `{{S:R2*}}` tags

### 4.2 Intern Offer Letter

- **Trigger:** Same as Consultant — Job Offer `on_submit` with `custom_offer_type == "Intern"`
- **Context builder:** `build_intern_offer_context(doc)` — INDEPENDENT (per Gap 11). Minimal context: `candidate_name`, `title`, `designation` (intern role), `internship_start_date` (reuses `custom_date_of_joining`), `internship_duration_months`, `stipend_monthly`, `work_location`, `reporting_to`, `learning_objectives`. No PF/ESI/Annexure A.
- **DOJ field reuse:** `custom_date_of_joining` semantically "Internship Start Date" for interns.
- **HTML template:** `intern_offer_letter.html`:
  - "Stipend" (not "salary")
  - Defined internship duration (e.g., 3 months, 6 months)
  - Learning objectives section
  - No PF, no ESI, no Annexure A
  - Termination on internship completion
  - Certificate of internship promised at successful completion
- **Zoho Sign:** Yes

### 4.3 Increment Letter

- **Trigger:** Salary Structure Assignment `on_submit`, but SKIP if any of:
  - `custom_send_increment_letter` checkbox is unchecked (HR decision)
  - No previous active SSA exists for this Employee (first salary — not an increment)
  - New CTC ≤ previous CTC (not an increment; could be a downgrade or correction)
- **Background:** `frappe.enqueue(queue="short")` so on_submit returns within 5 seconds
- **CTC source (Gap 1 fix):** New `custom_annual_ctc` Currency field added to SSA. HR fills this when creating the SSA. Context builder reads it directly — no formula/component summing.
- **Context builder:** `build_increment_context(ssa_doc)`:
  - Resolves Employee from `ssa_doc.employee`
  - Queries previous active SSA via `frappe.get_all("Salary Structure Assignment", filters={"employee": ..., "docstatus": 1, "name": ["!=", ssa_doc.name]}, fields=["name","custom_annual_ctc","from_date"], order_by="from_date desc", limit=1)`
  - Computes increment delta (INR + %)
- **HTML template:** `increment_letter.html`:
  - Header: "Salary Increment Letter" / "Compensation Revision Letter"
  - Salutation to employee by name
  - Acknowledges performance
  - Comparison block: Previous CTC → New CTC (with delta in INR and %)
  - Effective date
  - Brief Annexure showing new monthly breakup
  - HR signature image (no candidate signature)
- **PDF-only:** No Zoho. Generated PDF attached to SSA via `non_signing.generate_and_deliver()`.
- **Email delivery:** Employee's `company_email` → fallback `personal_email` → if neither, log warning and attach to SSA only.

### 4.4 Promotion Letter

- **Trigger:** Manual button "Generate Promotion Letter" on Employee form
- **Dialog (Gap 2 fix):** Button opens Frappe dialog asking for FOUR fields:
  - **Previous designation** (pre-filled with current `employee.designation`, HR can edit)
  - **New designation** (required)
  - **Effective date** (required, defaults to today)
  - **Manager notes** (optional textarea)

  Why both old + new: at button-click time we don't know if HR has already updated `designation`. Asking explicitly removes ambiguity.
- **Context builder:** `build_promotion_context(emp_doc, old_designation, new_designation, effective_date, notes)`
- **Background (Gap 6 fix):** Whitelisted method `send_promotion_letter(...)` invokes `frappe.enqueue(queue="short")` so the dialog returns immediately.
- **HTML template:** `promotion_letter.html`:
  - Header: "Promotion Letter"
  - Old designation → New designation
  - Effective date
  - Optional manager notes
  - Brief congratulations message
  - HR signature image
- **PDF-only:** Attached to Employee record via `non_signing.generate_and_deliver()`.
- **Email delivery (Gap 7 fix):** `company_email` → fallback `personal_email` → if neither, attach only.
- **Button mechanism (Gap 3 fix):** Client Script shipped in `fixtures/client_script.json`:
  - Adds button on Employee form
  - Visible only to users with `HR Manager` OR `System Manager` role (Gap 9)
  - On click → opens dialog → calls whitelisted `greythr_bridge.hooks_handlers.employee.send_promotion_letter`

### 4.5 Experience Letter

- **Trigger:** Employee Separation `on_submit` — IF `custom_send_experience_letter` is checked
- **Background (Gap 6):** Enqueued via `frappe.enqueue(queue="short")`
- **Context builder:** `build_experience_context(doc)`:
  - Resolves Employee via `doc.employee`
  - Computes employment summary (joining date, last working day, total tenure in years+months)
  - Uses current designation (Frappe HR doesn't always have designation history)
- **HTML template:** `experience_letter.html`:
  - "To Whom It May Concern" header
  - Employment dates + tenure summary
  - Designation held
  - Conduct certification: "...his conduct during this period was satisfactory"
  - Closing wishes
  - HR signature image
- **PDF-only:** Attached to Separation via `non_signing.generate_and_deliver()`.
- **Email delivery (Gap 7):** `personal_email` preferred (employee is leaving — company_email may be deactivated). Fallback `company_email`. If neither, attach only.

### 4.6 Relieving Letter

- **Trigger:** Employee Separation `on_submit` — IF `custom_send_relieving_letter` is checked
- **Background (Gap 6):** Enqueued via `frappe.enqueue(queue="short")` — fires alongside Experience Letter if both checkboxes are set
- **Context builder:** `build_relieving_context(doc)` — similar to Experience but different content
- **HTML template:** `relieving_letter.html`:
  - "To Whom It May Concern" header
  - Confirmation of relieving on specific date
  - Clearance status (all dues settled, company property returned)
  - Last working day
  - Brief tenure summary
  - HR signature image
- **PDF-only:** Attached to Separation via `non_signing.generate_and_deliver()`.
- **Email delivery (Gap 7):** Same as Experience — `personal_email` preferred, then `company_email`, then attach-only.

### 4.7 Service Certificate

- **Trigger:** Manual button "Generate Service Certificate" on Employee form (for current employees only)
- **Button mechanism (Gap 3):** Client Script in `fixtures/client_script.json`:
  - Adds button on Employee form
  - Visible only to `HR Manager` OR `System Manager` (Gap 9)
  - Only renders if Employee `status == "Active"` (skips ex-employees)
  - On click → opens confirmation dialog → calls whitelisted `greythr_bridge.hooks_handlers.employee.send_service_certificate`
- **Background (Gap 6):** Enqueued via `frappe.enqueue(queue="short")`
- **Context builder:** `build_service_certificate_context(emp_doc)` — current designation, joining date, status confirmation
- **HTML template:** `service_certificate.html`:
  - "To Whom It May Concern" header
  - Confirms employee IS currently employed (as of date of issue)
  - Current designation + joining date
  - Brief certificate-style language
  - HR signature image
- **PDF-only:** Attached to Employee record via `non_signing.generate_and_deliver()`.
- **Email delivery (Gap 7):** `company_email` → `personal_email` → attach-only. Updates `custom_service_certificate_issued_at` after success.

---

## 5. Custom fields needed

Added to `fixtures/custom_field.json`:

| Field | DocType | Type | Purpose | Default |
|---|---|---|---|---|
| `custom_offer_type` | Job Offer | Select | "Full-time" \| "Consultant" \| "Intern" | "Full-time" |
| `custom_engagement_duration_months` | Job Offer | Int | Consultant: months of engagement | (empty) |
| `custom_professional_fees_monthly` | Job Offer | Currency | Consultant: monthly retainer | (empty) |
| `custom_stipend_monthly` | Job Offer | Currency | Intern: monthly stipend | (empty) |
| `custom_internship_duration_months` | Job Offer | Int | Intern: months | (empty) |
| `custom_send_experience_letter` | Employee Separation | Check | Toggle Experience Letter generation | 1 (checked) |
| `custom_send_relieving_letter` | Employee Separation | Check | Toggle Relieving Letter generation | 1 (checked) |
| `custom_send_increment_letter` | Salary Structure Assignment | Check | Toggle Increment Letter generation (uncheck for initial salary creation, not an actual increment) | 1 (checked) |
| `custom_annual_ctc` | Salary Structure Assignment | Currency | Annual CTC value used by Increment Letter (Gap 1 fix — SSA has no native CTC field) | (empty) |
| `custom_increment_letter_generated` | Salary Structure Assignment | Check | Marker after PDF generated | 0 |
| `custom_promotion_letter_attached` | Employee | Check | Marker after Promotion Letter generated | 0 |
| `custom_service_certificate_issued_at` | Employee | Date | Last service cert issue date | (empty) |

**Total: 12 new custom fields.** All auto-installed via fixtures on `bench migrate`.

---

## 6. Shared infrastructure components

### 6.1 `letters/non_signing.py` (NEW)

Helper for the 5 PDF-only letters (Increment, Promotion, Experience, Relieving, Service Cert):

```python
def generate_and_deliver(
    template_filename: str,
    context: dict,
    attach_to: tuple[str, str],          # (doctype, docname)
    file_label: str,                     # e.g. "Increment Letter"
    employee_doc=None,                   # Frappe Employee doc — used to resolve email
    email_subject: str = "",
    email_body: str = "",
    prefer_personal_email: bool = False, # True for separation letters
) -> bytes:
    """
    Render PDF via merge_to_pdf_via_html(), attach as File to source doc,
    resolve employee email with fallback chain, email if address found.
    Returns PDF bytes.

    Email resolution (Gap 7 fix):
      if prefer_personal_email:
        personal_email -> company_email -> skip (log warning)
      else:
        company_email -> personal_email -> skip (log warning)
    """
```

All callers MUST invoke this from inside `frappe.enqueue(queue="short")` so the
synchronous on_submit / button-click handler returns within 5 seconds (Gap 6 fix).

### 6.2 `letters/dispatch.py` (NEW)

Picks the right template + context builder based on Job Offer type:

```python
def dispatch_offer_letter(doc) -> tuple[str, dict]:
    """Returns (template_filename, context_dict) based on custom_offer_type."""
    offer_type = getattr(doc, "custom_offer_type", "Full-time") or "Full-time"
    if offer_type == "Consultant":
        return "consultant_offer_letter.html", build_consultant_offer_context(doc)
    if offer_type == "Intern":
        return "intern_offer_letter.html", build_intern_offer_context(doc)
    return "offer_letter.html", build_offer_context(doc)
```

### 6.3 `_styles.css` additions

```css
/* HR signature image (PDF-only letters where HR signs via embedded image) */
.hr-sig-image {
  height: 14mm;
  width: auto;
  margin-bottom: 1mm;
  display: block;
}
.hr-sig-block {
  margin-top: 10mm;
  page-break-inside: avoid;
}
```

### 6.4 `hr_signature.png` asset (user provides)

User to save the signature image to `greythr_bridge/templates/letters/html/img/hr_signature.png` before deploy. (Provided in this conversation thread.)

---

## 7. Data flow

### For offer letters (Consultant / Intern) — same as Phase A
```
Job Offer submit → on_submit hook → send_offer_letter handler →
  → dispatch_offer_letter(doc) returns appropriate template + context →
  → merge_to_pdf_via_html(template, context) → PDF bytes →
  → Zoho Sign upload → signers sign → webhook → status = Accepted
```

### For PDF-only letters
```
Trigger event (submit or button click) → handler →
  → frappe.enqueue("...send_<letter>", queue="short", source_name=...)  [Gap 6: always enqueued]
  → handler returns immediately (5-second window safe)

  Background job:
  → build_<letter>_context(doc) → context dict →
  → non_signing.generate_and_deliver(template, context, attach_to=(doctype,docname), employee_doc=..., ...) →
    1. merge_to_pdf_via_html() → PDF bytes
    2. Frappe File doc.insert() → attached to source
    3. Resolve email via fallback chain [Gap 7]:
       - For onboarding/active employee letters: company_email -> personal_email -> skip
       - For separation letters (Experience, Relieving): personal_email -> company_email -> skip
    4. If email resolved: frappe.sendmail() → employee inbox
       Otherwise: log warning, skip email step
  → marker field set (e.g., custom_increment_letter_generated = 1)
```

---

## 8. Error handling

| Failure | Handling |
|---|---|
| `custom_offer_type` unknown value | Fall back to "Full-time" (default offer letter) |
| Source DocType missing required field | Log warning, skip letter generation, don't block submit |
| Email send fails (no employee email) | Log + attach PDF; HR can manually share |
| Increment letter: no previous SSA found | Show "—" for old CTC, still generate letter |
| HR signature image missing | Fall back to text-only "[Authorised Signatory]" |
| Employee Separation submit with both letters unchecked | Skip both, no error |
| Manual button clicked with missing data (e.g., new designation for Promotion) | Show dialog asking HR to provide |

All errors via `frappe.log_error(...)` with title `greytHR Letter Generation Error`.

---

## 9. HR signature image setup

The signature image attached in this thread shows "N. [handwritten signature]" — the company's authorised signatory.

Before deploy, user must save the image as:
```
greythr_bridge/templates/letters/html/img/hr_signature.png
```

Specs:
- Format: PNG with transparency preferred
- Recommended size: ~200×60 pixels (will display at 14mm height in PDF, auto-width)
- Background: transparent (so it overlays nicely on the white PDF)

Verification: after deploy, run `health_check` URL — we'll extend it (Gap 8 fix) to verify `hr_signature.png` is present and readable on the bench. Extension adds these keys to the JSON response:

```json
{
  "hr_signature_image_path": "/home/frappe/...img/hr_signature.png",
  "hr_signature_image_exists": true,
  "hr_signature_image_size_bytes": 12345
}
```

If `hr_signature_image_exists: false`, PDF-only letters will render but fall back to text-only "[Authorised Signatory]" placeholder. HR can re-upload the image and re-run `health_check` to confirm.

---

## 10. Testing

~25 new tests added to `tests/test_letters.py`:

- 1 test per letter type verifying context builder returns expected keys (7 tests)
- 1 test per letter type verifying HTML renders without Jinja errors (7 tests)
- 1 test for `dispatch_offer_letter()` returning correct (template, context) per offer_type (3 tests)
- 1 test for `non_signing.generate_and_deliver()` happy path (1 test)
- Custom field fixture sanity test (1 test)
- 6 misc integration tests (skipped on hosts without WeasyPrint rendering)

**Target: 94 → 119 passing.**

End-to-end smoke (local): render each of the 7 templates with FakeDoc, save PDFs, visually verify in PDF reader.

---

## 11. Definition of done

- ✅ 12 custom fields auto-installed via fixtures on `bench migrate`
- ✅ 2 Client Scripts (Promotion + Service Cert buttons) auto-installed via `fixtures/client_script.json`
- ✅ Health check confirms `hr_signature.png` present on bench
- ✅ All 7 HTML templates render valid PDFs locally + on Frappe Cloud
- ✅ `dispatch_offer_letter()` correctly branches by `custom_offer_type`
- ✅ Consultant + Intern offers go through Zoho Sign successfully (live test each)
- ✅ Increment auto-generates on SSA submit, PDF attached + emailed (live test)
- ✅ Promotion button on Employee form opens dialog, generates PDF on submit (live test)
- ✅ Experience + Relieving letters auto-generate on Separation submit when respective checkboxes set
- ✅ Service Certificate button on Employee form generates PDF (live test)
- ✅ HR signature image visible in all 5 PDF-only letters
- ✅ All 119 tests passing (94 existing + 25 new)
- ✅ At least 1 successful live test per letter type
- ✅ DOCX rendering path STILL in code (cleanup deferred to separate commit)
- ✅ Phase A's offer letter still works identically (no regression)

---

## 12. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| HR's source DOCX content doesn't translate cleanly to HTML | Medium | We have all 7 DOCX. I'll preserve HR's exact language wherever possible; flag awkward sections for HR review before deploy. |
| Frappe HR doesn't have all Employee fields we need (e.g. designation history) | Medium | Use `getattr(doc, field, default)` defensively; fall back to current designation when history unavailable. |
| Manual buttons on Employee form require Client Script which is hard to maintain | Low | Ship Client Scripts as fixtures (auto-installed). Document them in CLAUDE.md. |
| Email delivery fails silently | Low | Frappe's sendmail returns success/fail; we log failures. HR can re-trigger via button. |
| Two letters generated for same Separation cause confusion | Low | Letter naming: "Experience Letter - {name}.pdf" and "Relieving Letter - {name}.pdf" — clearly named. |
| Increment letter: previous SSA missing/cancelled | Low | Show "—" for old CTC, still generate. Don't fail. |
| `custom_offer_type` migration on existing Job Offers | Low | Default value "Full-time" — existing offers behave identically. |
| HR signature image file is missing on Frappe Cloud bench | Medium | Pre-flight check in health_check; if missing, PDF falls back to text-only signature ("[Authorised Signatory]") |
| Increment Letter triggers on EVERY SSA submit (including initial salary creation, not just increments) | Medium | HR controls via `custom_send_increment_letter` checkbox on SSA (default checked). Plus defensive check: if no previous SSA exists OR new CTC ≤ previous CTC, skip with a log warning. |
| Promotion / Service Cert buttons visible to wrong users | Low | Client Script gates visibility to `HR Manager` OR `System Manager` roles (Gap 9). Backend handler also enforces role check via `frappe.get_roles()`. |
| Background job (enqueued letter generation) silently fails | Low | All errors logged to `Error Log` with title `greytHR Letter Generation Error`. Retrieveable via existing `get_recent_errors` endpoint. |

---

## 13. Out of scope (explicit non-goals)

- Removing DOCX path entirely — separate cleanup commit later
- Bulk letter generation (CSV upload → generate for many employees) — separate feature
- Letter templates editable via Frappe Print Format UI — future enhancement
- Multi-language support — future
- Letterhead variations per business unit — future
- E-stamping (Indian stamp duty) integration — separate Zoho feature
- Signed PDF push to greytHR (Phase 6) — separate phase
- Audit log dashboard for letter generation history — future feature

---

## 14. Phased implementation within Phase B

To stay under 20 hours and ship incrementally, work breaks into 5 logical sub-commits, all pushed together:

| Sub-step | Deliverable | Effort |
|---|---|---|
| B.1 | Custom Fields fixture (10 new fields) + dispatcher skeleton | 1 hour |
| B.2 | Shared infrastructure: `non_signing.py`, signature image, CSS additions | 2 hours |
| B.3 | Consultant + Intern Offer Letters (Zoho flow, similar to Phase A) | 4 hours |
| B.4 | Increment + Promotion Letters (PDF-only, SSA + Employee button) | 3 hours |
| B.5 | Experience + Relieving + Service Certificate (PDF-only) | 3 hours |
| B.6 | Tests + local smoke + commit + push | 2 hours |
| B.7 | Frappe Cloud deploy + 7 live tests (one per letter) | 2 hours |
| **Total** | | **~17 hours** |

All sub-steps land in ONE commit (atomic). User does ONE deploy. ONE migrate. Then live-tests each letter.

---

## 15. Assumptions / what HR needs to provide before/during testing

1. **`hr_signature.png`** — user has attached image, will save to project before deploy
2. **HR-reviewed source content** — we'll use the language from the 7 DOCX files in `templates/`. If HR wants different wording, they can update HTML templates later (or we iterate)
3. **At least one test employee** in Frappe HR for each scenario:
   - Employee for Promotion + Service Cert tests
   - Active SSA for Increment test (and a previous SSA to compare against)
   - Active Employee Separation (with both checkboxes set) for Experience + Relieving test
4. **Test Job Offers** with `custom_offer_type = Consultant` and `custom_offer_type = Intern` to test the two new offer types

---

## 16. Approval gate

User must approve this spec before implementation begins.

---

## Sources / references

- [Phase A spec — WeasyPrint offer letter](2026-05-21-weasyprint-offer-letter-design.md)
- [HR source DOCX templates](../../../templates/)
- [Frappe HR DocType: Job Offer](https://docs.frappe.io/hr/job-offer)
- [Frappe HR DocType: Salary Structure Assignment](https://docs.frappe.io/hr/salary-structure-assignment)
- [Frappe HR DocType: Employee Separation](https://docs.frappe.io/hr/employee-separation)

---

## Revision log

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-05-22 | Initial draft |
| 2 | 2026-05-22 | Self-review found inconsistency: added `custom_send_increment_letter` field that was referenced in §12 but missing from §5. Now 11 fields. |
| 3 | 2026-05-22 | Re-check found 11 gaps. Applied all 11 fixes: (1) added `custom_annual_ctc` to SSA so Increment Letter can compute old vs new CTC reliably — now 12 fields total; (2) Promotion dialog captures both old + new designation; (3) added `fixtures/client_script.json` for Promotion + Service Cert buttons; (4) hooks.py doc_events block shown explicitly in §3; (5) DOJ field stays mandatory, used semantically as Start Date for Consultant/Intern; (6) ALL PDF-only letter handlers use `frappe.enqueue(queue="short")`; (7) email delivery uses fallback chain (with `prefer_personal_email` for separation letters); (8) health_check extended to verify hr_signature.png presence; (9) button visibility restricted to HR Manager / System Manager; (10) Increment skip logic made explicit (checkbox + no-prior-SSA + delta <= 0); (11) Consultant/Intern context builders are INDEPENDENT, not derived from offer context. |
