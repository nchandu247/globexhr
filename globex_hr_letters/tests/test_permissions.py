"""
Tests for greytHR Employee ID validation (Employee `validate` hook).

Replaces the old silent list-filter tests: utils/permissions.py was
deleted 2026-07-13 (decision B4) — malformed IDs are now a hard save
error and the records stay visible so HR can fix them.
"""
import os
from types import SimpleNamespace

import pytest

from globex_hr_letters.hooks_handlers.employee import (
    GREYTHR_ID_RE,
    validate_employee_number,
)


def _employee(number):
    return SimpleNamespace(employee_number=number)


def test_valid_ids_pass_and_normalise_to_uppercase(patch_frappe):
    for raw, expected in [
        ("GDS0115", "GDS0115"),      # real production ID
        ("gds0115", "GDS0115"),      # manual lowercase entry normalised
        ("GDS034", "GDS034"),        # 3 digits (early employees)
        ("GDS123456", "GDS123456"),  # 6 digits (B4: 3-6 range)
        (" GDS0115 ", "GDS0115"),    # stray whitespace stripped
    ]:
        doc = _employee(raw)
        validate_employee_number(doc)
        assert doc.employee_number == expected, raw
    patch_frappe.throw.assert_not_called()


def test_empty_id_allowed(patch_frappe):
    """The greytHR ID arrives only after joining — an Employee without one
    must save; letter generation is guarded separately (B5)."""
    for empty in (None, "", "   "):
        validate_employee_number(_employee(empty))
    patch_frappe.throw.assert_not_called()


def test_invalid_ids_throw(patch_frappe):
    """Known-bad production values and boundary cases must hard-error at
    save instead of silently vanishing from list views."""
    patch_frappe.throw.side_effect = RuntimeError("frappe.throw")
    for bad in (
        "GSD0033",       # transposed prefix (real incident)
        "Gds0943274",    # 7 digits (real incident)
        "ABC0001",       # wrong prefix
        "0001",          # no prefix
        "GDS",           # no digits
        "GDS00",         # 2 digits — below minimum
        "GDS1234567",    # 7 digits — above maximum
        "XGDS0001",      # prefix not anchored
        "GDS0001X",      # suffix not anchored
    ):
        with pytest.raises(RuntimeError):
            validate_employee_number(_employee(bad))
    patch_frappe.throw.side_effect = None


def test_pattern_is_gds_plus_3_to_6_digits():
    assert GREYTHR_ID_RE.match("GDS123")
    assert GREYTHR_ID_RE.match("GDS123456")
    assert not GREYTHR_ID_RE.match("GDS12")
    assert not GREYTHR_ID_RE.match("GDS1234567")


def test_hooks_py_wires_validator_and_drops_retired_hooks():
    """Validator only fires if hooks.py routes Employee.validate to it —
    catch the silent wiring mistake. Also pin the 2026-07-13 retirements:
    no list filter, no insert-time rename."""
    hooks_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "hooks.py")
    )
    with open(hooks_path) as f:
        source = f.read()
    assert (
        "globex_hr_letters.hooks_handlers.employee.validate_employee_number"
        in source
    ), "Employee.validate must be wired to validate_employee_number"
    assert (
        "globex_hr_letters.hooks_handlers.employee.apply_employee_defaults"
        in source
    ), "Employee.before_insert must be wired to apply_employee_defaults"
    assert "permission_query_conditions" not in source, \
        "Silent list filter retired 2026-07-13 (B4) — must not return"
    assert "set_name_from_employee_number" not in source, \
        "Insert-time rename retired 2026-07-13 (B3) — must not return"
