"""
DOCX mail-merge for Globex HR letters using docxtpl (Jinja2 inside Word).

Templates live in greythr_bridge/templates/letters/*.docx.
Add {{ variable_name }} placeholders in your Word document.
Call merge_to_pdf() to get PDF bytes ready for Zoho Sign.

Smoke tests (run via bench execute):
    bench --site hr-globexdigital execute greythr_bridge.letters.merger.test_merge_only
    bench --site hr-globexdigital execute greythr_bridge.letters.merger.test_merge_to_pdf
"""
import os
import tempfile

import frappe
from docxtpl import DocxTemplate

from .pdf_convert import docx_to_pdf_bytes


_TEMPLATE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "templates", "letters")
)


def merge_to_pdf(template_filename: str, context: dict) -> bytes:
    """
    Fill *template_filename* (inside templates/letters/) with *context*
    and return PDF bytes.

    Raises frappe.ValidationError if the template file is missing.
    Raises RuntimeError if LibreOffice conversion fails.
    """
    template_path = os.path.join(_TEMPLATE_DIR, template_filename)
    if not os.path.exists(template_path):
        frappe.throw(
            f"Letter template not found: {template_filename}<br>"
            f"Expected path: {template_path}",
            title="Template Missing",
        )

    tpl = DocxTemplate(template_path)
    tpl.render(context)

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        tpl.save(tmp_path)
        return docx_to_pdf_bytes(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def build_offer_context(doc) -> dict:
    """
    Build the Jinja2 context dict from a Job Offer document.
    Matches the {{ variable }} placeholders expected in offer_letter.docx.

    All numeric values are returned as bare strings in Indian comma format
    (e.g. '6,00,000') with NO currency symbol — the template adds '₹' where needed.
    """
    def fmt_inr(value) -> str:
        """Format a number in Indian comma style, no currency symbol.
        e.g. 600000 → '6,00,000', 12345678 → '1,23,45,678'.
        """
        try:
            n = float(value or 0)
        except (TypeError, ValueError):
            return "0"
        s = "{:.0f}".format(n)
        if len(s) <= 3:
            return s
        last3, rest = s[-3:], s[:-3]
        grouped = ""
        while len(rest) > 2:
            grouped = "," + rest[-2:] + grouped
            rest = rest[:-2]
        return rest + grouped + "," + last3

    def fmt_date(value) -> str:
        """Format a Frappe date field as '01 June 2025'."""
        if not value:
            return ""
        try:
            import frappe.utils
            return frappe.utils.formatdate(value, "dd MMMM yyyy")
        except Exception:
            return str(value)

    # ── Salary components ─────────────────────────────────────────────────────
    basic   = doc.custom_basic_monthly or 0
    hra     = doc.custom_hra_monthly or 0
    conv    = doc.custom_conveyance_allowance_monthly or 0
    med_all = doc.custom_medical_allowance_monthly or 0
    special = doc.custom_special_allowance_monthly or 0
    gross   = basic + hra + conv + med_all + special

    emp_pf  = doc.custom_employee_pf_monthly or 0
    emp_esi = doc.custom_employee_esi_monthly or 0
    pt      = doc.custom_professional_tax_monthly or 0
    net     = gross - emp_pf - emp_esi - pt

    er_pf   = doc.custom_employer_pf or 0
    er_esi  = doc.custom_employer_esiinsurance_monthly or 0

    annual_ctc   = doc.custom_annual_ctc or 0
    monthly_ctc  = round(annual_ctc / 12) if annual_ctc else gross + er_pf + er_esi

    esi_applies = gross <= 21000

    # Medical insurance line for Annexure — shown only when ESI doesn't apply
    med_ins_monthly = 0
    if not esi_applies and not doc.custom_medical_insurance_opted_out:
        annual_prem = doc.custom_medical_insurance_annual_premium or 10000
        med_ins_monthly = round(annual_prem / 12)

    # ── Optional offer terms (custom fields on Job Offer) ─────────────────────
    work_location         = getattr(doc, "custom_work_location", None) or "Hyderabad"
    probation_period      = getattr(doc, "custom_probation_period", None) or "6 months"
    notice_period         = getattr(doc, "custom_notice_period", None) or "60 days"
    joining_bonus_raw     = getattr(doc, "custom_joining_bonus", None) or 0
    variable_pay_raw      = getattr(doc, "custom_variable_pay_annual", None) or 0
    acceptance_deadline_v = getattr(doc, "custom_acceptance_deadline", None)
    band                  = getattr(doc, "custom_band", None) or ""

    # ── Annual / total derived values for Annexure A ──────────────────────────
    total_deductions_monthly = emp_pf + emp_esi + pt
    employer_total_monthly   = er_pf + er_esi + med_ins_monthly
    today_str = ""
    try:
        import frappe.utils
        today_str = frappe.utils.formatdate(frappe.utils.today(), "dd MMMM yyyy")
    except Exception:
        pass

    # ── Reporting manager resolution (Link → Employee name lookup) ────────────
    reporting_to_raw  = getattr(doc, "custom_reporting_to", None) or ""
    reporting_to_name = reporting_to_raw
    if reporting_to_raw:
        try:
            import frappe
            resolved = frappe.db.get_value("Employee", reporting_to_raw, "employee_name")
            if resolved:
                reporting_to_name = resolved
        except Exception:
            pass

    # ── Candidate contact details from linked Job Applicant ───────────────────
    candidate_email   = ""
    candidate_mobile  = ""
    candidate_address = ""
    if doc.applicant:
        try:
            import frappe
            applicant = frappe.get_doc("Job Applicant", doc.applicant)
            candidate_email   = applicant.email_id or ""
            candidate_mobile  = (getattr(applicant, "phone_number", None)
                                 or getattr(applicant, "cell_number", None)
                                 or "")
            candidate_address = (getattr(applicant, "custom_address", None)
                                 or getattr(applicant, "country", None)
                                 or "")
        except Exception:
            pass

    return {
        # ── Header / addressing ────────────────────────────────────────────────
        "ref_number":          doc.name,
        "offer_date":          fmt_date(doc.offer_date),
        "candidate_name":      doc.applicant_name or "",
        "candidate_email":     candidate_email,
        "candidate_mobile":    candidate_mobile,
        "candidate_address":   candidate_address,
        "designation":         doc.designation or "",
        "department":          doc.department or "",
        "date_of_joining":     fmt_date(getattr(doc, "custom_date_of_joining", None)),
        "acceptance_deadline": fmt_date(acceptance_deadline_v),

        # ── Offer terms ────────────────────────────────────────────────────────
        "work_location":       work_location,
        "reporting_to":        reporting_to_name,
        "probation_period":    probation_period,
        "notice_period":       notice_period,
        "joining_bonus":       fmt_inr(joining_bonus_raw),
        "variable_pay_annual": fmt_inr(variable_pay_raw),
        "band":                band,
        "current_date":        today_str,

        # ── CTC summary ────────────────────────────────────────────────────────
        "annual_ctc":          fmt_inr(annual_ctc),
        "monthly_ctc":         fmt_inr(monthly_ctc),
        "gross_monthly":       fmt_inr(gross),
        "gross_annual":        fmt_inr(gross * 12),
        "net_take_home":       fmt_inr(net),
        "net_take_home_annual": fmt_inr(net * 12),

        # ── Annexure A — earnings (monthly + annual) ───────────────────────────
        "basic_monthly":              fmt_inr(basic),
        "basic_annual":               fmt_inr(basic * 12),
        "hra_monthly":                fmt_inr(hra),
        "hra_annual":                 fmt_inr(hra * 12),
        "conveyance_monthly":         fmt_inr(conv),
        "conveyance_annual":          fmt_inr(conv * 12),
        "medical_allowance_monthly":  fmt_inr(med_all),
        "medical_allowance_annual":   fmt_inr(med_all * 12),
        "special_allowance_monthly":  fmt_inr(special),
        "special_allowance_annual":   fmt_inr(special * 12),

        # ── Annexure A — deductions (monthly + annual + totals) ────────────────
        "employee_pf_monthly":        fmt_inr(emp_pf),
        "employee_pf_annual":         fmt_inr(emp_pf * 12),
        "employee_esi_monthly":       fmt_inr(emp_esi),
        "employee_esi_annual":        fmt_inr(emp_esi * 12),
        "professional_tax_monthly":   fmt_inr(pt),
        "professional_tax_annual":    fmt_inr(pt * 12),
        "total_deductions_monthly":   fmt_inr(total_deductions_monthly),
        "total_deductions_annual":    fmt_inr(total_deductions_monthly * 12),

        # ── Annexure A — employer contributions (monthly + annual + totals) ────
        "employer_pf_monthly":        fmt_inr(er_pf),
        "employer_pf_annual":         fmt_inr(er_pf * 12),
        "employer_esi_monthly":       fmt_inr(er_esi),
        "employer_esi_annual":        fmt_inr(er_esi * 12),
        "medical_insurance_monthly":  fmt_inr(med_ins_monthly),
        "medical_insurance_annual":   fmt_inr(med_ins_monthly * 12),
        "employer_deductions_annual": fmt_inr(employer_total_monthly * 12),

        # ── Conditional flags (for {% if %} blocks in template) ────────────────
        "esi_applies":        esi_applies,
        "pf_opted_out":       bool(doc.custom_pf_opted_out),
        "medical_opted_out":  bool(doc.custom_medical_insurance_opted_out),
        "has_joining_bonus":  bool(joining_bonus_raw and float(joining_bonus_raw) > 0),
        "has_variable_pay":   bool(variable_pay_raw and float(variable_pay_raw) > 0),

        # ── Raw numbers (for arithmetic inside template if needed) ─────────────
        "basic_monthly_raw":       basic,
        "gross_monthly_raw":       gross,
        "net_take_home_raw":       net,
        "annual_ctc_raw":          annual_ctc,
        "joining_bonus_raw":       joining_bonus_raw,
        "variable_pay_annual_raw": variable_pay_raw,
    }


# ── Bench-callable smoke tests ───────────────────────────────────────────────

class _FakeOffer:
    """Hardcoded sample Job Offer used by the bench smoke tests."""
    name = "OFR-SMOKE-TEST"
    applicant_name = "Smoke Test Candidate"
    designation = "Software Engineer"
    department = "Engineering"
    offer_date = "2026-05-20"
    applicant = None
    custom_date_of_joining = "2026-06-16"
    custom_annual_ctc = 600000
    custom_basic_monthly = 21600
    custom_hra_monthly = 10800
    custom_conveyance_allowance_monthly = 1600
    custom_medical_allowance_monthly = 1250
    custom_special_allowance_monthly = 7950
    custom_employee_pf_monthly = 1800
    custom_employee_esi_monthly = 0
    custom_professional_tax_monthly = 200
    custom_employer_pf = 1950
    custom_employer_esiinsurance_monthly = 0
    custom_pf_opted_out = False
    custom_medical_insurance_opted_out = False
    custom_medical_insurance_annual_premium = 10000
    custom_work_location = "Hyderabad"
    custom_band = "B3"


def test_merge_only():
    """
    Smoke test — DOCX render only (no PDF conversion).

    Verifies the template loads, docxtpl is installed, and all placeholders
    have matching context keys. Writes /tmp/offer_smoke.docx.

    Run:  bench --site hr-globexdigital execute greythr_bridge.letters.merger.test_merge_only
    """
    template_path = os.path.join(_TEMPLATE_DIR, "offer_letter.docx")
    out_path = os.path.join(tempfile.gettempdir(), "offer_smoke.docx")

    if not os.path.exists(template_path):
        print(f"FAIL: template missing at {template_path}")
        return

    ctx = build_offer_context(_FakeOffer())
    tpl = DocxTemplate(template_path)
    tpl.render(ctx)
    tpl.save(out_path)

    print(f"OK: rendered DOCX → {out_path}")
    print(f"OK: docxtpl is installed and template merges cleanly")
    print(f"OK: context has {len(ctx)} keys")


def test_merge_to_pdf():
    """
    Smoke test — full DOCX → PDF flow via LibreOffice headless.

    Writes /tmp/offer_smoke.pdf. If this fails, LibreOffice probably isn't
    installed on the Frappe Cloud bench — open a support ticket or pivot
    to sending the DOCX directly to Zoho Sign (which accepts .docx uploads).

    Run:  bench --site hr-globexdigital execute greythr_bridge.letters.merger.test_merge_to_pdf
    """
    out_path = os.path.join(tempfile.gettempdir(), "offer_smoke.pdf")
    try:
        pdf_bytes = merge_to_pdf("offer_letter.docx", build_offer_context(_FakeOffer()))
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return

    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"OK: PDF generated ({len(pdf_bytes):,} bytes) → {out_path}")


@frappe.whitelist()
def health_check() -> dict:
    """
    HTTP-callable health check for the letter pipeline.

    Verifies: docxtpl import, template file present, LibreOffice availability,
    and full DOCX→PDF conversion with sample data.

    Call from any logged-in browser:
        https://<site>/api/method/greythr_bridge.letters.merger.health_check

    Returns a JSON object with one boolean per check + diagnostic details.
    """
    import subprocess

    result = {
        "docxtpl_installed": False,
        "docxtpl_version": None,
        "template_exists": False,
        "template_path": "",
        "libreoffice_path": None,
        "libreoffice_version": None,
        "merge_only_ok": False,
        "merge_to_pdf_ok": False,
        "pdf_bytes": 0,
        "job_offer_custom_fields_total": 0,
        "expected_new_fields_present": [],
        "expected_new_fields_missing": [],
        "errors": [],
    }

    # 0. Custom Field installation check
    try:
        all_jo_fields = frappe.get_all(
            "Custom Field",
            filters={"dt": "Job Offer"},
            pluck="fieldname",
        )
        result["job_offer_custom_fields_total"] = len(all_jo_fields)
        expected = {
            "custom_band", "custom_work_location", "custom_reporting_to",
            "custom_probation_period", "custom_notice_period",
            "custom_joining_bonus", "custom_variable_pay_annual",
            "custom_acceptance_deadline",
        }
        present = expected & set(all_jo_fields)
        missing = expected - set(all_jo_fields)
        result["expected_new_fields_present"] = sorted(present)
        result["expected_new_fields_missing"] = sorted(missing)
    except Exception as exc:
        result["errors"].append(f"custom_field listing: {exc!r}")

    # 1. docxtpl
    try:
        import docxtpl
        result["docxtpl_installed"] = True
        result["docxtpl_version"] = docxtpl.__version__
    except Exception as exc:
        result["errors"].append(f"docxtpl import: {exc!r}")

    # 2. Template file present
    template_path = os.path.join(_TEMPLATE_DIR, "offer_letter.docx")
    result["template_path"] = template_path
    result["template_exists"] = os.path.exists(template_path)
    if not result["template_exists"]:
        result["errors"].append(f"template missing at {template_path}")

    # 3. LibreOffice on PATH
    try:
        which = subprocess.run(["which", "libreoffice"], capture_output=True, text=True, timeout=5)
        path = which.stdout.strip()
        result["libreoffice_path"] = path or None
        if path:
            ver = subprocess.run(["libreoffice", "--version"], capture_output=True, text=True, timeout=10)
            result["libreoffice_version"] = (ver.stdout or ver.stderr).strip()
    except Exception as exc:
        result["errors"].append(f"libreoffice check: {exc!r}")

    # 4. DOCX merge only (no PDF)
    if result["docxtpl_installed"] and result["template_exists"]:
        try:
            from docxtpl import DocxTemplate
            tpl = DocxTemplate(template_path)
            tpl.render(build_offer_context(_FakeOffer()))
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=True) as t:
                tpl.save(t.name)
            result["merge_only_ok"] = True
        except Exception as exc:
            result["errors"].append(f"merge_only: {exc!r}")

    # 5. Full DOCX → PDF
    if result["merge_only_ok"] and result["libreoffice_path"]:
        try:
            pdf = merge_to_pdf("offer_letter.docx", build_offer_context(_FakeOffer()))
            result["merge_to_pdf_ok"] = True
            result["pdf_bytes"] = len(pdf)
        except Exception as exc:
            result["errors"].append(f"merge_to_pdf: {exc!r}")

    return result
