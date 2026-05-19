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
