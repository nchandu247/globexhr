"""
Tests for tasks/rename_employees_to_greythr_id.py — offline, no Frappe.

The rename module has two whitelisted entry points:
  - plan_rename() — read-only categorisation; safe to call anytime
  - run_rename(confirm) — enqueues background job _do_rename

These tests cover:
  - Role check (System Manager only)
  - plan_rename categorisation logic (to_rename, already_correct,
    no_employee_number, invalid_pattern, collisions)
  - run_rename's confirm gate
  - _do_rename's per-record commit/rollback, sync auto-disable/re-enable,
    progress logging, audit trail in details field
"""
from unittest.mock import MagicMock, patch


def _setup_sysadmin(patch_frappe):
    patch_frappe.get_roles.return_value = ["System Manager"]
    patch_frappe.session.user = "admin@example.com"


def _employees(rows):
    """Helper to mock the get_all('Employee', ...) response."""
    return rows


# ── Role check ────────────────────────────────────────────────────────────────

def test_plan_rename_requires_system_manager(patch_frappe):
    patch_frappe.get_roles.return_value = ["HR Manager"]  # not enough
    patch_frappe.throw.side_effect = PermissionError("Only System Manager")

    from greythr_bridge.tasks.rename_employees_to_greythr_id import plan_rename
    try:
        plan_rename()
        assert False, "Should have raised"
    except PermissionError:
        pass


def test_run_rename_requires_system_manager(patch_frappe):
    patch_frappe.get_roles.return_value = ["HR Manager"]
    patch_frappe.throw.side_effect = PermissionError("Only System Manager")

    from greythr_bridge.tasks.rename_employees_to_greythr_id import run_rename
    try:
        run_rename(confirm="yes")
        assert False
    except PermissionError:
        pass


def test_run_rename_requires_confirm_yes(patch_frappe):
    """Without confirm=yes, refuses to start. Even System Manager."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.throw.side_effect = ValueError("must confirm")

    from greythr_bridge.tasks.rename_employees_to_greythr_id import run_rename
    try:
        run_rename(confirm="no")  # default
        assert False
    except ValueError:
        pass


def test_run_rename_with_confirm_enqueues(patch_frappe):
    """With confirm=yes, enqueues the background job."""
    _setup_sysadmin(patch_frappe)

    from greythr_bridge.tasks.rename_employees_to_greythr_id import run_rename
    result = run_rename(confirm="yes")

    assert result["status"] == "enqueued"
    patch_frappe.enqueue.assert_called_once()


# ── plan_rename categorisation ────────────────────────────────────────────────

def test_plan_rename_categorises_correctly(patch_frappe):
    """5 categories: to_rename, already_correct, no_employee_number,
    invalid_pattern, collisions."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.get_all.return_value = _employees([
        # Clean record — needs rename
        {"name": "HR-EMP-00001", "employee_number": "GDS0001",
         "first_name": "Alice", "status": "Active"},
        {"name": "HR-EMP-00002", "employee_number": "GDS0002",
         "first_name": "Bob", "status": "Active"},
        # Already correct — name already matches
        {"name": "GDS0003", "employee_number": "GDS0003",
         "first_name": "Carol", "status": "Active"},
        # No employee_number
        {"name": "HR-EMP-00004", "employee_number": None,
         "first_name": "Dave", "status": "Active"},
        {"name": "HR-EMP-00005", "employee_number": "",
         "first_name": "Eve", "status": "Active"},
        # Invalid pattern — lowercase, typo, wrong format
        {"name": "HR-EMP-00006", "employee_number": "gds0006",  # lowercase OK
         "first_name": "Frank", "status": "Active"},
        {"name": "HR-EMP-00007", "employee_number": "GSD0007",  # typo
         "first_name": "Grace", "status": "Active"},
        {"name": "HR-EMP-00008", "employee_number": "9876543210",  # phone
         "first_name": "Hank", "status": "Active"},
    ])

    from greythr_bridge.tasks.rename_employees_to_greythr_id import plan_rename
    result = plan_rename()

    summary = result["summary"]
    assert summary["total_employees"] == 8
    assert summary["to_rename"] == 3   # GDS0001, GDS0002, AND gds0006 (case-insensitive)
    assert summary["already_correct"] == 1  # GDS0003
    assert summary["no_employee_number"] == 2  # Dave + Eve
    assert summary["invalid_pattern"] == 2  # GSD0007, 9876543210
    assert summary["collisions"] == 0

    # Spot-check the rename plan
    rename_targets = {(r["from"], r["to"]) for r in result["to_rename"]}
    assert ("HR-EMP-00001", "GDS0001") in rename_targets
    assert ("HR-EMP-00002", "GDS0002") in rename_targets


def test_plan_rename_detects_collisions(patch_frappe):
    """If two records' employee_numbers would collide (e.g., both renamed
    to GDS0001, or one rename would clash with another record's existing
    name), report as collision."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.get_all.return_value = _employees([
        {"name": "HR-EMP-00001", "employee_number": "GDS0001",
         "first_name": "A", "status": "Active"},
        # GDS0001 already exists as another record's name
        {"name": "GDS0001", "employee_number": "GDS0099",
         "first_name": "B", "status": "Active"},
    ])

    from greythr_bridge.tasks.rename_employees_to_greythr_id import plan_rename
    result = plan_rename()

    # HR-EMP-00001 would collide because GDS0001 exists already
    assert result["summary"]["collisions"] == 1
    assert result["collisions"][0]["name"] == "HR-EMP-00001"


def test_plan_rename_idempotent_on_already_renamed_records(patch_frappe):
    """If all records are already correctly named, plan reports zero work."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.get_all.return_value = _employees([
        {"name": "GDS0001", "employee_number": "GDS0001",
         "first_name": "A", "status": "Active"},
        {"name": "GDS0002", "employee_number": "GDS0002",
         "first_name": "B", "status": "Active"},
    ])

    from greythr_bridge.tasks.rename_employees_to_greythr_id import plan_rename
    result = plan_rename()

    assert result["summary"]["to_rename"] == 0
    assert result["summary"]["already_correct"] == 2


# ── _do_rename — actual execution ─────────────────────────────────────────────

def test_do_rename_disables_and_re_enables_sync(patch_frappe):
    """The background job must temporarily disable greytHR sync (to prevent
    race condition with scheduled pull_employees) and restore on completion."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.get_value.return_value = 1  # sync was enabled
    patch_frappe.get_all.return_value = _employees([])  # empty plan

    from greythr_bridge.tasks.rename_employees_to_greythr_id import _do_rename
    _do_rename()

    # set_value should be called at least twice: disable (0) and re-enable (1)
    calls = patch_frappe.db.set_value.call_args_list
    enabled_writes = [c for c in calls
                      if len(c.args) >= 4 and c.args[2] == "enabled"]
    values_written = [c.args[3] for c in enabled_writes]
    assert 0 in values_written, "Must disable sync at start"
    assert 1 in values_written, "Must re-enable sync at end"


def test_do_rename_skips_re_enable_if_sync_was_disabled(patch_frappe):
    """If sync was already disabled before run, don't auto-enable it
    (would change HR's intended state)."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.get_value.return_value = 0  # sync was already off
    patch_frappe.get_all.return_value = _employees([])

    from greythr_bridge.tasks.rename_employees_to_greythr_id import _do_rename
    _do_rename()

    # No set_value to 'enabled' since it was already off
    calls = patch_frappe.db.set_value.call_args_list
    enabled_writes = [c for c in calls
                      if len(c.args) >= 4 and c.args[2] == "enabled"]
    assert not enabled_writes


def test_do_rename_per_record_commit_on_success(patch_frappe):
    """Each successful rename must commit independently."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.get_value.return_value = 0  # sync disabled (simpler)
    patch_frappe.get_all.return_value = _employees([
        {"name": "HR-EMP-00001", "employee_number": "GDS0001",
         "first_name": "A", "status": "Active"},
        {"name": "HR-EMP-00002", "employee_number": "GDS0002",
         "first_name": "B", "status": "Active"},
    ])
    patch_frappe.rename_doc = MagicMock()  # succeeds for both

    from greythr_bridge.tasks.rename_employees_to_greythr_id import _do_rename
    _do_rename()

    # rename_doc called twice (one per record)
    assert patch_frappe.rename_doc.call_count == 2
    # commit called multiple times (per-record + log writes)
    assert patch_frappe.db.commit.call_count >= 2


def test_do_rename_rolls_back_and_continues_on_failure(patch_frappe):
    """If one rename fails, rollback that record and continue to the next."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.get_value.return_value = 0
    patch_frappe.get_all.return_value = _employees([
        {"name": "HR-EMP-00001", "employee_number": "GDS0001",
         "first_name": "A", "status": "Active"},
        {"name": "HR-EMP-00002", "employee_number": "GDS0002",
         "first_name": "B", "status": "Active"},
        {"name": "HR-EMP-00003", "employee_number": "GDS0003",
         "first_name": "C", "status": "Active"},
    ])
    # rename_doc fails for the middle record
    patch_frappe.rename_doc = MagicMock(side_effect=[
        None, RuntimeError("validate hook rejected"), None
    ])

    from greythr_bridge.tasks.rename_employees_to_greythr_id import _do_rename
    _do_rename()

    # Continued past the failure — all 3 attempted
    assert patch_frappe.rename_doc.call_count == 3
    # Rollback was called for the failure
    assert patch_frappe.db.rollback.called


def test_do_rename_persists_audit_trail_in_sync_log_details(patch_frappe):
    """The greytHR Sync Log's `details` field must contain JSON with every
    (old, new) rename pair for disaster recovery."""
    _setup_sysadmin(patch_frappe)
    patch_frappe.db.get_value.return_value = 0
    patch_frappe.get_all.return_value = _employees([
        {"name": "HR-EMP-00001", "employee_number": "GDS0001",
         "first_name": "A", "status": "Active"},
    ])
    sync_log = MagicMock()
    patch_frappe.new_doc.return_value = sync_log
    patch_frappe.rename_doc = MagicMock()

    from greythr_bridge.tasks.rename_employees_to_greythr_id import _do_rename
    _do_rename()

    # `details` field was set with a JSON string
    assert sync_log.details is not None
    import json
    details_dict = json.loads(sync_log.details)
    assert "audit" in details_dict
    assert "summary" in details_dict
    # Audit log has the rename entry
    assert any(
        entry["old"] == "HR-EMP-00001" and entry["new"] == "GDS0001"
        and entry["status"] == "OK"
        for entry in details_dict["audit"]
    )


# ── Sync Log Select-field convention ──────────────────────────────────────────

def test_start_rename_log_uses_valid_status_enum(patch_frappe):
    """The initial `status` written to greytHR Sync Log must be 'Started'
    (the only valid 'job is running' value in the Select options:
    Started / Success / Partial Success / Failed).

    Regression: an earlier version used 'In Progress', which Frappe's
    _validate_selects rejected, crashing _do_rename before any rename ran.
    """
    sync_log = MagicMock()
    patch_frappe.new_doc.return_value = sync_log

    from datetime import datetime
    from greythr_bridge.tasks.rename_employees_to_greythr_id import _start_rename_log
    _start_rename_log(datetime(2026, 5, 24, 15, 0, 0))

    valid_running_states = {"Started", "Success", "Partial Success", "Failed"}
    assert sync_log.status in valid_running_states, (
        f"status={sync_log.status!r} not in Select options {valid_running_states}"
    )
    # Specifically pin to "Started" — convention shared with pull_employees
    # and pull_salary_structures.
    assert sync_log.status == "Started"
    assert sync_log.sync_type == "Rename Employees to greytHR ID"
    assert sync_log.triggered_by == "Manual"
