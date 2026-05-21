"""
Tests for the DOCX letter merger.

These tests run without Frappe — they mock the frappe module.
"""
import os
import sys
import types
import unittest
from unittest.mock import MagicMock, patch


# ── Minimal frappe stub so merger.py can be imported offline ──────────────────
_frappe = types.ModuleType("frappe")
_frappe.throw = lambda msg, title=None: (_ for _ in ()).throw(ValueError(msg))
_frappe.utils = types.SimpleNamespace(
    formatdate=lambda v, fmt: str(v)
)
sys.modules.setdefault("frappe", _frappe)
sys.modules.setdefault("frappe.utils", _frappe.utils)

# Stub docxtpl
_docxtpl = types.ModuleType("docxtpl")
_docxtpl.DocxTemplate = MagicMock()
sys.modules.setdefault("docxtpl", _docxtpl)

from greythr_bridge.letters.merger import build_offer_context  # noqa: E402


class FakeDoc:
    """Minimal Job Offer document stub."""
    name = "OFR-2025-TEST"
    applicant_name = "Test Candidate"
    designation = "Software Engineer"
    department = "Engineering"
    offer_date = "2025-06-01"
    job_applicant = None
    applicant_email = "test.candidate@example.com"
    custom_date_of_joining = "2025-06-16"
    custom_annual_ctc = 600000
    custom_basic_monthly = 21600      # 50% of ~43200 gross
    custom_hra_monthly = 10800        # 50% of basic
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
    # Optional offer terms
    custom_work_location = "Hyderabad"
    custom_reporting_to = ""
    custom_probation_period = "6 months"
    custom_notice_period = "60 days"
    custom_joining_bonus = 50000
    custom_variable_pay_annual = 0
    custom_acceptance_deadline = "2025-06-10"


class TestBuildOfferContext(unittest.TestCase):

    def setUp(self):
        self.ctx = build_offer_context(FakeDoc())

    def test_candidate_name_present(self):
        self.assertEqual(self.ctx["candidate_name"], "Test Candidate")

    def test_gross_computed_from_components(self):
        expected_gross = 21600 + 10800 + 1600 + 1250 + 7950  # 43200
        self.assertEqual(self.ctx["gross_monthly_raw"], expected_gross)

    def test_net_computed_correctly(self):
        gross = 43200
        deductions = 1800 + 0 + 200  # pf + esi + pt
        self.assertEqual(self.ctx["net_take_home_raw"], gross - deductions)

    def test_inr_formatting_bare_no_symbol(self):
        # gross_monthly should be a bare number (no ₹) in Indian comma format
        self.assertNotIn("₹", self.ctx["gross_monthly"])
        self.assertEqual(self.ctx["gross_monthly"], "43,200")

    def test_indian_comma_formatting_for_lakhs(self):
        # 600000 → 6,00,000 (Indian style, not Western 600,000)
        self.assertEqual(self.ctx["annual_ctc"], "6,00,000")

    def test_esi_flag(self):
        # Gross 43200 > 21000 → ESI does not apply
        self.assertFalse(self.ctx["esi_applies"])

    def test_medical_insurance_included_when_esi_not_applicable(self):
        # ESI doesn't apply, medical not opted out → med_ins_monthly = 10000/12 = 833
        self.assertEqual(self.ctx["medical_insurance_monthly"], "833")

    def test_annual_values_computed_as_monthly_times_12(self):
        self.assertEqual(self.ctx["basic_annual"], "2,59,200")  # 21600 * 12
        self.assertEqual(self.ctx["hra_annual"], "1,29,600")    # 10800 * 12
        self.assertEqual(self.ctx["gross_annual"], "5,18,400")  # 43200 * 12

    def test_total_deductions(self):
        # emp_pf(1800) + emp_esi(0) + pt(200) = 2000 monthly, 24000 annually
        self.assertEqual(self.ctx["total_deductions_monthly"], "2,000")
        self.assertEqual(self.ctx["total_deductions_annual"], "24,000")

    def test_band_passthrough(self):
        # FakeDoc has no custom_band → default empty string
        self.assertEqual(self.ctx["band"], "")

    def test_all_required_keys_present(self):
        required = [
            # header / addressing
            "ref_number", "offer_date", "current_date", "candidate_name",
            "candidate_email", "candidate_mobile", "candidate_address",
            "designation", "department", "band", "date_of_joining",
            "acceptance_deadline",
            # offer terms
            "work_location", "reporting_to", "probation_period", "notice_period",
            "joining_bonus", "variable_pay_annual",
            # CTC summary
            "annual_ctc", "monthly_ctc",
            "gross_monthly", "gross_annual",
            "net_take_home", "net_take_home_annual",
            # earnings monthly + annual
            "basic_monthly", "basic_annual",
            "hra_monthly", "hra_annual",
            "conveyance_monthly", "conveyance_annual",
            "medical_allowance_monthly", "medical_allowance_annual",
            "special_allowance_monthly", "special_allowance_annual",
            # employee deductions
            "employee_pf_monthly", "employee_pf_annual",
            "employee_esi_monthly", "employee_esi_annual",
            "professional_tax_monthly", "professional_tax_annual",
            "total_deductions_monthly", "total_deductions_annual",
            # employer contributions
            "employer_pf_monthly", "employer_pf_annual",
            "employer_esi_monthly", "employer_esi_annual",
            "medical_insurance_monthly", "medical_insurance_annual",
            "employer_deductions_annual",
            # flags
            "esi_applies", "pf_opted_out", "medical_opted_out",
            "has_joining_bonus", "has_variable_pay",
        ]
        for key in required:
            self.assertIn(key, self.ctx, f"Missing context key: {key}")

    def test_offer_terms_passthrough(self):
        self.assertEqual(self.ctx["work_location"], "Hyderabad")
        self.assertEqual(self.ctx["probation_period"], "6 months")
        self.assertEqual(self.ctx["notice_period"], "60 days")

    def test_joining_bonus_flag_set_when_amount_positive(self):
        self.assertTrue(self.ctx["has_joining_bonus"])
        self.assertEqual(self.ctx["joining_bonus"], "50,000")

    def test_variable_pay_flag_false_when_zero(self):
        self.assertFalse(self.ctx["has_variable_pay"])
        self.assertEqual(self.ctx["variable_pay_annual"], "0")

    def test_candidate_email_read_directly_from_job_offer(self):
        """Email should come from doc.applicant_email — no Job Applicant fetch needed."""
        self.assertEqual(self.ctx["candidate_email"], "test.candidate@example.com")

    def test_no_attribute_error_when_optional_fields_missing(self):
        """
        Regression test for 'JobOffer object has no attribute applicant'.
        Doc with no candidate-link / no opt-out flags should still produce
        a full context, not raise.
        """
        class MinimalDoc:
            name = "OFR-MIN"
            applicant_name = "Min Candidate"
            designation = "Eng"
            offer_date = "2025-06-01"
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
            # NO job_applicant, applicant_email, department, opt-out flags

        ctx = build_offer_context(MinimalDoc())
        self.assertEqual(ctx["candidate_email"], "")
        self.assertEqual(ctx["department"], "")
        self.assertFalse(ctx["pf_opted_out"])
        self.assertFalse(ctx["medical_opted_out"])

    def test_defaults_when_custom_fields_missing(self):
        """When optional custom fields aren't on the doc at all, defaults apply."""
        class BareDoc:
            name = "OFR-BARE"
            applicant_name = "Bare Candidate"
            designation = "Engineer"
            department = ""
            offer_date = "2025-06-01"
            job_applicant = None
            applicant_email = ""
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
            # Note: NO optional offer-term attrs defined

        ctx = build_offer_context(BareDoc())
        self.assertEqual(ctx["work_location"], "Hyderabad")
        self.assertEqual(ctx["probation_period"], "6 months")
        self.assertEqual(ctx["notice_period"], "60 days")
        self.assertEqual(ctx["joining_bonus"], "0")
        self.assertFalse(ctx["has_joining_bonus"])
        self.assertEqual(ctx["reporting_to"], "")
        self.assertEqual(ctx["acceptance_deadline"], "")


class TestAppendZohoSignatureTags(unittest.TestCase):
    """
    Verify _append_zoho_signature_tags() injects Zoho text tags into a real
    DOCX so /submit doesn't fail with error 9101 'Add atleast one field for
    a signer'.
    """

    def test_appends_signature_tags_for_both_signers(self):
        import tempfile
        from docx import Document
        from greythr_bridge.letters.merger import _append_zoho_signature_tags

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            doc = Document()
            doc.add_paragraph("Existing content")
            doc.save(tmp_path)

            _append_zoho_signature_tags(tmp_path)

            result = Document(tmp_path)
            all_text = "\n".join(p.text for p in result.paragraphs)
            self.assertIn("{{S:R1*}}", all_text,
                          "Signer 1 mandatory signature tag missing")
            self.assertIn("{{S:R2*}}", all_text,
                          "Signer 2 mandatory signature tag missing")
            self.assertIn("Existing content", all_text,
                          "Original content was destroyed")
        finally:
            os.unlink(tmp_path)

    def test_signature_tags_are_white_invisible(self):
        """
        Regression: tags were visible in black 8pt in the first signed PDF.
        Should now be white = invisible on white page (Zoho still parses text).
        """
        import tempfile
        from docx import Document
        from docx.shared import RGBColor
        from greythr_bridge.letters.merger import _append_zoho_signature_tags

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            doc = Document()
            doc.save(tmp_path)
            _append_zoho_signature_tags(tmp_path)

            result = Document(tmp_path)
            # Find the paragraph containing the tags
            tag_para = None
            for p in result.paragraphs:
                if "{{S:R1*}}" in p.text:
                    tag_para = p
                    break
            self.assertIsNotNone(tag_para, "Tag paragraph not found")
            self.assertTrue(len(tag_para.runs) > 0, "Tag paragraph has no runs")
            color = tag_para.runs[0].font.color.rgb
            self.assertEqual(
                color, RGBColor(0xFF, 0xFF, 0xFF),
                f"Expected white (FFFFFF), got {color}",
            )
        finally:
            os.unlink(tmp_path)


class TestOfferContextDateOfJoining(unittest.TestCase):
    """Verify build_offer_context picks up custom_date_of_joining correctly."""

    def test_doj_truthy_when_set(self):
        """When DOJ is set on the doc, context's date_of_joining is non-empty."""
        ctx = build_offer_context(FakeDoc())
        # Note: actual format depends on frappe.utils.formatdate (not under test).
        # We just verify the field flows through to the context.
        self.assertTrue(
            ctx["date_of_joining"],
            "date_of_joining should be non-empty when custom_date_of_joining is set",
        )

    def test_doj_blank_when_missing(self):
        class NoDOJDoc:
            name = "OFR-NODOJ"
            applicant_name = "X"
            designation = "Y"
            offer_date = "2025-06-01"
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
            # No custom_date_of_joining attribute at all

        ctx = build_offer_context(NoDOJDoc())
        self.assertEqual(
            ctx["date_of_joining"], "",
            "date_of_joining should be empty string when field missing",
        )


class TestBuildScriptPolish(unittest.TestCase):
    """
    Verify the polish passes in scripts/build_offer_template.py:
    - Fix 'Hi .{{ candidate_name }}' → 'Hi {{ candidate_name }}'
    - Insert reporting-manager paragraph after the joining sentence
    """

    def _make_fixture_docx(self, with_hi_dot=True, with_joining=True):
        """Create a tiny fixture DOCX containing the patterns we polish."""
        import tempfile
        from docx import Document
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            path = tmp.name
        doc = Document()
        if with_hi_dot:
            doc.add_paragraph("Hi .{{ candidate_name }},")
        doc.add_paragraph("Dear {{ candidate_name }},")
        if with_joining:
            doc.add_paragraph(
                "We are eager for you to join us as early as possible, "
                "ideally by {{ date_of_joining }}."
            )
        doc.add_paragraph("Yours sincerely,")
        doc.save(path)
        return path

    def test_fix_hi_dot_salutation(self):
        from docx import Document
        # Import the build module
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_offer_template",
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_offer_template.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        src = self._make_fixture_docx()
        dst = src.replace(".docx", "_out.docx")
        try:
            stats = mod.build(src, dst)
            self.assertGreaterEqual(stats["salutation_fixes"], 1,
                                    "Expected at least 1 'Hi .' fix")
            result = Document(dst)
            all_text = "\n".join(p.text for p in result.paragraphs)
            self.assertNotIn("Hi .{{", all_text, "'Hi .' pattern still present")
            self.assertIn("Hi {{ candidate_name }}", all_text,
                          "Fixed 'Hi ' salutation missing")
        finally:
            os.unlink(src)
            if os.path.exists(dst):
                os.unlink(dst)

    def test_inject_reporting_manager_line(self):
        from docx import Document
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_offer_template",
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_offer_template.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        src = self._make_fixture_docx()
        dst = src.replace(".docx", "_out.docx")
        try:
            stats = mod.build(src, dst)
            self.assertEqual(stats["reporting_manager_inserted"], 1,
                             "Expected exactly 1 reporting-manager line")
            result = Document(dst)
            all_text = "\n".join(p.text for p in result.paragraphs)
            self.assertIn("{% if reporting_to %}", all_text,
                          "Jinja conditional missing")
            self.assertIn("You will report to {{ reporting_to }}", all_text,
                          "Reporting manager sentence missing")
            self.assertIn("{% endif %}", all_text, "endif missing")
        finally:
            os.unlink(src)
            if os.path.exists(dst):
                os.unlink(dst)


if __name__ == "__main__":
    unittest.main()
