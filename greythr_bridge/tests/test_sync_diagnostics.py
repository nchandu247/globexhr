"""
Tests for utils/sync_diagnostics.py — Phase 1 follow-up diagnostic.

The inspect endpoint is read-only by default (save_dry_run=True).
Tests verify the full path from Frappe Employee → mapping lookup →
greytHR API call → mapper output → would-change diff, plus the
optional save attempt path.
"""
from unittest.mock import MagicMock, patch


def _setup_admin_role(patch_frappe):
    patch_frappe.get_roles.return_value = ["System Manager"]
    patch_frappe.session.user = "admin@example.com"


def _setup_employee_doc(patch_frappe, fields):
    """Configure get_doc to return a MagicMock Employee with field values."""
    doc = MagicMock()
    doc.get.side_effect = lambda f, *a, **k: fields.get(f)
    patch_frappe.get_doc.return_value = doc
    return doc


def test_inspect_requires_system_manager(patch_frappe):
    """HR Manager is NOT enough — diagnostics require System Manager."""
    patch_frappe.get_roles.return_value = ["HR Manager"]
    patch_frappe.throw.side_effect = PermissionError("Only System Manager...")

    from greythr_bridge.utils.sync_diagnostics import inspect_sync_for_employee
    try:
        inspect_sync_for_employee("HR-EMP-00001")
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass


def test_inspect_no_mapping_returns_clear_error(patch_frappe):
    """When the Frappe Employee has no greytHR mapping, return a clear error
    explaining we can't fetch from greytHR without an ID."""
    _setup_admin_role(patch_frappe)
    _setup_employee_doc(patch_frappe, {
        "name": "HR-EMP-99999",
        "first_name": "",
        "custom_greythr_employee_id": None,
    })
    patch_frappe.get_all.return_value = []  # no mapping rows

    from greythr_bridge.utils.sync_diagnostics import inspect_sync_for_employee
    result = inspect_sync_for_employee("HR-EMP-99999")

    assert "error" in result
    assert "No greytHR Employee Mapping" in result["error"]
    assert result["frappe_record_now"]["name"] == "HR-EMP-99999"


def test_inspect_empty_greythr_id_in_mapping_flagged(patch_frappe):
    """If a mapping row exists but greythr_employee_id is empty (bulk-import
    placeholder bug), surface a specific error message."""
    _setup_admin_role(patch_frappe)
    _setup_employee_doc(patch_frappe, {"name": "HR-EMP-00869"})
    patch_frappe.get_all.return_value = [{
        "name": "GTH-MAP-001",
        "greythr_employee_id": None,  # broken mapping
        "greythr_employee_no": "GDS0234",
        "sync_status": "Pending",
        "last_sync_error": None,
        "last_synced_at": None,
    }]

    from greythr_bridge.utils.sync_diagnostics import inspect_sync_for_employee
    result = inspect_sync_for_employee("HR-EMP-00869")

    assert "error" in result
    assert "greythr_employee_id is empty" in result["error"]


def test_inspect_full_diagnostic_dry_run(patch_frappe):
    """Happy path: mapping exists, greytHR returns data, mapper extracts it,
    would-change diff computed, no save called (default dry-run)."""
    _setup_admin_role(patch_frappe)
    doc = _setup_employee_doc(patch_frappe, {
        "name": "HR-EMP-00869",
        "first_name": "",          # ghost
        "last_name": "",
        "company_email": "sanjeevgandla22@gmail.com",
        "employee_number": "GDS0234",
        "custom_greythr_employee_id": None,
        "status": "Active",
        "date_of_joining": None,
    })
    patch_frappe.get_all.return_value = [{
        "name": "GTH-MAP-869",
        "greythr_employee_id": "gth-uuid-234",
        "greythr_employee_no": "GDS0234",
        "sync_status": "In Sync",
        "last_sync_error": None,
        "last_synced_at": None,
    }]

    fake_greythr_response = {
        "data": [{
            "employeeId": "gth-uuid-234",
            "employeeNo": "GDS0234",
            "firstName": "Sanjeev",
            "lastName": "Gandla",
            "email": "sanjeevgandla22@gmail.com",
            "dateOfJoin": "01-06-2024",
        }]
    }

    with patch("greythr_bridge.utils.sync_diagnostics.get_employee",
               return_value=fake_greythr_response):
        from greythr_bridge.utils.sync_diagnostics import inspect_sync_for_employee
        result = inspect_sync_for_employee("HR-EMP-00869")

    # Diagnostic returned all expected sections
    assert "frappe_record_now" in result
    assert "greythr_api_response" in result
    assert "mapper_output" in result
    assert "would_change_fields" in result

    # Mapper produced enriched output
    mapper = result["mapper_output"]
    assert mapper["custom_greythr_employee_id"] == "gth-uuid-234"
    assert mapper["first_name"] == "Sanjeev"
    assert mapper["last_name"] == "Gandla"
    assert mapper["date_of_joining"] == "2024-06-01"  # mapper formats date

    # Would-change diff identified the empty Frappe fields
    changed_fields = {c["field"] for c in result["would_change_fields"]}
    assert "first_name" in changed_fields
    assert "last_name" in changed_fields
    assert "custom_greythr_employee_id" in changed_fields
    # Fields that already match are NOT in the diff
    assert "company_email" not in changed_fields
    assert "status" not in changed_fields

    # Dry run by default → no save attempted
    assert result["save_attempted"] is False
    assert result["save_result"] is None
    doc.save.assert_not_called()


def test_inspect_save_dry_run_false_actually_calls_save(patch_frappe):
    """When save_dry_run=False, save() IS called and the result is captured."""
    _setup_admin_role(patch_frappe)
    doc = _setup_employee_doc(patch_frappe, {
        "name": "HR-EMP-00869",
        "first_name": "",
        "company_email": "x@y.com",
        "custom_greythr_employee_id": None,
        "status": "Active",
    })
    patch_frappe.get_all.return_value = [{
        "name": "GTH-MAP-869",
        "greythr_employee_id": "gth-uuid-234",
        "greythr_employee_no": "GDS0234",
        "sync_status": "In Sync",
        "last_sync_error": None,
        "last_synced_at": None,
    }]

    fake_greythr_response = {
        "data": [{
            "employeeId": "gth-uuid-234",
            "employeeNo": "GDS0234",
            "firstName": "Sanjeev",
            "email": "x@y.com",
        }]
    }
    patch_frappe.db.commit = MagicMock()

    with patch("greythr_bridge.utils.sync_diagnostics.get_employee",
               return_value=fake_greythr_response):
        from greythr_bridge.utils.sync_diagnostics import inspect_sync_for_employee
        result = inspect_sync_for_employee("HR-EMP-00869", save_dry_run="false")

    assert result["save_attempted"] is True
    assert result["save_result"] == "OK"
    doc.save.assert_called_once()
    patch_frappe.db.commit.assert_called_once()


def test_inspect_save_failure_captures_traceback(patch_frappe):
    """When save() raises, the diagnostic captures the full traceback in
    save_result instead of leaking the exception up."""
    _setup_admin_role(patch_frappe)
    doc = _setup_employee_doc(patch_frappe, {
        "name": "HR-EMP-00869",
        "first_name": "",
        "custom_greythr_employee_id": None,
        "status": "Active",
    })
    doc.save.side_effect = RuntimeError("validate hook rejected save")
    patch_frappe.get_all.return_value = [{
        "name": "GTH-MAP-869",
        "greythr_employee_id": "gth-uuid-234",
        "greythr_employee_no": "GDS0234",
        "sync_status": "In Sync",
        "last_sync_error": None,
        "last_synced_at": None,
    }]
    patch_frappe.db.rollback = MagicMock()

    fake_greythr_response = {
        "data": [{
            "employeeId": "gth-uuid-234",
            "firstName": "Sanjeev",
        }]
    }

    with patch("greythr_bridge.utils.sync_diagnostics.get_employee",
               return_value=fake_greythr_response):
        from greythr_bridge.utils.sync_diagnostics import inspect_sync_for_employee
        result = inspect_sync_for_employee("HR-EMP-00869", save_dry_run=False)

    assert result["save_attempted"] is True
    assert "FAILED" in result["save_result"]
    assert "validate hook rejected save" in result["save_result"]
    patch_frappe.db.rollback.assert_called_once()


def test_list_recent_sync_errors_returns_filtered_log(patch_frappe):
    """Recent errors helper returns Error Log filtered to greytHR titles."""
    _setup_admin_role(patch_frappe)
    patch_frappe.get_all.return_value = [
        {"name": "EL-001", "title": "greytHR Pull Employee Error",
         "creation": "2026-05-23 04:48:30", "error": "Some error trace"},
    ]

    from greythr_bridge.utils.sync_diagnostics import list_recent_sync_errors
    result = list_recent_sync_errors(limit=5)

    assert result["count"] == 1
    assert result["errors"][0]["title"] == "greytHR Pull Employee Error"
    # Confirm we passed the title filter (raw string check, format-agnostic)
    full_call_repr = str(patch_frappe.get_all.call_args)
    assert "greytHR" in full_call_repr, (
        f"Expected get_all call to filter by greytHR title; got {full_call_repr}"
    )
    assert "Error Log" in full_call_repr


def test_list_recent_sync_errors_requires_system_manager(patch_frappe):
    patch_frappe.get_roles.return_value = ["HR Manager"]
    patch_frappe.throw.side_effect = PermissionError("denied")

    from greythr_bridge.utils.sync_diagnostics import list_recent_sync_errors
    try:
        list_recent_sync_errors()
        assert False, "Should have raised"
    except PermissionError:
        pass
