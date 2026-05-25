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


# ── inspect_greythr_employee — for records without mappings ──────────────────

def test_inspect_greythr_employee_requires_system_manager(patch_frappe):
    patch_frappe.get_roles.return_value = ["HR Manager"]
    patch_frappe.throw.side_effect = PermissionError("denied")

    from greythr_bridge.utils.sync_diagnostics import inspect_greythr_employee
    try:
        inspect_greythr_employee("389")
        assert False, "Should have raised"
    except PermissionError:
        pass


def test_inspect_greythr_employee_requires_id(patch_frappe):
    """Empty greythr_id returns a clear error instead of calling greytHR."""
    _setup_admin_role(patch_frappe)

    from greythr_bridge.utils.sync_diagnostics import inspect_greythr_employee
    result = inspect_greythr_employee("")
    assert "error" in result
    assert "required" in result["error"]


def test_inspect_greythr_employee_returns_api_response_and_mapper_output(patch_frappe):
    """Happy path: greytHR returns a record, mapper extracts it, both visible
    in the response for debugging."""
    _setup_admin_role(patch_frappe)

    fake_response = {
        "data": [{
            "employeeId": 389,
            "name": "Test Person",
            "employeeNo": "GDS0389",
            "dateOfJoin": "2024-01-15",
            "leavingDate": "2024-08-15",
            "leftorg": True,
            "gender": "M",
        }]
    }

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee", return_value=fake_response):
        result = sync_diagnostics.inspect_greythr_employee("389")

    assert result["greythr_id"] == "389"
    assert result["greythr_api_response"] == fake_response
    assert result["extracted_employee_payload"]["employeeId"] == 389
    assert result["mapper_output"]["first_name"] == "Test Person"
    assert result["mapper_output"]["custom_greythr_employee_id"] == "389"
    # Valid record — no sanity-check error
    assert result["mapper_output"]["status"] == "Left"
    assert result["mapper_output"]["relieving_date"] == "2024-08-15"


def test_inspect_greythr_employee_surfaces_sanity_check_for_bad_data(patch_frappe):
    """When greytHR returns a record with missing dateOfJoin + leavingDate,
    the response should show the mapper-output with relieving_date dropped
    and the sanity-check error message visible — the exact diagnostic we
    need for employeeId=389."""
    _setup_admin_role(patch_frappe)

    bad_payload = {
        "employeeId": 389,
        "name": "Missing Joining Date",
        "employeeNo": "GDS0389",
        # dateOfJoin missing — the hypothesis we're testing
        "leavingDate": "2024-06-15",
        "leftorg": True,
    }

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee", return_value=bad_payload):
        result = sync_diagnostics.inspect_greythr_employee("389")

    # Mapper applied the sanity check (Bug #2 2026-05-25: relieving_date is
    # now explicit None, not absent — see employee_mapper.py status block)
    assert result["mapper_output"]["relieving_date"] is None
    assert result["mapper_output"]["status"] == "Active"
    # And surfaced the reason so HR knows what to fix in greytHR
    assert any("missing" in e and "389" in str(e) for e in result["mapper_errors"])


def test_inspect_greythr_employee_handles_api_error(patch_frappe):
    """greytHR API errors (network, 404, auth) return a structured error
    instead of bubbling up — caller can read the JSON instead of seeing a
    500 in the browser."""
    _setup_admin_role(patch_frappe)

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee",
                      side_effect=RuntimeError("greytHR returned 404")):
        result = sync_diagnostics.inspect_greythr_employee("999999")

    assert result["greythr_id"] == "999999"
    assert "greythr_api_error" in result
    assert "RuntimeError" in result["greythr_api_error"]
    assert "404" in result["greythr_api_error"]


# ── force_resync_employee — HR repair tool for broken mappings ────────────────

def test_force_resync_requires_system_manager(patch_frappe):
    patch_frappe.get_roles.return_value = ["HR Manager"]
    patch_frappe.throw.side_effect = PermissionError("Only System Manager")

    from greythr_bridge.utils.sync_diagnostics import force_resync_employee
    try:
        force_resync_employee("GDS0215", "250")
        assert False, "Should have raised PermissionError"
    except PermissionError:
        pass


def test_force_resync_requires_both_args(patch_frappe):
    _setup_admin_role(patch_frappe)

    from greythr_bridge.utils.sync_diagnostics import force_resync_employee
    assert "error" in force_resync_employee("", "250")
    assert "error" in force_resync_employee("GDS0215", "")


def test_force_resync_aborts_if_greythr_returns_different_id(patch_frappe):
    """Safety: if we ask greytHR for ID 250 but the API returns data with
    employeeId=999, refuse to apply it. Otherwise we'd corrupt the slot
    with mismatched data."""
    _setup_admin_role(patch_frappe)
    employee_doc = MagicMock()
    employee_doc.name = "GDS0215"
    patch_frappe.get_doc.return_value = employee_doc

    fake_response = {"data": [{
        "employeeId": 999,           # DIFFERENT from requested 250
        "employeeNo": "GDS0999",
        "name": "Someone Else",
        "email": "someone@example.com",
    }]}

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee", return_value=fake_response):
        result = sync_diagnostics.force_resync_employee("GDS0215", "250")

    assert "error" in result
    assert "250" in result["error"] and "999" in result["error"]
    # Critically — we did NOT save anything
    employee_doc.save.assert_not_called()


def test_force_resync_corrects_existing_mapping(patch_frappe):
    """Happy path: Frappe Employee + existing wrong mapping. After
    force_resync, fields are updated AND mapping is corrected."""
    _setup_admin_role(patch_frappe)

    # Frappe Employee GDS0215 currently has wrong (syed shabber) data
    employee_doc = MagicMock()
    employee_doc.name = "GDS0215"
    field_state = {
        "employee_number": "GDS0144",
        "first_name": "syed shabber",
        "company_email": "syedshabber121@gmail.com",
        "status": "Left",
        "date_of_joining": "2021-09-01",
        "relieving_date": "2022-09-30",
        "custom_greythr_employee_id": "159",
    }
    employee_doc.get.side_effect = lambda f, *a, **kw: field_state.get(f)
    def _set(field, value):
        field_state[field] = value
    employee_doc.set.side_effect = _set

    mapping_doc = MagicMock()
    mapping_doc.name = "MAP-c3ug4edk5j"

    # get_doc is called twice: once for Employee, once for Mapping
    patch_frappe.get_doc.side_effect = [employee_doc, mapping_doc]

    # get_all is called once: find existing mapping by frappe_employee
    patch_frappe.get_all.return_value = [{
        "name": "MAP-c3ug4edk5j",
        "greythr_employee_id": "159",     # WRONG — points at older record
        "greythr_employee_no": "GDS0144",
    }]

    # greytHR returns Shabbir Syed's data for ID 250
    fake_response = {"data": [{
        "employeeId": 250,
        "employeeNo": "GDS0215",
        "name": "Shabbir Syed",
        "email": "syedshabber121@gmail.com",
        "dateOfJoin": "2023-04-03",
        "leavingDate": "2024-03-29",
        "leftorg": True,
    }]}

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee", return_value=fake_response):
        result = sync_diagnostics.force_resync_employee("GDS0215", "250")

    assert result["result"] == "OK"
    assert result["frappe_employee"] == "GDS0215"
    assert result["greythr_id"] == "250"
    assert "corrected" in result["mapping_action"]

    # Employee fields were overwritten with Shabbir Syed's data
    assert field_state["first_name"] == "Shabbir Syed"
    assert field_state["employee_number"] == "GDS0215"
    assert field_state["custom_greythr_employee_id"] == "250"
    assert field_state["date_of_joining"] == "2023-04-03"
    employee_doc.save.assert_called()

    # Mapping was corrected
    assert mapping_doc.greythr_employee_id == "250"
    assert mapping_doc.greythr_employee_no == "GDS0215"
    mapping_doc.save.assert_called()

    # Changed fields documented in response for audit
    assert "first_name" in result["fields_changed"]
    assert result["fields_changed"]["first_name"]["before"] == "syed shabber"
    assert result["fields_changed"]["first_name"]["after"] == "Shabbir Syed"


def test_force_resync_creates_mapping_when_none_exists(patch_frappe):
    """Edge case: Frappe Employee exists but has no mapping row yet.
    force_resync should CREATE the mapping pointing at the given greytHR ID."""
    _setup_admin_role(patch_frappe)

    employee_doc = MagicMock()
    employee_doc.name = "GDS9999"
    employee_doc.get.return_value = None

    new_mapping = MagicMock()
    patch_frappe.new_doc.return_value = new_mapping
    patch_frappe.get_doc.return_value = employee_doc
    patch_frappe.get_all.return_value = []  # no existing mapping

    fake_response = {"data": [{
        "employeeId": 777,
        "employeeNo": "GDS9999",
        "name": "Test Person",
        "email": "test@example.com",
        "dateOfJoin": "2024-01-01",
    }]}

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee", return_value=fake_response):
        result = sync_diagnostics.force_resync_employee("GDS9999", "777")

    assert result["result"] == "OK"
    assert "created" in result["mapping_action"]
    # new mapping was inserted with the right values
    assert new_mapping.greythr_employee_id == "777"
    assert new_mapping.greythr_employee_no == "GDS9999"
    assert new_mapping.frappe_employee == "GDS9999"
    new_mapping.insert.assert_called()


def test_force_resync_returns_error_if_frappe_employee_missing(patch_frappe):
    """If get_doc raises DoesNotExistError, return a clear error message
    naming the missing Frappe Employee."""
    _setup_admin_role(patch_frappe)
    # Promote frappe.DoesNotExistError to a real Exception subclass so the
    # function's `except frappe.DoesNotExistError:` actually catches it.
    import sys
    class _FakeDNE(Exception):
        pass
    sys.modules["frappe"].DoesNotExistError = _FakeDNE
    patch_frappe.get_doc.side_effect = _FakeDNE("not found")

    from greythr_bridge.utils.sync_diagnostics import force_resync_employee
    result = force_resync_employee("GDS-nonexistent", "250")
    assert "error" in result
    assert "not found" in result["error"]
    # Restore the mock to avoid bleeding state into other tests
    sys.modules["frappe"].DoesNotExistError = MagicMock()


def test_force_resync_returns_error_if_greythr_api_fails(patch_frappe):
    """If the greytHR API call itself fails, return a structured error
    without touching the Frappe Employee."""
    _setup_admin_role(patch_frappe)
    employee_doc = MagicMock()
    patch_frappe.get_doc.return_value = employee_doc

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee",
                      side_effect=RuntimeError("greytHR 503")):
        result = sync_diagnostics.force_resync_employee("GDS0215", "250")

    assert "error" in result
    assert "503" in result["error"] or "RuntimeError" in result["error"]
    employee_doc.save.assert_not_called()


def test_force_resync_logs_audit_entry(patch_frappe):
    """Every successful resync writes a 'greytHR Forced Resync' Error Log
    entry naming the slot, greytHR ID, mapping action, and changed fields."""
    _setup_admin_role(patch_frappe)

    employee_doc = MagicMock()
    employee_doc.name = "GDS0215"
    employee_doc.get.return_value = "old_value"
    mapping_doc = MagicMock()
    patch_frappe.get_doc.side_effect = [employee_doc, mapping_doc]
    patch_frappe.get_all.return_value = [{
        "name": "MAP-X",
        "greythr_employee_id": "159",
        "greythr_employee_no": "GDS0144",
    }]

    fake_response = {"data": [{
        "employeeId": 250,
        "employeeNo": "GDS0215",
        "name": "Shabbir Syed",
        "email": "syedshabber121@gmail.com",
        "dateOfJoin": "2023-04-03",
    }]}

    from greythr_bridge.utils import sync_diagnostics
    with patch.object(sync_diagnostics, "get_employee", return_value=fake_response):
        sync_diagnostics.force_resync_employee("GDS0215", "250")

    log_calls = patch_frappe.log_error.call_args_list
    audit_logs = [c for c in log_calls
                  if c.kwargs.get("title") == "greytHR Forced Resync"]
    assert audit_logs, "Must write a 'greytHR Forced Resync' audit log entry"
    audit_msg = audit_logs[0].kwargs.get("message", "")
    assert "GDS0215" in audit_msg
    assert "250" in audit_msg
