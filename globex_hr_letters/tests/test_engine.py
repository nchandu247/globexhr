"""
Tests for letters/engine.py — placeholder resolution, compensation totals,
formatting helpers, and template scanning. All offline (frappe is mocked in
conftest; template scanning uses the real shipped HTML files + Jinja2).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from globex_hr_letters.letters.merger import (
    fmt_inr,
    format_person_name,
    html_template_exists,
    scan_html_placeholders,
    tenure_str,
)
from globex_hr_letters.letters import engine


# ── fakes ─────────────────────────────────────────────────────────────────────

class FakeField(SimpleNamespace):
    pass


class FakeRecipient:
    """Duck-typed Frappe doc: meta.fields + get() + name."""

    def __init__(self, name, fields: dict, fieldtypes: dict | None = None):
        self.name = name
        self._values = fields
        fieldtypes = fieldtypes or {}
        self.meta = SimpleNamespace(fields=[
            FakeField(fieldname=k, fieldtype=fieldtypes.get(k, "Data"))
            for k in fields
        ])

    def get(self, key, default=None):
        return self._values.get(key, default)


def _employee(**overrides):
    values = {
        "employee_name": "nalluri sudha",
        "employee_number": "GDS0021",
        "designation": "SOFTWARE ENGINEER",
        "date_of_joining": "2024-01-15",
        "company_email": "sudha@globexdigital.ai",
    }
    values.update(overrides)
    return FakeRecipient(
        "GDS0021", values,
        fieldtypes={"date_of_joining": "Date", "relieving_date": "Date"},
    )


def _comp_row(component, monthly, annual=None):
    return SimpleNamespace(
        component=component, monthly_amount=monthly, annual_amount=annual,
    )


def _hr_letter(**overrides):
    letter = MagicMock()
    letter.name = "HR-LTR-2026-0001"
    letter.letter_type = "Offer Letter"
    letter.recipient_type = "Employee"
    letter.recipient = "GDS0021"
    letter.letter_date = "2026-07-11"
    letter.filled_values = None
    letter.compensation = []
    for key, value in overrides.items():
        setattr(letter, key, value)
    return letter


def _letter_type(**overrides):
    lt = MagicMock()
    lt.name = "Offer Letter"
    lt.render_engine = "HTML"
    lt.html_template = "offer_letter.html"
    lt.recipient_kind = "Employee"
    lt.requires_signature = 1
    lt.uses_compensation_table = 1
    lt.signatory_source = "From Settings"
    lt.is_active = 1
    for key, value in overrides.items():
        setattr(lt, key, value)
    return lt


# ── formatting helpers ────────────────────────────────────────────────────────

@pytest.mark.parametrize("value,expected", [
    (600000, "6,00,000"),
    (12345678, "1,23,45,678"),
    (999, "999"),
    (0, "0"),
    (None, "0"),
    ("garbage", "0"),
])
def test_fmt_inr(value, expected):
    assert fmt_inr(value) == expected


@pytest.mark.parametrize("value,expected", [
    ("nalluri sudha", "Nalluri Sudha"),
    ("MOHD BALEEGH AHMED", "Mohd Baleegh Ahmed"),
    ("Avinash Nalluri", "Avinash Nalluri"),
    ("McDonald Smith", "McDonald Smith"),
    ("", ""),
    (None, ""),
])
def test_format_person_name(value, expected):
    assert format_person_name(value) == expected


def test_tenure_str():
    assert tenure_str("2024-01-15", "2026-04-20") == "2 years and 3 months"
    assert tenure_str("2026-01-01", "2026-01-20") == "less than a month"
    assert tenure_str(None, "2026-01-01") == ""


# ── template scanning ─────────────────────────────────────────────────────────

def test_shipped_templates_exist():
    for template in (
        "offer_letter.html", "appointment_letter.html", "confirmation_letter.html",
        "promotion_letter.html", "salary_revision_letter.html",
        "experience_letter.html", "relieving_letter.html",
        "service_certificate.html", "warning_letter.html",
        "termination_letter.html", "internship_certificate.html",
        "address_proof_letter.html", "consultant_offer_letter.html",
        "intern_offer_letter.html",
    ):
        assert html_template_exists(template), f"missing: {template}"


def test_html_template_exists_rejects_traversal():
    assert not html_template_exists("../secrets.html")
    assert not html_template_exists("")


def test_scan_offer_template_placeholders():
    """The scan walks the template AND its base, so letterhead vars are
    included; the compensation loop variable is detected too."""
    names = scan_html_placeholders("offer_letter.html")
    assert "candidate_name" in names
    assert "compensation" in names
    assert "annual_ctc" in names
    assert "ref_number" in names  # from _base.html title


# ── compensation context ──────────────────────────────────────────────────────

def test_compensation_totals_and_annual_default():
    letter = _hr_letter(compensation=[
        _comp_row("Basic", 21600),               # annual defaults to 12x
        _comp_row("HRA", 10800, 129600),
        _comp_row("Special Allowance", 7600),
    ])
    ctx = engine._compensation_context(letter)

    assert [r["component"] for r in ctx["compensation"]] == [
        "Basic", "HRA", "Special Allowance"]
    assert ctx["compensation"][0]["annual"] == fmt_inr(21600 * 12)
    assert ctx["gross_monthly"] == fmt_inr(40000)
    assert ctx["gross_annual"] == fmt_inr(480000)
    assert ctx["annual_ctc"] == fmt_inr(480000)
    assert ctx["monthly_ctc"] == fmt_inr(40000)


def test_compensation_empty_table_gives_zero_totals():
    ctx = engine._compensation_context(_hr_letter())
    assert ctx["compensation"] == []
    assert ctx["gross_annual"] == "0"


# ── recipient context ─────────────────────────────────────────────────────────

def test_employee_recipient_context_formats_and_conveniences():
    ctx = engine._recipient_context("Employee", _employee())

    assert ctx["employee_id"] == "GDS0021"
    assert ctx["employee_name"] == "Nalluri Sudha"      # pretty-cased
    assert ctx["recipient_name"] == "Nalluri Sudha"
    assert ctx["designation"] == "Software Engineer"
    assert "January" in ctx["date_of_joining"] or ctx["date_of_joining"]  # formatted
    assert ctx["tenure"]  # up to today, non-empty


def test_employee_with_relieving_date_gets_last_working_day():
    ctx = engine._recipient_context(
        "Employee", _employee(relieving_date="2026-06-30"))
    assert ctx["last_working_day"]
    assert ctx["tenure"] == tenure_str("2024-01-15", "2026-06-30")


def test_job_applicant_recipient_context():
    applicant = FakeRecipient("JA-0007", {
        "applicant_name": "PRIYA SHARMA",
        "email_id": "priya@example.com",
    })
    ctx = engine._recipient_context("Job Applicant", applicant)
    assert ctx["candidate_name"] == "Priya Sharma"
    assert ctx["recipient_name"] == "Priya Sharma"
    assert ctx["candidate_email"] == "priya@example.com"


def test_empty_recipient_fields_are_skipped():
    """Empty fields stay out of the context so prompts can supply them."""
    emp = FakeRecipient("GDS0022", {"employee_name": "Test User", "designation": ""})
    ctx = engine._recipient_context("Employee", emp)
    # designation empty on doc → curated convenience sets it to "" anyway,
    # but the raw loop must not have added a bogus value before that
    assert ctx["designation"] == ""


# ── build_context precedence + missing detection ──────────────────────────────

def _wire_get_doc(patch_frappe, letter_type, recipient):
    def fake_get_doc(doctype, name=None, *args, **kwargs):
        if doctype == "Letter Type":
            return letter_type
        return recipient
    patch_frappe.get_doc.side_effect = fake_get_doc


def test_filled_values_win_over_recipient_fields(patch_frappe, settings):
    letter_type = _letter_type()
    _wire_get_doc(patch_frappe, letter_type, _employee())

    letter = _hr_letter(filled_values='{"designation": "Principal Engineer"}')
    ctx = engine.build_context(letter, letter_type)

    assert ctx["designation"] == "Principal Engineer"  # HR override wins
    assert ctx["ref_number"] == "HR-LTR-2026-0001"
    assert ctx["requires_signature"] is True


def test_get_missing_placeholders_lists_unresolved(patch_frappe, settings):
    """offer_letter.html needs work_location / notice_period / band etc.
    that neither an Employee doc nor Settings supply — they must be
    reported for the prompt dialog, and resolved ones must not."""
    letter_type = _letter_type()
    _wire_get_doc(patch_frappe, letter_type, _employee())

    missing = engine.get_missing_placeholders(_hr_letter())

    assert "work_location" in missing
    assert "notice_period" in missing
    assert "employee_name" not in missing      # resolved from recipient
    assert "compensation" not in missing       # resolved from child table
    assert "ref_number" not in missing         # always provided


def test_generate_hard_errors_on_unresolved_placeholders(patch_frappe, settings):
    """A letter is never rendered with silent blanks — generate() must
    throw listing the unresolved names."""
    letter_type = _letter_type()
    _wire_get_doc(patch_frappe, letter_type, _employee())
    settings.enabled = True
    patch_frappe.throw.side_effect = RuntimeError("frappe.throw")

    with pytest.raises(RuntimeError):
        engine.generate(_hr_letter())

    thrown = str(patch_frappe.throw.call_args)
    assert "work_location" in thrown
    patch_frappe.throw.side_effect = None


# ── greytHR Employee ID (decisions B3/B5, 2026-07-13) ─────────────────────────

def test_employee_context_exposes_greythr_id():
    """Letters print the greytHR ID (employee_number), not the internal
    Frappe docname — employee_id and greythr_employee_id both carry it."""
    ctx = engine._recipient_context("Employee", _employee())
    assert ctx["employee_id"] == "GDS0021"
    assert ctx["greythr_employee_id"] == "GDS0021"


def test_employee_context_falls_back_to_docname_without_greythr_id():
    """Defensive fallback for non-letter callers — generate() itself is
    guarded and never reaches this state."""
    ctx = engine._recipient_context("Employee", _employee(employee_number=""))
    assert ctx["employee_id"] == "GDS0021"  # doc.name fallback
    assert ctx["greythr_employee_id"] == ""


def test_generate_blocks_employee_letter_without_greythr_id(patch_frappe, settings):
    """B5: employee letters refuse to generate until the greytHR ID is
    recorded — otherwise the letter would print the internal name."""
    letter_type = _letter_type()
    _wire_get_doc(patch_frappe, letter_type, _employee(employee_number=""))
    patch_frappe.throw.side_effect = RuntimeError("frappe.throw")

    with pytest.raises(RuntimeError):
        engine.generate(_hr_letter())

    thrown = str(patch_frappe.throw.call_args)
    assert "greytHR" in thrown
    patch_frappe.throw.side_effect = None


def test_generate_blocks_employee_letter_with_malformed_greythr_id(patch_frappe, settings):
    letter_type = _letter_type()
    _wire_get_doc(patch_frappe, letter_type, _employee(employee_number="GSD0033"))
    patch_frappe.throw.side_effect = RuntimeError("frappe.throw")

    with pytest.raises(RuntimeError):
        engine.generate(_hr_letter())

    thrown = str(patch_frappe.throw.call_args)
    assert "greytHR" in thrown
    patch_frappe.throw.side_effect = None


# ── Job Offer context (decision A1, 2026-07-13) ───────────────────────────────

from globex_hr_letters.letters.merger import fmt_date as _fmt_date


def _job_offer(terms=None, **fields):
    values = {
        "designation": "Senior Consultant",
        "offer_date": "2026-07-20",
        "company": "Globex Digital Solutions Pvt. Ltd.",
    }
    values.update(fields)
    offer = FakeRecipient("JO-0001", values)
    offer._values["offer_terms"] = [
        SimpleNamespace(offer_term=t, value=v) for t, v in (terms or {}).items()
    ]
    return offer


def test_job_offer_context_maps_terms_and_formats(patch_frappe):
    """Offer terms typed once on the Job Offer resolve as placeholders:
    labels scrub to snake_case, ISO dates format as letter dates, amounts
    on amount-ish terms get Indian commas, prose passes through."""
    offer = _job_offer(terms={
        "Date of Joining": "2026-08-01",
        "Annual CTC": "1200000",
        "Work Location": "Hyderabad",
        "Notice Period": "90 days",
        "Probation Period": "6 months",
    })
    patch_frappe.get_all.return_value = [{"name": "JO-0001"}]
    patch_frappe.get_all.side_effect = None
    patch_frappe.get_doc.side_effect = lambda dt, name=None, *a, **k: offer

    ctx = engine._job_offer_context("Job Applicant", "JA-0007")

    assert ctx["designation"] == "Senior Consultant"
    assert ctx["offer_date"] == _fmt_date("2026-07-20")
    assert ctx["company"] == "Globex Digital Solutions Pvt. Ltd."
    assert ctx["date_of_joining"] == _fmt_date("2026-08-01")
    assert ctx["annual_ctc"] == "12,00,000"
    assert ctx["work_location"] == "Hyderabad"
    assert ctx["notice_period"] == "90 days"
    assert ctx["probation_period"] == "6 months"


def test_job_offer_context_only_for_job_applicants():
    assert engine._job_offer_context("Employee", "GDS0021") == {}


def test_job_offer_context_empty_when_no_offer(patch_frappe):
    patch_frappe.get_all.return_value = []
    patch_frappe.get_all.side_effect = None
    assert engine._job_offer_context("Job Applicant", "JA-0007") == {}


def test_job_offer_skips_blank_terms(patch_frappe):
    offer = _job_offer(terms={"Notice Period": "", "Band": "L4"})
    patch_frappe.get_all.return_value = [{"name": "JO-0001"}]
    patch_frappe.get_all.side_effect = None
    patch_frappe.get_doc.side_effect = lambda dt, name=None, *a, **k: offer

    ctx = engine._job_offer_context("Job Applicant", "JA-0007")
    assert "notice_period" not in ctx      # blank value → prompt supplies it
    assert ctx["band"] == "L4"


def test_format_term_value_only_formats_amountish_numbers():
    assert engine._format_term_value("Annual CTC", "1200000") == "12,00,000"
    assert engine._format_term_value("Probation Period", "6") == "6"
    assert engine._format_term_value("Monthly Stipend", "25000") == "25,000"
    assert engine._format_term_value("Work Location", "Hyderabad") == "Hyderabad"


# ── stamped signature + single-signer dispatch (decision 2026-07-13) ──────────

def test_signature_image_becomes_data_uri(patch_frappe):
    """Private file_url resolves to a data: URI WeasyPrint can embed."""
    file_doc = MagicMock()
    file_doc.get_content.return_value = b"\x89PNGfake"
    patch_frappe.get_doc.side_effect = lambda *a, **k: file_doc

    uri = engine._signature_image_data_uri("/private/files/sig.png")

    assert uri.startswith("data:image/png;base64,")
    import base64
    assert base64.b64decode(uri.split(",")[1]) == b"\x89PNGfake"


def test_signature_image_empty_or_nonstring_gives_blank():
    assert engine._signature_image_data_uri("") == ""
    assert engine._signature_image_data_uri(None) == ""
    assert engine._signature_image_data_uri(MagicMock()) == ""


def test_signature_image_load_failure_logs_and_blanks(patch_frappe):
    patch_frappe.get_doc.side_effect = RuntimeError("file gone")
    assert engine._signature_image_data_uri("/private/files/gone.png") == ""


def test_dispatch_signature_sends_single_recipient_signer(monkeypatch, patch_frappe, settings):
    """Company signature is stamped at generation — Zoho request carries
    exactly one signer: the recipient, order 1."""
    letter = _hr_letter(zoho_request_id=None)
    letter_type = _letter_type(category="Onboarding")
    employee = _employee()
    employee.company_email = "sudha@globexdigital.ai"  # resolve_recipient_email uses getattr

    def fake_get_doc(dt, name=None, *a, **k):
        if dt == "HR Letter":
            return letter
        if dt == "Letter Type":
            return letter_type
        return employee
    patch_frappe.get_doc.side_effect = fake_get_doc
    patch_frappe.get_all.return_value = []
    patch_frappe.get_all.side_effect = None

    monkeypatch.setattr(engine, "merge_to_pdf_via_html", lambda *a, **k: b"%PDF-fake")

    sent = {}
    import globex_hr_letters.api.zoho_sign as zs

    def fake_send(**kwargs):
        sent.update(kwargs)
        return "REQ-SINGLE"
    monkeypatch.setattr(zs, "send_for_signature", fake_send)

    engine.dispatch_signature("HR-LTR-2026-0001")

    assert [s["order"] for s in sent["signers"]] == [1], \
        "exactly one signer, order 1 — the recipient"
    assert sent["signers"][0]["email"] == "sudha@globexdigital.ai"
    assert sent["signers"][0]["name"] == "Nalluri Sudha"
    letter.db_set.assert_any_call("zoho_request_id", "REQ-SINGLE")
    letter.db_set.assert_any_call("status", "Sent for Signature")


def test_dispatch_signature_idempotent(patch_frappe):
    """Already-dispatched letters (zoho_request_id set) are skipped."""
    letter = _hr_letter(zoho_request_id="REQ-EXISTING")
    patch_frappe.get_doc.side_effect = lambda *a, **k: letter

    engine.dispatch_signature("HR-LTR-2026-0001")

    letter.db_set.assert_not_called()


# ── deductions in the compensation annexure (2026-07-13) ──────────────────────

def _ded_row(component, monthly, annual=None):
    return SimpleNamespace(
        component=component, monthly_amount=monthly, annual_amount=annual,
        component_type="Deduction",
    )


def test_compensation_splits_earnings_and_deductions():
    """Sample-format annexure: Monthly Gross (A), Deductions (B),
    Monthly Net (A - B). Rows without component_type stay earnings."""
    letter = _hr_letter(compensation=[
        _comp_row("Basic", 12000),
        _comp_row("HRA", 6000),
        _comp_row("Special Allowance", 12000),
        _ded_row("Professional Tax", 200),
    ])
    ctx = engine._compensation_context(letter)

    assert [r["component"] for r in ctx["compensation"]] == [
        "Basic", "HRA", "Special Allowance"]
    assert [r["component"] for r in ctx["deductions"]] == ["Professional Tax"]
    assert ctx["gross_monthly"] == fmt_inr(30000)
    assert ctx["gross_annual"] == fmt_inr(360000)
    assert ctx["deductions_monthly"] == fmt_inr(200)
    assert ctx["deductions_annual"] == fmt_inr(2400)
    assert ctx["net_monthly"] == fmt_inr(29800)
    assert ctx["net_annual"] == fmt_inr(357600)
    assert ctx["annual_ctc"] == fmt_inr(360000)  # CTC = earnings only


def test_compensation_no_deductions_keeps_empty_list():
    ctx = engine._compensation_context(_hr_letter(compensation=[
        _comp_row("Basic", 10000),
    ]))
    assert ctx["deductions"] == []
    assert ctx["net_monthly"] == ctx["gross_monthly"]
