"""
Permission query conditions wired up via hooks.py.

These produce extra SQL WHERE clauses that Frappe appends to list / autocomplete
queries. They are NOT a security boundary — direct URL access (`/app/employee/
HR-EMP-01010`) bypasses these filters. Treat them as UX filters that keep
the autocomplete pickers tidy.

Why we use them here:
  - greytHR sometimes returns records with malformed `employee_number` values
    (e.g., "Gds0943274" with 10 digits, "GSD0033" with a transposed
    abbreviation). Our `tasks/rename_employees_to_greythr_id.py` plan_rename
    categorises those into the `invalid_pattern` bucket and skips them. They
    still live in Frappe as HR-EMP-#### records, but their identifier is wrong
    so HR shouldn't pick them when assigning Salary Structure Assignments,
    setting Reporting To on a Job Offer, etc.
  - The cleanest UX fix is to omit them from list / picker results across the
    whole system. HR can still open them via the URL bar after fixing the
    underlying greytHR data, which is what we want.
"""


def employee_query_conditions(user: str | None = None) -> str:
    """
    Filter Employee queries to skip records whose `employee_number` is set
    but doesn't match the canonical GDS#### pattern (case-insensitive,
    3 to 5 digits — same regex as `plan_rename`).

    Allowed:
      - employee_number IS NULL or empty (manual Frappe-only employees,
        legitimately have no greytHR ID — e.g., new hires created before
        greytHR onboarding)
      - employee_number matches `^GDS\\d{3,5}$` case-insensitive
        (greytHR-aligned records)

    Filtered out:
      - employee_number set to anything else (typos, garbage, mis-formatted)

    The MariaDB `REGEXP` operator is case-insensitive by default for
    non-binary collations (utf8mb4_unicode_ci / utf8mb4_general_ci, which is
    Frappe's default), so a single character-class regex covers both
    "GDS0001" and "gds0115".

    Args:
        user: the calling user — accepted for the Frappe hook signature but
              not used. The filter is uniform for everyone (UX, not security).

    Returns:
        A SQL WHERE-clause fragment ready to be ANDed by Frappe.
    """
    return (
        "(`tabEmployee`.employee_number IS NULL "
        "OR `tabEmployee`.employee_number = '' "
        "OR `tabEmployee`.employee_number REGEXP '^GDS[0-9]{3,5}$')"
    )
