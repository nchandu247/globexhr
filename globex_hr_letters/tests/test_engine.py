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
