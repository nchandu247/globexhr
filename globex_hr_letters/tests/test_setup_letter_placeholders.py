"""
Tests for tasks/setup_letter_placeholders.py — the HR repair tool that
creates the 3 placeholder records (Salary Component, Salary Structure,
Holiday List) and backfills holiday_list on all Employees.
"""
from unittest.mock import MagicMock, patch


def _setup_sysadmin(patch_frappe):
    patch_frappe.get_roles.return_value = ["System Manager"]
    patch_frappe.session.user = "admin@example.com"


# ── Role check ────────────────────────────────────────────────────────────────

def test_setup_requires_system_manager(patch_frappe):
    patch_frappe.get_roles.return_value = ["HR Manager"]
    patch_frappe.throw.side_effect = PermissionError("Only System Manager")

    from globex_hr_letters.tasks.setup_letter_placeholders import setup_letter_placeholders
    try:
        setup_letter_placeholders()
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass


# ── Idempotent creation ──────────────────────────────────────────────────────

def test_setup_creates_all_three_records_on_fresh_run(patch_frappe):
    """First run: all 3 placeholders + backfill happen."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.exists.return_value = False     # nothing exists yet
    patch_frappe.get_all.return_value = []          # no employees to backfill
    patch_frappe.defaults.get_user_default.return_value = "Globex Digital"

    from globex_hr_letters.tasks.setup_letter_placeholders import setup_letter_placeholders
    result = setup_letter_placeholders()

    assert result["salary_component_created"] is True
    assert result["salary_structure_created"] is True
    assert result["holiday_list_created"] is True
    # new_doc was called for each
    new_doc_types = [c.args[0] for c in patch_frappe.new_doc.call_args_list]
    assert "Salary Component" in new_doc_types
    assert "Salary Structure" in new_doc_types
    assert "Holiday List" in new_doc_types


def test_setup_is_idempotent(patch_frappe):
    """Second run: all records already exist → no creates, no error."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.exists.return_value = True      # everything exists
    patch_frappe.get_all.return_value = []          # no employees

    from globex_hr_letters.tasks.setup_letter_placeholders import setup_letter_placeholders
    result = setup_letter_placeholders()

    assert result["salary_component_created"] is False
    assert result["salary_structure_created"] is False
    assert result["holiday_list_created"] is False
    assert result["errors"] == []


# ── Backfill behaviour ───────────────────────────────────────────────────────

def test_setup_backfills_employees_missing_holiday_list(patch_frappe):
    """Employees without holiday_list get the default assigned;
    employees that already have one are skipped."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.exists.return_value = True      # records already exist
    # 3 employees: 2 missing, 1 already has one
    patch_frappe.get_all.return_value = [
        {"name": "GDS0001", "holiday_list": None},
        {"name": "GDS0002", "holiday_list": ""},
        {"name": "GDS0003", "holiday_list": "Calendar-Only (No Holidays)"},
    ]

    from globex_hr_letters.tasks.setup_letter_placeholders import setup_letter_placeholders
    result = setup_letter_placeholders()

    assert result["employees_backfilled"] == 2
    assert result["employees_already_set"] == 1
    # set_value was called for the 2 missing
    set_calls = [
        c for c in patch_frappe.db.set_value.call_args_list
        if c.args and c.args[0] == "Employee" and c.args[2] == "holiday_list"
    ]
    assert len(set_calls) == 2
    # Both got assigned the default Holiday List
    for c in set_calls:
        assert c.args[3] == "Calendar-Only (No Holidays)"


def test_setup_skips_backfill_if_holiday_list_record_missing(patch_frappe):
    """If the Holiday List record creation failed earlier (e.g., DB error)
    AND the record doesn't exist, the backfill must NOT proceed — otherwise
    it would set employees' holiday_list to a non-existent record FK."""
    _setup_sysadmin(patch_frappe)
    # Simulate: nothing exists, AND new_doc for Holiday List raises
    def _exists(doctype, name=None):
        return False  # nothing exists
    patch_frappe.db.exists.side_effect = _exists

    holiday_list_mock = MagicMock()
    holiday_list_mock.insert.side_effect = RuntimeError("DB unavailable")
    component_mock = MagicMock()
    structure_mock = MagicMock()

    def _new_doc(doctype):
        if doctype == "Holiday List":
            return holiday_list_mock
        if doctype == "Salary Component":
            return component_mock
        return structure_mock

    patch_frappe.new_doc.side_effect = _new_doc
    patch_frappe.defaults.get_user_default.return_value = "Globex Digital"

    from globex_hr_letters.tasks.setup_letter_placeholders import setup_letter_placeholders
    result = setup_letter_placeholders()

    # Holiday List didn't get created
    assert result["holiday_list_created"] is False
    assert any("Holiday List" in e for e in result["errors"])
    # Backfill skipped — no set_value calls for holiday_list field
    set_holiday_calls = [
        c for c in patch_frappe.db.set_value.call_args_list
        if c.args and len(c.args) > 2 and c.args[2] == "holiday_list"
    ]
    assert not set_holiday_calls, (
        "Must NOT backfill holiday_list when the Holiday List record itself "
        "doesn't exist — would create dangling FKs."
    )


# ── Salary Structure requires Company default ────────────────────────────────

def test_setup_reports_error_when_no_default_company(patch_frappe):
    """If neither user default nor Global Defaults has a company set, the
    Salary Structure creation reports a clear error without crashing."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.exists.return_value = False
    patch_frappe.get_all.return_value = []
    patch_frappe.defaults.get_user_default.return_value = None
    patch_frappe.db.get_single_value.return_value = None

    from globex_hr_letters.tasks.setup_letter_placeholders import setup_letter_placeholders
    result = setup_letter_placeholders()

    # Other records still created
    assert result["salary_component_created"] is True
    assert result["holiday_list_created"] is True
    # Salary Structure NOT created — error logged
    assert result["salary_structure_created"] is False
    assert any("Company" in e for e in result["errors"])


# ── Constants exported for hook usage ────────────────────────────────────────

def test_module_exports_default_holiday_list_constant():
    """hooks_handlers/employee.py and tasks/pull_employees.py both import
    or reference DEFAULT_HOLIDAY_LIST. Pin the name so a rename here
    cascades to a test failure."""
    from globex_hr_letters.tasks.setup_letter_placeholders import (
        DEFAULT_HOLIDAY_LIST,
        DEFAULT_SALARY_STRUCTURE,
        DEFAULT_SALARY_COMPONENT,
    )
    assert DEFAULT_HOLIDAY_LIST == "Calendar-Only (No Holidays)"
    assert DEFAULT_SALARY_STRUCTURE == "Letter Trigger Structure"
    assert DEFAULT_SALARY_COMPONENT == "CTC"
