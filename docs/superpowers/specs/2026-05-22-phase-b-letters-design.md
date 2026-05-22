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
├── hooks.py                                 [MODIFIED: register new doc_events]
└── fixtures/custom_field.json               [+ new fields: see Section 5]
```

**Reuse principle:** `build_offer_context()` from Phase A stays. New context builders share helpers (`fmt_inr`, `fmt_date`, `_get_applicant_email`).

---

## 4. Detailed per-letter design

### 4.1 Consultant Offer Letter

- **Trigger:** Job Offer `on_submit` → handler branches on `custom_offer_type == "Consultant"`
- **Context builder:** `build_consultant_offer_context(doc)` in merger.py — reuses 80% of `build_offer_context` but adds: `engagement_duration`, `professional_fees_monthly`, `gst_clause`. Excludes: probation, PF/ESI deductions (consultants are not employees).
- **HTML template:** `consultant_offer_letter.html` — same structure as Phase A but content reflects consultancy relationship:
  - No "employment" language — uses "engagement"
  - No salary table (Annexure A); instead a "Professional Fees" section with monthly retainer
  - GST clause (consultant invoices with GST)
  - Termination by either party with 30-day notice (not "60 days notice period")
  - No Benefits / Leave sections
- **Zoho Sign:** Yes — `merge_to_pdf_via_html("consultant_offer_letter.html", ...)` → upload to Zoho with `{{S:R1*}}` and `{{S:R2*}}` tags

### 4.2 Intern Offer Letter

- **Trigger:** Same as Consultant — Job Offer `on_submit` with `custom_offer_type == "Intern"`
- **Context builder:** `build_intern_offer_context(doc)` — uses: `stipend_monthly`, `internship_duration_months`, `learning_objectives`
- **HTML template:** `intern_offer_letter.html`:
  - "Stipend" (not "salary")
  - Defined internship duration (e.g., 3 months, 6 months)
  - Learning objectives section
  - No PF, no ESI, no Annexure A
  - Termination on internship completion
  - Certificate of internship promised at successful completion
- **Zoho Sign:** Yes

### 4.3 Increment Letter

- **Trigger:** Salary Structure Assignment `on_submit` (new hook in `hooks_handlers/salary_structure_assignment.py`)
- **Context builder:** `build_increment_context(doc)`:
  - Resolves Employee from SSA
  - Fetches PREVIOUS active SSA for same employee to compute old CTC vs new CTC
  - Computes increment amount (delta) and percentage
- **HTML template:** `increment_letter.html`:
  - Header: "Salary Increment Letter" / "Compensation Revision Letter"
  - Salutation to employee by name
  - Acknowledges performance
  - Comparison block: Previous CTC → New CTC (with delta in INR and %)
  - Effective date
  - Brief Annexure showing new monthly breakup
  - HR signature image (no candidate signature)
- **PDF-only:** No Zoho. Generated PDF attached to SSA, emailed to employee's company email.

### 4.4 Promotion Letter

- **Trigger:** Manual button "Generate Promotion Letter" on Employee form
- **Context builder:** `build_promotion_context(doc, new_designation, effective_date, notes)` — takes args from button dialog
- **HTML template:** `promotion_letter.html`:
  - Header: "Promotion Letter"
  - Old designation → New designation
  - Effective date
  - Optional manager notes
  - Brief congratulations message
  - HR signature image
- **PDF-only:** Attached to Employee record, emailed.
- **Button placement:** Frappe Server Script or whitelisted method invoked from a custom client-script button on Employee form. We add the client script via fixtures.

### 4.5 Experience Letter

- **Trigger:** Employee Separation `on_submit` — IF `custom_send_experience_letter` is checked
- **Context builder:** `build_experience_context(doc)`:
  - Resolves Employee
  - Computes employment summary (joining date, last working day, total tenure in years+months)
  - Lists all designations held (from Employee history if available, else current)
- **HTML template:** `experience_letter.html`:
  - "To Whom It May Concern" header
  - Employment dates + tenure summary
  - Designation(s) held
  - Conduct certification: "...his conduct during this period was satisfactory"
  - Closing wishes
  - HR signature image
- **PDF-only:** Attached to Separation, emailed.

### 4.6 Relieving Letter

- **Trigger:** Employee Separation `on_submit` — IF `custom_send_relieving_letter` is checked
- **Context builder:** `build_relieving_context(doc)` — similar to Experience but different content
- **HTML template:** `relieving_letter.html`:
  - "To Whom It May Concern" header
  - Confirmation of relieving on specific date
  - Clearance status (all dues settled, company property returned)
  - Last working day
  - Brief tenure summary
  - HR signature image
- **PDF-only:** Attached to Separation, emailed.

### 4.7 Service Certificate

- **Trigger:** Manual button "Generate Service Certificate" on Employee form (for current employees, not separated)
- **Context builder:** `build_service_certificate_context(doc)` — current designation, joining date, status: currently employed
- **HTML template:** `service_certificate.html`:
  - "To Whom It May Concern" header
  - Confirms candidate IS currently employed (as of date of issue)
  - Current designation + joining date
  - Brief certificate-style language
  - HR signature image
- **PDF-only:** Attached to Employee record, emailed if requested.

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
| `custom_increment_letter_generated` | Salary Structure Assignment | Check | Marker after PDF generated | 0 |
| `custom_promotion_letter_attached` | Employee | Check | Marker after Promotion Letter generated | 0 |
| `custom_service_certificate_issued_at` | Employee | Date | Last service cert issue date | (empty) |

**Total: 11 new custom fields.** All auto-installed via fixtures on `bench migrate`.

---

## 6. Shared infrastructure components

### 6.1 `letters/non_signing.py` (NEW)

Helper for the 5 PDF-only letters (Increment, Promotion, Experience, Relieving, Service Cert):

```python
def generate_and_deliver(
    template_filename: str,
    context: dict,
    attach_to: tuple[str, str],  # (doctype, docname)
    email_to: str | None = None,
    email_subject: str = "",
    email_body: str = "",
) -> bytes:
    """
    Render PDF via merge_to_pdf_via_html(), attach as File to source doc,
    optionally email to employee. Returns PDF bytes.
    """
```

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
  → build_<letter>_context(doc) → context dict →
  → generate_and_deliver(template, context, attach_to=(doctype, docname), email_to=...) →
    1. merge_to_pdf_via_html() → PDF bytes
    2. Frappe File doc.insert() → attached to source
    3. frappe.sendmail() → employee inbox (optional)
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

Verification: after deploy, run `health_check` URL — we'll extend it to verify hr_signature.png is present and readable.

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

- ✅ 10 custom fields auto-installed via fixtures on `bench migrate`
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
