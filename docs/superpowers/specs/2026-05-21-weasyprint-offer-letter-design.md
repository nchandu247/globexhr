# WeasyPrint Offer Letter — Design Spec (Phase A)

**Date:** 2026-05-21
**Author:** Chandu + Claude (Opus 4.7)
**Status:** Draft — awaiting user review
**Scope:** Replace the current DOCX-based offer letter generation with HTML+CSS rendered to PDF via WeasyPrint. Phase A covers ONLY the offer letter — other 6 letter types deferred to future specs.
**Supersedes:** Polish design (2026-05-21-offer-letter-polish-design.md) — DOCX polish was a stopgap; this is the real fix.

---

## 1. Goals

Produce a professional, consistent, controllable offer letter PDF that:

- Eliminates every issue observed in the current PDF (visible tags, dark watermark, awkward line breaks, font quality, page break problems)
- Uses modern HTML+CSS so all future design changes are trivial
- Establishes the rendering infrastructure that the other 6 letter types can reuse later
- Maintains 100% of the existing legal/business language from HR's approved DOCX

**Non-goals (Phase A only):**

- Other letter types (consultant offer, intern offer, increment, promotion, experience, relieving, service certificate)
- Removing the DOCX path entirely (kept as fallback during testing window)
- Changing any legal/business language HR approved
- Adding new content sections (variable pay paragraph, joining bonus, etc.)

---

## 2. Why WeasyPrint (and not alternatives)

| Option | Decision | Reason |
|---|---|---|
| **WeasyPrint** | ✅ Chosen | Pure Python, modern CSS, lightweight, secure, actively maintained, works on Frappe Cloud (pending libcairo2 verification) |
| wkhtmltopdf | ❌ Rejected | Archived January 2023, unpatched CVEs, legal documents shouldn't run on deprecated software |
| Frappe Chromium (via print_designer app) | ❌ Deferred | NOT yet supported on Frappe Cloud per [Frappe forum](https://discuss.frappe.io/t/new-feature-faster-better-printing-backend/143774) — re-evaluate in 6-12 months |
| Playwright / Headless Chromium | ❌ Rejected | 10× deployment complexity, ~300MB Chromium binary, browser crash management — overkill for 5-10 letters/month |
| Gotenberg (microservice) | ❌ Rejected | Additional service to deploy/monitor, no native Frappe Cloud support |
| Stay with DOCX | ❌ Rejected | Already spent 15+ hours hitting unfixable layout issues |

---

## 3. Architecture

Three new files, two modifications, one dependency:

```
greythr_bridge/
├── pyproject.toml                          [+ weasyprint]
├── letters/
│   ├── merger.py                           [+ merge_to_pdf_via_html()]
│   └── pdf_check.py                        [NEW: libcairo + weasyprint availability]
├── templates/letters/html/                 [NEW directory]
│   ├── _base.html                          [letterhead + watermark + footer + Zoho tag area]
│   ├── _styles.css                         [typography, colors, @page rules, signature blocks]
│   ├── fonts/                              [self-hosted Inter font files — no network fetch]
│   └── offer_letter.html                   [extends _base, body content only]
├── hooks_handlers/job_offer.py             [_generate_document uses HTML path]
└── utils/logging.py                        [extend health_check with weasyprint checks]
```

**Critical principle:** `build_offer_context()` in merger.py stays unchanged. Same 60+ context keys feed HTML that fed DOCX. Data layer is settled; only rendering changes.

---

## 4. Pre-flight verification (must pass before Phase A proceeds)

Before building any HTML templates, deploy ONE commit that adds:

1. `weasyprint` to `pyproject.toml` dependencies
2. New file `greythr_bridge/letters/pdf_check.py`:
   ```python
   def check_pdf_dependencies() -> dict:
       import ctypes.util
       result = {
           "weasyprint_installed": False,
           "weasyprint_version": None,
           "libcairo_available": False,
           "libpango_available": False,
           "libgdk_pixbuf_available": False,
       }
       try:
           import weasyprint
           result["weasyprint_installed"] = True
           result["weasyprint_version"] = weasyprint.__version__
       except Exception as e:
           result["weasyprint_error"] = str(e)[:200]
       result["libcairo_available"] = bool(ctypes.util.find_library("cairo"))
       result["libpango_available"] = bool(ctypes.util.find_library("pango-1.0"))
       result["libgdk_pixbuf_available"] = bool(ctypes.util.find_library("gdk_pixbuf-2.0"))
       return result
   ```
3. Wire `check_pdf_dependencies()` into the existing `health_check()` function in `greythr_bridge/letters/merger.py` (where the health check already lives). The new keys merge into the existing health_check response.

**Then deploy** (Apps → Fetch → Update Bench → Migrate) and **hit `https://hr.globexdigital.ai/api/method/greythr_bridge.letters.merger.health_check`** in a logged-in browser. Verify the JSON response includes the new keys:

```json
{
  "weasyprint_installed": true,
  "weasyprint_version": "65.1" (or later),
  "libcairo_available": true,
  "libpango_available": true,
  "libgdk_pixbuf_available": true
}
```

**Gate:** if all four `*_available` keys are true, proceed with the rest of Phase A. If any are false, open a Frappe Cloud support ticket requesting the missing system library (same flow as we'd use to request LibreOffice or any apt package).

---

## 5. Component design

### 5.1 `letters/pdf_check.py` (NEW)

Single function `check_pdf_dependencies()` as shown in Section 4. ~30 lines. Pure Python, no Frappe dependencies — testable offline.

### 5.2 `letters/merger.py` (MODIFIED)

Add new function:

```python
def merge_to_pdf_via_html(template_filename: str, context: dict) -> bytes:
    """
    Render an HTML template with context (Jinja2) and return PDF bytes via WeasyPrint.

    Template files live in templates/letters/html/. Templates use {% extends '_base.html' %}.
    CSS is loaded from _styles.css and applied during rendering.

    Raises frappe.ValidationError if template missing.
    Raises RuntimeError if WeasyPrint rendering fails.
    """
    from weasyprint import HTML, CSS
    import frappe

    html_dir = os.path.join(os.path.dirname(__file__), "..", "templates", "letters", "html")
    template_path = os.path.join(html_dir, template_filename)
    css_path = os.path.join(html_dir, "_styles.css")

    if not os.path.exists(template_path):
        frappe.throw(f"HTML template not found: {template_filename}")

    with open(template_path, "r", encoding="utf-8") as f:
        html_template = f.read()

    rendered_html = frappe.render_template(html_template, context)

    return HTML(string=rendered_html, base_url=html_dir).write_pdf(
        stylesheets=[CSS(filename=css_path)] if os.path.exists(css_path) else []
    )
```

Keep `merge_to_docx()` available unchanged. Will be removed in a later commit after live verification.

### 5.3 `templates/letters/html/_base.html` (NEW)

Skeleton:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{{ ref_number }} — Offer Letter</title>
</head>
<body>
  <div class="page-content">
    {% block body %}{% endblock %}
  </div>

  <!-- Invisible Zoho Sign signature tags — placed once, end of doc -->
  <div class="zoho-tags">{{ "{{S:R1*}}" }}     {{ "{{S:R2*}}" }}</div>
</body>
</html>
```

Note: `{{ "{{S:R1*}}" }}` makes Jinja render the literal text `{{S:R1*}}` into the final HTML (Jinja's own escape pattern), which is what Zoho's auto-detection sees.

### 5.4 `templates/letters/html/_styles.css` (NEW)

Single CSS file. Sections:

**Reset + box-sizing:**
```css
* { box-sizing: border-box; }
body { margin: 0; padding: 0; }
```

**Fonts (self-hosted, no network):**
```css
@font-face {
  font-family: 'Inter';
  src: url('fonts/Inter-Regular.ttf') format('truetype');
  font-weight: 400;
}
@font-face {
  font-family: 'Inter';
  src: url('fonts/Inter-SemiBold.ttf') format('truetype');
  font-weight: 600;
}
```
Fonts shipped with app, no Google Fonts dependency.

**Page setup (CSS Paged Media):**
```css
@page {
  size: A4;
  margin: 25mm 20mm 25mm 20mm;
  @top-left  { content: element(letterhead); }
  @bottom-center { content: element(footer); font-size: 9pt; color: #555; }
}
```

**Letterhead (runs on every page):**
```css
.letterhead { position: running(letterhead); ... }
.letterhead img.logo { height: 18mm; }
```

**Watermark (subtle background):**
```css
body::before {
  content: "";
  position: fixed;
  inset: 0;
  background: url('img/globex-watermark.png') no-repeat center;
  background-size: 60%;
  opacity: 0.08;
  z-index: -1;
}
```

**Typography:**
```css
body { font-family: 'Inter', 'Calibri', sans-serif; font-size: 11pt; color: #1a1a1a; line-height: 1.5; }
h1 { font-size: 20pt; font-weight: 600; }
h2 { font-size: 13pt; font-weight: 600; margin-top: 8mm; }
```

**Tables (Annexure A):**
```css
table.salary-breakup { width: 100%; border-collapse: collapse; page-break-inside: avoid; }
table.salary-breakup th { background: #01248A; color: white; padding: 2mm; text-align: left; }
table.salary-breakup tr.total { background: #f0f0f0; font-weight: 600; }
```

**Signature blocks:**
```css
.signature-block { display: flex; justify-content: space-between; margin-top: 15mm; page-break-inside: avoid; }
.signature-line { border-top: 1px solid #333; padding-top: 2mm; width: 40%; }
```

**Zoho tag invisibility:**
```css
.zoho-tags { color: white; font-size: 0.1pt; line-height: 0; }
```

**Page break controls:**
```css
h2 { page-break-after: avoid; }
.no-break { page-break-inside: avoid; }
```

### 5.5 `templates/letters/html/offer_letter.html` (NEW)

Extends `_base.html`, fills `{% block body %}` with the existing offer letter content from HR's DOCX:

- Greeting + ref/date
- Selection paragraph (designation, company)
- Joining paragraph (location, DOJ)
- Conditional Reporting Manager line (`{% if reporting_to %}...{% endif %}`)
- Salary paragraph + Annexure A table
- Introductory Period
- Tax Advice
- Conflict of Interest
- Separation + Notice Period
- Benefits + Leave
- Right to Hire
- Project Start Date
- Acceptance section
- Two-column signature block (HR + Candidate)

All variable substitutions use the existing context keys from `build_offer_context()`.

### 5.6 `hooks_handlers/job_offer.py` (MODIFIED)

Change `_generate_document()`:

```python
def _generate_document(doc) -> bytes | None:
    """Merge offer letter template and return PDF bytes via WeasyPrint."""
    try:
        from ..letters.merger import build_offer_context, merge_to_pdf_via_html
        context = build_offer_context(doc)
        return merge_to_pdf_via_html("offer_letter.html", context)
    except Exception as exc:
        log_error(
            f"_generate_document: doc={doc.name} error={str(exc)[:200]}",
            "greytHR Letter Generation Error",
        )
        return None
```

Also change `send_for_signature` call: `file_extension="pdf"` instead of `"docx"`.

### 5.7 `letters/merger.py:health_check()` (EXTENDED)

The existing `health_check()` function in `letters/merger.py` already returns docxtpl, template, libreoffice, and custom field statuses. Extend it to also call `check_pdf_dependencies()` and merge the result:

```python
@frappe.whitelist()
def health_check() -> dict:
    # ...existing implementation that returns docxtpl/template/libreoffice/custom_field keys...

    from .pdf_check import check_pdf_dependencies
    result.update(check_pdf_dependencies())

    return result
```

Same URL as before: `/api/method/greythr_bridge.letters.merger.health_check`.

---

## 6. Data flow

```
Job Offer submit
  → on_offer_submitted hook
    → enqueue send_offer_letter (queue=short)
      → frappe.get_doc("Job Offer", offer_name)
      → idempotency check (existing custom_zoho_sign_request_id)
      → pre-flight (default_signatory, applicant_email, DOJ)
      → build_offer_context(doc)  ← UNCHANGED, 60+ keys
      → merge_to_pdf_via_html("offer_letter.html", context)  ← NEW
        ├─ frappe.render_template(html, context)  → rendered HTML string
        └─ weasyprint.HTML(string=...).write_pdf(stylesheets=[_styles.css])  → PDF bytes
      → send_for_signature(file_bytes=pdf, file_extension="pdf", ...)
        → POST /requests + /submit to Zoho Sign
      → save request_id with deadlock retry
    → Zoho emails signers
    → Candidate signs
    → webhook → push to greytHR (Phase 6, separate)
```

---

## 7. Error handling

| Failure mode | Handling |
|---|---|
| `weasyprint` not installed | health_check shows `weasyprint_installed: false`; offer submission fails with clear log message |
| `libcairo2` missing | pre-flight blocks; support ticket workflow |
| Template file missing | `frappe.throw` with template path, surfaced to user |
| Jinja rendering error (missing var) | Caught in `merge_to_pdf_via_html`, logged with template + offending var |
| WeasyPrint render error (bad CSS, missing image) | Caught, logged with stage indicator, raises so handler aborts and email never sent |
| PDF bytes empty or < 5KB | Raise — an offer letter PDF should always be > 30KB; anything tiny indicates a rendering failure |
| Zoho Sign rejects PDF | Already handled by existing `send_for_signature` error path |

All errors readable via `/api/method/greythr_bridge.utils.logging.get_recent_errors`.

---

## 8. Testing

Unit tests (5 new, 87 → 92):

1. `test_letters.py::test_pdf_check_returns_status_keys` — `check_pdf_dependencies()` returns dict with all 5 expected keys, booleans for availability.

2. `test_letters.py::test_merge_to_pdf_via_html_returns_valid_pdf` — render offer_letter.html with sample context, verify output starts with `%PDF-` magic bytes and is > 10KB.

3. `test_letters.py::test_pdf_contains_all_context_values` — extract text from rendered PDF (via `pypdf` or similar lightweight reader), assert candidate_name, designation, salary value, DOJ all appear.

4. `test_letters.py::test_pdf_includes_zoho_signature_tags` — extract text from PDF, assert literal `{{S:R1*}}` and `{{S:R2*}}` strings are present (even though styled invisible).

5. `test_letters.py::test_pdf_omits_reporting_manager_when_blank` — render with `reporting_to=""`, assert "You will report to" not present.

End-to-end smoke (local): run merger with realistic context, save PDF, open in viewer, verify visually.

End-to-end live: submit a real Job Offer on Frappe Cloud, sign via Zoho, verify the final signed PDF meets all "Definition of done" criteria.

---

## 9. Definition of done

A new Job Offer submitted on Frappe Cloud produces a Zoho-rendered signed PDF where ALL of these are observable:

- ✅ `weasyprint_installed: true` and `libcairo_available: true` in `health_check` JSON
- ✅ Modern font (Inter) renders correctly across all pages
- ✅ Logo top-left on every page (controlled via CSS `@page`)
- ✅ Watermark visible but at 8% opacity — readable text in front of it
- ✅ NO visible `{{S:R1*}}` `{{S:R2*}}` tags anywhere in PDF
- ✅ Date of Joining appears in all 4 places (joining paragraph, Annexure Effective Date, Project Start Date, Acceptance)
- ✅ Reporting Manager line appears when `custom_reporting_to` set, omitted otherwise
- ✅ Salutation reads "Hi Vedanth Nalluri," with no weird dot
- ✅ Salary displayed as Indian comma format (₹ 6,00,000) wherever amounts shown
- ✅ Annexure A salary table does not split across pages (or splits cleanly with header repeat)
- ✅ Signature block (HR + Candidate side-by-side) on signature page, not split
- ✅ NO orphan headings at top of any page (Authorized Signatory etc.)
- ✅ NO empty pages
- ✅ Both signatures placed by Zoho Sign on the signature page
- ✅ All 87 existing tests still pass + 5 new tests pass (92 total)

---

## 10. Risks & mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| libcairo2 missing on Frappe Cloud bench | Medium | Pre-flight check via health_check gates entire migration. Support ticket if missing. |
| WeasyPrint render differs from local browser preview | Certain (different engine) | We render once on server, no user inspects HTML. Output is what matters. |
| WeasyPrint can't handle a needed CSS feature | Low for static doc | Falls within CSS Paged Media Level 3 + Flexbox which WeasyPrint fully supports |
| Zoho Sign rejects invisible signature tags (color: white) | Low | Zoho parses text content, color-agnostic. Verified earlier with DOCX approach. Fallback: font-size: 0.1pt |
| Cold-start render slow (~600ms) | Low impact | Volume is 5-10 letters/month — performance irrelevant |
| Page breaks inside Annexure A | Medium | `page-break-inside: avoid` on table, with `thead` repeated. Standard CSS. |
| Self-hosted Inter font fails to load | Low | Fallback in CSS: `font-family: 'Inter', 'Calibri', sans-serif;` |
| HR doesn't like the new design | Medium | Iterate on CSS — much faster than DOCX iterations |
| Migration breaks existing draft offer | Low | DOCX path kept as fallback for one deploy cycle; can revert easily |

---

## 11. Out of scope (explicit non-goals)

- Other 6 letter types — separate specs per letter
- Removing the DOCX path — done in a later commit after live verification
- Frappe Print Format integration (UI-editable templates) — defer to future
- Migration to Frappe's Chromium PDF when it becomes available on Cloud — future
- PDF/A-1b compliance for long-term archival — future
- Digital seal / certificate of signing — Zoho handles this
- Multi-language support — future
- Mobile-responsive HTML — letters are print-only documents

---

## 12. Effort estimate

- Pre-flight verification commit (deps + check): 30 min
- HTML+CSS base + offer_letter.html with all sections: 3 hours
- `merge_to_pdf_via_html()` + 5 tests: 1.5 hours
- Handler switch: 15 min
- Local smoke test (visually verify PDF): 30 min
- Live test on Frappe Cloud (full sign cycle): 30 min
- **Total: ~6 hours wall-clock**

If libcairo2 missing → add support-ticket wait time (likely a day).

---

## 13. Phased approach within Phase A

| Step | Deliverable | Gate before next step |
|---|---|---|
| A.1 | Pre-flight commit (deps + check) | `health_check` shows all green |
| A.2 | _base.html + _styles.css + offer_letter.html | Local PDF generation works, looks good visually |
| A.3 | merge_to_pdf_via_html() + 5 tests | All 92 tests pass |
| A.4 | Handler switch + push as one commit | Deploy succeeds |
| A.5 | Live offer letter test | Signed PDF meets all 14 "Definition of done" criteria |
| A.6 | Remove DOCX path (separate commit) | After 1 week of stable HTML path |

---

## 14. After Phase A succeeds

Next steps (separate specs each):

- Phase B: rebuild remaining 6 letter types using established HTML+CSS infrastructure
- Phase C: remove DOCX rendering code entirely
- Phase D: consider HR-editable templates via Frappe Print Format DocType

Each gets its own design spec via the same brainstorming flow.

---

## 15. Approval

User must approve this spec before implementation begins. Implementation will follow the phased approach in Section 13, with each step verified before the next.

---

## Sources

- [WeasyPrint official site](https://weasyprint.org/)
- [WeasyPrint samples (CourtBouillon)](https://github.com/CourtBouillon/weasyprint-samples)
- [PDF4.dev benchmark 2026](https://pdf4.dev/blog/html-to-pdf-benchmark-2026)
- [Frappe Chromium PDF announcement](https://discuss.frappe.io/t/new-feature-faster-better-printing-backend/143774)
- [DocRaptor wkhtmltopdf alternatives](https://docraptor.com/wkhtmltopdf-alternatives)
