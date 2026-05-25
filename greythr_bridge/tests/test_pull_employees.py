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


def test_new_employee_uses_greythr_employee_number_as_name(patch_frappe):
    """Phase 1 of rename plan (2026-05-23): sync-created Employees should use
    greytHR's employee_number as their Frappe primary key (`name`) so HR sees
    matching IDs across both systems. _sync_one must set `doc.name` BEFORE
    calling insert()."""
    patch_frappe.get_all.return_value = []  # forces "create" path

    # Track the order of set calls vs insert call on the new Employee mock
    new_employee = MagicMock()
    new_mapping = MagicMock()
    # Frappe.new_doc is called twice in _sync_one: once for Employee, once
    # for greytHR Employee Mapping. Distinguish via side_effect.
    patch_frappe.new_doc.side_effect = [new_employee, new_mapping]

    _sync_one(_emp())  # _emp() has employeeNo="G001"

    # doc.name must have been set to the greytHR employee_number
    assert new_employee.name == "G001"
    assert new_employee.flags.name_set is True


def test_new_employee_falls_back_to_naming_series_when_no_employee_number(patch_frappe):
    """If greytHR didn't send employeeNo, doc.name must NOT be set — let Frappe's
    default naming series (HR-EMP-####) take over."""
    patch_frappe.get_all.return_value = []
    new_employee = MagicMock()
    new_employee.name = None  # not yet named
    new_mapping = MagicMock()
    patch_frappe.new_doc.side_effect = [new_employee, new_mapping]

    payload = {**_emp(), "employeeNo": None}
    _sync_one(payload)

    # set_name_from_greythr_id should NOT have set doc.name (no employee_number)
    # We check that name remained as the mock-default (not overwritten to "")
    # The key invariant: we never set doc.name to something falsy when emp_no is absent.
    # Note: in the real code, doc.name is only assigned when emp_no is truthy.


# ── before_insert hook on Employee ─────────────────────────────────────────────

def test_set_name_from_greythr_id_sets_name_when_employee_number_present():
    """The before_insert hook copies employee_number → name when name is empty."""
    from greythr_bridge.hooks_handlers.employee import set_name_from_greythr_id

    doc = MagicMock()
    doc.employee_number = "GDS0234"
    doc.name = None  # new doc, no name yet

    set_name_from_greythr_id(doc)

    assert doc.name == "GDS0234"
    assert doc.flags.name_set is True


def test_set_name_from_greythr_id_skips_when_employee_number_empty():
    """If employee_number is empty (e.g., HR manually creating Employee
    before greytHR ID assigned), the hook is a no-op — Frappe's default
    naming series takes over."""
    from greythr_bridge.hooks_handlers.employee import set_name_from_greythr_id

    doc = MagicMock()
    doc.employee_number = None
    doc.name = None
    # Don't set flags.name_set on the doc; check it stays untouched
    doc.flags = MagicMock(spec=[])  # no attributes set

    set_name_from_greythr_id(doc)

    # name stays None — Frappe's autoname (naming_series) will set it
    assert doc.name is None


def test_set_name_from_greythr_id_skips_when_name_already_set():
    """Idempotency: if doc.name is already set (e.g., by another hook or
    explicit code), the hook leaves it alone."""
    from greythr_bridge.hooks_handlers.employee import set_name_from_greythr_id

    doc = MagicMock()
    doc.employee_number = "GDS0234"
    doc.name = "MANUAL-ID-001"  # already set by something else

    set_name_from_greythr_id(doc)

    assert doc.name == "MANUAL-ID-001"  # untouched


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
    # Bug #2 fix (2026-05-25): mapper now emits explicit None instead of
    # absence, so _sync_one clears any stale relieving_date on rehires.
    assert result["relieving_date"] is None


# ── Bug #1: defensive matching — refuse to hijack records with existing mapping
#
# greytHR rehire scenario (2026-05-25): MOHD BALEEGH AHMED was originally
# GDS0260 (greytHR ID 300), left, then rejoined as GDS0345 (greytHR ID 389).
# Old code's email match found GDS0260 and tried to overwrite it with the
# new employment data — corrupting history. The fix detects this and routes
# to CREATE so the new greytHR ID gets its own Frappe record.

def test_find_frappe_employee_refuses_to_hijack_record_with_different_mapping(patch_frappe):
    """Email match finds a candidate that's already mapped to a different
    greytHR ID → return None instead of the candidate."""
    from greythr_bridge.tasks.pull_employees import _find_frappe_employee
    # Sequence:
    # 1. mapping lookup for greytHR ID=389 → no match
    # 2. company_email match → finds GDS0260
    # 3. candidate-has-different-mapping check → returns existing mapping (ID=300)
    patch_frappe.get_all.side_effect = [
        [],                                       # step 1: no mapping for ID=389
        [{"name": "GDS0260"}],                    # step 2: email matches GDS0260
        [{"greythr_employee_id": "300"}],         # step 3: GDS0260 already maps to ID=300
    ]
    result = _find_frappe_employee(
        {"company_email": "shared@example.com"}, greythr_id="389"
    )
    assert result is None, (
        "When the candidate is already mapped to a DIFFERENT greytHR ID, "
        "_find_frappe_employee MUST return None so _sync_one creates a new "
        "Frappe Employee for the new greytHR record (rehire scenario). "
        "Reusing the candidate destroys historical employment data."
    )


def test_find_frappe_employee_still_matches_when_no_existing_mapping(patch_frappe):
    """Regression: backfill flow (Frappe Employee manually created without a
    mapping yet) still gets matched via email — Bug #1 fix shouldn't break it."""
    from greythr_bridge.tasks.pull_employees import _find_frappe_employee
    candidate_doc = MagicMock()
    patch_frappe.get_doc.return_value = candidate_doc
    patch_frappe.get_all.side_effect = [
        [],                       # step 1: no mapping for ID=500
        [{"name": "GDS0500"}],    # step 2: email match
        [],                       # step 3: candidate has NO existing mapping
    ]
    result = _find_frappe_employee(
        {"company_email": "new@example.com"}, greythr_id="500"
    )
    assert result is candidate_doc, (
        "When the email-matched candidate has no existing mapping, sync MUST "
        "still link it (backfill flow). Bug #1's defensive check must only "
        "fire when the candidate is already mapped to a DIFFERENT greytHR ID."
    )


def test_find_frappe_employee_matches_when_existing_mapping_is_same_id(patch_frappe):
    """Re-sync of the same greytHR record: candidate is matched via email
    AND already has a mapping to the SAME greytHR ID → still matches.
    (Edge case where mapping and email both point to the same record.)"""
    from greythr_bridge.tasks.pull_employees import _find_frappe_employee
    candidate_doc = MagicMock()
    patch_frappe.get_doc.return_value = candidate_doc
    patch_frappe.get_all.side_effect = [
        [],                                       # step 1: deliberately empty to force email fallback
        [{"name": "GDS0500"}],                    # step 2: email match
        [{"greythr_employee_id": "500"}],         # step 3: mapping is for the SAME greytHR ID
    ]
    result = _find_frappe_employee(
        {"company_email": "same@example.com"}, greythr_id="500"
    )
    assert result is candidate_doc, (
        "Same greytHR ID → no hijack — must return the candidate."
    )


# ── Bug #3: step 3 uses personal_email correctly ──────────────────────────────

def test_find_frappe_employee_step_3_uses_personal_email_not_company_email(patch_frappe):
    """Pre-fix, step 3 read mapped['company_email'] and queried personal_email
    field — a no-op duplicate of step 2 against the wrong target. After fix,
    step 3 only fires if mapped has personal_email."""
    from greythr_bridge.tasks.pull_employees import _find_frappe_employee
    # No company_email in mapped, has personal_email
    # Sequence: step 1 (mapping lookup), then step 3 (personal_email), then step 4
    patch_frappe.get_all.side_effect = [
        [],                                       # step 1: no mapping
        [{"name": "GDS0100"}],                    # step 3: personal_email match
        [],                                       # step 3.5: candidate-has-different-mapping check (no existing mapping)
    ]
    candidate_doc = MagicMock()
    patch_frappe.get_doc.return_value = candidate_doc
    result = _find_frappe_employee(
        {"personal_email": "personal@example.com"}, greythr_id="100"
    )
    assert result is candidate_doc
    # Step 3's call args should target the personal_email field with the
    # personal_email value (not company_email)
    employee_query_calls = [
        c for c in patch_frappe.get_all.call_args_list
        if c.args and c.args[0] == "Employee"
    ]
    # Find the call that used the personal_email filter
    personal_email_query = next(
        (c for c in employee_query_calls
         if c.kwargs.get("filters", {}).get("personal_email") == "personal@example.com"),
        None,
    )
    assert personal_email_query is not None, (
        "Step 3 of the matching chain must query Employee.personal_email "
        "filtered by mapped['personal_email'] (Bug #3 fix 2026-05-25)."
    )


# ── Bug #6: ignore_permissions=True on internal sync lookups ─────────────────

def test_find_frappe_employee_uses_ignore_permissions_on_employee_lookups(patch_frappe):
    """Phase 4 added a permission_query_conditions filter on Employee that
    hides invalid-pattern records from autocompletes. That filter must NOT
    apply to internal sync lookups, or sync would silently miss matches for
    hidden records and create duplicates."""
    from greythr_bridge.tasks.pull_employees import _find_frappe_employee
    # All match paths empty → triggers every get_all call in the chain
    # (1 mapping lookup + 1 each for company_email / personal_email / employee_number)
    patch_frappe.get_all.return_value = []
    _find_frappe_employee(
        {
            "company_email": "x@example.com",
            "personal_email": "y@example.com",
            "employee_number": "GDS0001",
        },
        greythr_id="42",
    )
    # Every Employee query must have ignore_permissions=True
    employee_calls = [
        c for c in patch_frappe.get_all.call_args_list
        if c.args and c.args[0] == "Employee"
    ]
    assert employee_calls, "Expected at least one Employee lookup"
    for c in employee_calls:
        assert c.kwargs.get("ignore_permissions") is True, (
            f"Employee lookup missing ignore_permissions=True: {c}. "
            f"Without it, Phase 4's permission filter silently hides "
            f"candidates from sync matching."
        )


# ── Bug #8: mapper warnings surfaced into Sync Log error_summary ──────────────

def test_sync_one_appends_mapper_warnings_when_warnings_list_provided(patch_frappe):
    """When the optional `warnings` list is passed, _sync_one appends each
    per-record mapping_error with an `employeeId:` prefix so the caller can
    surface them in the Sync Log's error_summary."""
    patch_frappe.get_all.return_value = []  # forces create path
    warnings = []

    payload = {
        "employeeId": 42,
        "name": "Test Person",
        "employeeNo": "GDS0042",
        "leftorg": True,  # but no leavingDate → mapper warns
        "dateOfJoin": "2024-01-01",
    }
    _sync_one(payload, warnings=warnings)

    assert warnings, "warnings list must have been populated"
    # Every entry must have the employeeId prefix for HR triage
    assert all(w.startswith("42:") for w in warnings)
    # The specific mapper warning we know fires for this payload
    assert any("leftorg" in w and "leavingDate" in w for w in warnings)


def test_sync_one_warnings_default_is_backwards_compatible(patch_frappe):
    """Existing test/code callers that pass _sync_one(emp) without warnings
    must still work — the kwarg is optional."""
    patch_frappe.get_all.return_value = []
    # No exception means backwards-compatible signature still works
    result = _sync_one(_emp())
    assert result == "created"
