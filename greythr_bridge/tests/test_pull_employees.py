"""
Tests for tasks/pull_employees.py — mocked HTTP and frappe ORM.
"""
import pytest
import responses as rsps_lib
from unittest.mock import MagicMock, patch, call

from greythr_bridge.tasks.pull_employees import _sync_one, _pull
from greythr_bridge.mappers.employee_mapper import greythr_to_frappe


# ── fixtures ───────────────────────────────────────────────────────────────────

def _emp(overrides=None):
    base = {
        "employeeId": "E001",
        "employeeNo": "G001",
        "firstName": "Ravi",
        "lastName": "Kumar",
        "email": "ravi@globexdigital.ai",
        "dateOfJoin": "01-06-2023",
        "leavingDate": None,
    }
    return {**base, **(overrides or {})}


# ── _sync_one: new employee created ───────────────────────────────────────────

def test_new_employee_is_created(patch_frappe):
    patch_frappe.get_all.return_value = []  # no mapping, no email match, no emp_no match

    result = _sync_one(_emp())

    assert result == "created"
    # Employee doc was created (mapping doc insert also runs — check by call args)
    employee_creates = [
        c for c in patch_frappe.new_doc.call_args_list if c == call("Employee")
    ]
    assert len(employee_creates) == 1


# ── _sync_one: existing employee updated ──────────────────────────────────────

def test_existing_employee_updated_via_mapping(patch_frappe):
    # Mapping exists → returns existing employee
    patch_frappe.get_all.side_effect = [
        [{"frappe_employee": "EMP-0001"}],  # mapping found
        [{"name": "EMP-0001"}],             # mapping upsert check
    ]
    existing = MagicMock()
    existing.get.return_value = None  # all fields differ → triggers save
    patch_frappe.get_doc.return_value = existing

    result = _sync_one(_emp())

    assert result == "updated"
    # save called at least once (employee update + mapping upsert both call save on same mock)
    assert existing.save.called


# ── _sync_one: matched but nothing to change → "skipped" (counter-honesty fix) ──

# ── _values_differ: type-aware comparison ─────────────────────────────────────

def test_values_differ_date_object_equals_iso_string():
    """Regression: Frappe returns Date fields as Python date objects, mapper
    produces ISO strings. Naïve != returns True (different types), causing
    sync to save() every run with no actual changes."""
    from datetime import date, datetime
    from greythr_bridge.tasks.pull_employees import _values_differ

    # Same value, different types → must compare as equal
    assert _values_differ(date(2024, 1, 2), "2024-01-02") is False
    assert _values_differ(datetime(2026, 5, 23, 12, 30, 0),
                          "2026-05-23 12:30:00") is False


def test_values_differ_both_none_equal():
    from greythr_bridge.tasks.pull_employees import _values_differ
    assert _values_differ(None, None) is False


def test_values_differ_one_none_differs():
    from greythr_bridge.tasks.pull_employees import _values_differ
    assert _values_differ(None, "value") is True
    assert _values_differ("value", None) is True


def test_values_differ_different_strings():
    from greythr_bridge.tasks.pull_employees import _values_differ
    assert _values_differ("Active", "Left") is True


def test_values_differ_same_strings():
    from greythr_bridge.tasks.pull_employees import _values_differ
    assert _values_differ("Active", "Active") is False


def test_values_differ_different_dates_differ():
    from datetime import date
    from greythr_bridge.tasks.pull_employees import _values_differ
    assert _values_differ(date(2024, 1, 2), "2024-09-02") is True


def test_existing_employee_no_changes_returns_skipped(patch_frappe):
    """When all mapped fields match the existing Frappe record, the function
    must return 'skipped' — NOT 'updated'. The old behaviour returned
    'updated' regardless and produced misleading sync log counts (the
    '340 updated but 0 enriched' bug discovered 2026-05-23)."""
    patch_frappe.get_all.side_effect = [
        [{"frappe_employee": "EMP-0001"}],  # mapping found
        [{"name": "EMP-0001"}],             # mapping upsert check
    ]
    existing = MagicMock()
    # Every field already matches mapped output → no changes
    def _matches(field, *_, **__):
        mapping = {
            "custom_greythr_employee_id": "E001",
            "employee_number": "G001",
            "first_name": "Ravi",
            "last_name": "Kumar",
            "company_email": "ravi@globexdigital.ai",
            "date_of_joining": "2023-06-01",
            "status": "Active",
        }
        return mapping.get(field)
    existing.get.side_effect = _matches
    patch_frappe.get_doc.return_value = existing

    result = _sync_one(_emp())

    assert result == "skipped", (
        "When mapped output matches existing record fields, _sync_one must "
        "return 'skipped' so the sync log counters reflect reality."
    )
    # Note: _upsert_mapping ALWAYS calls save (on the Mapping doc, same
    # MagicMock here). The test that the Employee save was skipped is
    # encoded in the return value being "skipped" — the function only
    # returns "updated" if `changed` was True and Employee.save() ran.


# ── _sync_one: duplicate email skipped ────────────────────────────────────────

def test_duplicate_email_returns_skipped(patch_frappe):
    patch_frappe.get_all.side_effect = [
        [],  # no mapping
        [{"name": "EMP-0001"}, {"name": "EMP-0002"}],  # two matches → duplicate
    ]

    result = _sync_one(_emp())

    assert result == "skipped"


# ── _sync_one: missing employeeId raises ──────────────────────────────────────

def test_missing_employee_id_raises(patch_frappe):
    with pytest.raises(ValueError, match="employeeId missing"):
        _sync_one({**_emp(), "employeeId": None})


# ── _pull: dry_run skips employee creation ────────────────────────────────────

def test_dry_run_makes_no_frappe_writes(patch_frappe, settings):
    settings.dry_run = True
    settings.last_employee_sync = None  # avoid MagicMock being passed as updated_after

    _pull(triggered_by="Manual")

    # No Employee documents created — only Sync Log doc is created
    employee_creates = [
        c for c in patch_frappe.new_doc.call_args_list if c == call("Employee")
    ]
    assert len(employee_creates) == 0


# ── _pull: sync log always created ────────────────────────────────────────────

def test_sync_log_created_on_every_run(patch_frappe, settings):
    settings.dry_run = True
    settings.last_employee_sync = None

    _pull(triggered_by="Scheduled")

    sync_log_creates = [
        c for c in patch_frappe.new_doc.call_args_list if c == call("greytHR Sync Log")
    ]
    assert len(sync_log_creates) == 1


# ── mapper: status from leavingDate on employee list ─────────────────────────

def test_left_status_inferred_from_leaving_date_on_list():
    emp = _emp({"leavingDate": "31-12-2023"})
    result = greythr_to_frappe(emp)
    assert result["status"] == "Left"
    assert result["relieving_date"] == "2023-12-31"


def test_active_status_when_no_leaving_date():
    result = greythr_to_frappe(_emp())
    assert result["status"] == "Active"
    assert "relieving_date" not in result
