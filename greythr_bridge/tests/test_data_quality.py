"""
Tests for utils/data_quality.py — Phase 1 read-only Employee audit.

Critical invariant verified by every test: the audit endpoint NEVER
writes to the database. No frappe.db.set_value, no frappe.new_doc,
no frappe.delete_doc, no frappe.db.sql with anything but SELECT.

See docs/superpowers/specs/2026-05-23-employee-data-integrity-plan.md
"""
from unittest.mock import MagicMock


def _setup_audit_role(patch_frappe):
    """Grant the HR Manager role to the current test user."""
    patch_frappe.get_roles.return_value = ["HR Manager"]
    patch_frappe.session.user = "test_hr_manager@example.com"


def test_list_ghost_employees_categorises_correctly(patch_frappe):
    """Three buckets: ghosts (blank first_name), mapped_clean (has first_name
    AND mapping), frappe_only (has first_name, no mapping)."""
    _setup_audit_role(patch_frappe)

    # Frappe.get_all called 3 times: ghosts, employees_with_data, mappings
    ghosts_response = [
        {"name": "HR-EMP-00684", "employee_number": "",
         "custom_greythr_employee_id": "gth-xyz",
         "company_email": "", "status": "Active",
         "custom_greythr_last_synced": None,
         "creation": "2025-01-01", "owner": "Administrator"},
    ]
    employees_with_data_response = [
        {"name": "HR-EMP-00100", "first_name": "Rohan", "last_name": "Kumar",
         "employee_number": "GDS0100",
         "custom_greythr_employee_id": "gth-100",
         "company_email": "rohan@globex.com", "status": "Active",
         "custom_greythr_last_synced": "2026-05-23"},
        {"name": "HR-EMP-00200", "first_name": "Manual", "last_name": "Entry",
         "employee_number": "", "custom_greythr_employee_id": "",
         "company_email": "manual@globex.com", "status": "Active",
         "custom_greythr_last_synced": None},
    ]
    mappings_response = [{"frappe_employee": "HR-EMP-00100"}]

    patch_frappe.get_all.side_effect = [
        ghosts_response,
        employees_with_data_response,
        mappings_response,
    ]

    from greythr_bridge.utils.data_quality import list_ghost_employees
    result = list_ghost_employees()

    # Categorisation correct
    assert result["summary"]["total_employees"] == 3
    assert result["summary"]["ghosts"] == 1
    assert result["summary"]["mapped_clean"] == 1
    assert result["summary"]["frappe_only"] == 1
    assert result["summary"]["total_mappings"] == 1

    assert result["ghosts"][0]["name"] == "HR-EMP-00684"
    assert result["mapped_clean"][0]["name"] == "HR-EMP-00100"
    assert result["frappe_only"][0]["name"] == "HR-EMP-00200"


def test_list_ghost_employees_does_not_write_to_db(patch_frappe):
    """Critical invariant: audit MUST NOT call any write method."""
    _setup_audit_role(patch_frappe)
    patch_frappe.get_all.side_effect = [[], [], []]

    # Spy on every write method we care about
    patch_frappe.db.set_value = MagicMock()
    patch_frappe.db.sql = MagicMock()
    patch_frappe.db.delete = MagicMock()
    patch_frappe.db.commit = MagicMock()
    patch_frappe.db.rollback = MagicMock()
    patch_frappe.new_doc = MagicMock()
    patch_frappe.delete_doc = MagicMock()
    patch_frappe.rename_doc = MagicMock()

    from greythr_bridge.utils.data_quality import list_ghost_employees
    list_ghost_employees()

    # Assert NONE of the write methods were called
    patch_frappe.db.set_value.assert_not_called()
    patch_frappe.db.sql.assert_not_called()
    patch_frappe.db.delete.assert_not_called()
    patch_frappe.db.commit.assert_not_called()
    patch_frappe.db.rollback.assert_not_called()
    patch_frappe.new_doc.assert_not_called()
    patch_frappe.delete_doc.assert_not_called()
    patch_frappe.rename_doc.assert_not_called()


def test_list_ghost_employees_requires_hr_role(patch_frappe):
    """Non-HR/non-System-Manager users are rejected."""
    patch_frappe.get_roles.return_value = ["Employee"]  # not HR Manager
    patch_frappe.session.user = "regular_user@example.com"

    # frappe.throw should raise — we mock it to raise an exception so we can catch
    patch_frappe.throw.side_effect = PermissionError("Only HR Manager...")

    from greythr_bridge.utils.data_quality import list_ghost_employees
    try:
        list_ghost_employees()
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass

    patch_frappe.throw.assert_called_once()


def test_list_ghost_employees_accepts_system_manager(patch_frappe):
    """System Manager is also allowed (per _check_audit_role logic)."""
    patch_frappe.get_roles.return_value = ["System Manager"]
    patch_frappe.session.user = "sysadmin@example.com"
    patch_frappe.get_all.side_effect = [[], [], []]

    from greythr_bridge.utils.data_quality import list_ghost_employees
    result = list_ghost_employees()  # should not raise

    assert result["summary"]["total_employees"] == 0
    # frappe.throw should NOT have been called
    patch_frappe.throw.assert_not_called()


def test_list_ghost_employees_empty_database(patch_frappe):
    """Zero employees, zero mappings → all categories empty, total = 0."""
    _setup_audit_role(patch_frappe)
    patch_frappe.get_all.side_effect = [[], [], []]

    from greythr_bridge.utils.data_quality import list_ghost_employees
    result = list_ghost_employees()

    assert result["summary"] == {
        "total_employees": 0,
        "ghosts": 0,
        "mapped_clean": 0,
        "frappe_only": 0,
        "total_mappings": 0,
    }
    assert result["ghosts"] == []
    assert result["mapped_clean"] == []
    assert result["frappe_only"] == []
