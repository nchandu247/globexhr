"""
Tests for the Employee query-condition filter.

These check the SQL fragment shape (no Frappe runtime needed) and verify
the regex covers both case variants of the GDS#### pattern. The actual
in-DB filtering behaviour is tested implicitly by Frappe when migrate
runs and by the rename test suite.
"""
import re

from greythr_bridge.utils.permissions import employee_query_conditions


def test_returns_a_single_parenthesised_sql_clause():
    """Frappe ANDs the returned string into the query — it must be a
    self-contained boolean expression (parens around the OR), otherwise
    operator precedence breaks the rest of the WHERE clause."""
    clause = employee_query_conditions()
    assert clause.startswith("("), \
        f"Clause must start with '(' to bind OR cleanly: {clause!r}"
    assert clause.endswith(")"), \
        f"Clause must end with ')' to bind OR cleanly: {clause!r}"
    # Balance check
    assert clause.count("(") == clause.count(")"), \
        f"Unbalanced parens in clause: {clause!r}"


def test_clause_includes_null_and_empty_allowance():
    """Manual Frappe-only employees (no greytHR ID) must remain visible.
    Both NULL and empty-string forms of an unset value should pass."""
    clause = employee_query_conditions()
    assert "IS NULL" in clause, \
        "Clause must permit employee_number IS NULL (manual employees)"
    assert "= ''" in clause, \
        "Clause must permit employee_number = '' (the other unset form)"


def test_clause_uses_GDS_pattern_with_3_to_5_digits():
    """Must match the same valid set as the rename script's _VALID_EMPLOYEE_NUMBER
    (^GDS\\d{3,5}$). Drift here would silently re-show records the rename
    skips, undoing the whole UX fix."""
    clause = employee_query_conditions()
    # MariaDB REGEXP operator
    assert "REGEXP" in clause
    # Anchored regex covering GDS + 3-5 digits
    assert "^GDS[0-9]{3,5}$" in clause, \
        f"Regex must be anchored 3-5 digit GDS: {clause!r}"


def test_clause_filters_the_two_known_invalid_records():
    """Spot-check by extracting the regex and running it against the
    actual invalid_pattern values currently on the live site:
      - 'Gds0943274'  (siuad) — 10 digits, mixed case → must NOT match
      - 'GSD0033'     (Yarabaka Mahitha) — transposed prefix → must NOT match
    MariaDB's REGEXP on default utf8mb4_unicode_ci is case-insensitive,
    so we test with the IGNORECASE flag to mirror that behaviour."""
    clause = employee_query_conditions()
    pattern_match = re.search(r"REGEXP\s+'([^']+)'", clause)
    assert pattern_match, f"No regex literal found in clause: {clause!r}"
    pattern = pattern_match.group(1)
    rx = re.compile(pattern, re.IGNORECASE)

    # Known bad — must be FILTERED OUT (regex does NOT match)
    assert not rx.match("Gds0943274"), "siuad record (10 digits) should be filtered"
    assert not rx.match("GSD0033"), "Yarabaka Mahitha (GSD typo) should be filtered"
    assert not rx.match("ABC0001"), "Wrong prefix entirely should be filtered"
    assert not rx.match("0001"), "No prefix should be filtered"

    # Known good — must be ALLOWED (regex matches, case-insensitive)
    assert rx.match("GDS0001"), "Standard greytHR ID"
    assert rx.match("GDS0115"), "Real production ID"
    assert rx.match("gds0115"), "Lowercase variant must also pass (case-insensitive)"
    assert rx.match("GDS034"), "3-digit suffix valid per regex (early employees)"
    assert rx.match("GDS00012"), "5-digit suffix valid per regex"

    # Edge cases
    assert not rx.match("GDS"), "Empty digits must not match"
    assert not rx.match("GDS00"), "2 digits below minimum"
    assert not rx.match("GDS123456"), "6 digits above maximum"
    assert not rx.match("XGDS0001"), "Prefix must be anchored at start"
    assert not rx.match("GDS0001X"), "Suffix must be anchored at end"


def test_user_argument_accepted_but_ignored():
    """Frappe passes the calling user to permission_query_conditions hooks.
    Our filter is uniform for everyone (UX, not security) — must accept
    the kwarg without breaking."""
    clause_no_user = employee_query_conditions()
    clause_with_user = employee_query_conditions(user="admin@example.com")
    assert clause_no_user == clause_with_user, \
        "Filter must be identical regardless of user — it's a UX filter, " \
        "not a per-user permission."


def test_hooks_py_wires_the_filter():
    """The function exists, but unless hooks.py routes Employee queries to it,
    it doesn't fire. Catch the silent wiring mistake."""
    import os
    hooks_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "hooks.py")
    )
    with open(hooks_path) as f:
        source = f.read()
    assert "permission_query_conditions" in source, \
        "Missing permission_query_conditions in hooks.py — the filter won't fire."
    assert "greythr_bridge.utils.permissions.employee_query_conditions" in source, \
        "hooks.py must reference the full dotted path to the filter function."
    assert '"Employee"' in source, \
        "Filter must be keyed by 'Employee' doctype."
