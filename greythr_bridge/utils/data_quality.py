"""
Read-only data-quality audits for Employee records.

These helpers produce reports HR can use to identify data integrity
issues without making any database changes. See the Employee Data
Integrity Plan:
  docs/superpowers/specs/2026-05-23-employee-data-integrity-plan.md

Hard rule (saved in user memory): never delete or rename any Employee
or greytHR Employee Mapping record. greytHR is the production payroll
system; Frappe records may be linked to salary slips, leaves, and
attendance. These audits are read-only by design.
"""
import frappe


def _check_audit_role() -> None:
    """Audit endpoints expose PII — restrict to HR/System Managers."""
    roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in roles and "System Manager" not in roles:
        frappe.throw(
            "Only HR Manager or System Manager can run data quality audits."
        )


@frappe.whitelist()
def list_ghost_employees() -> dict:
    """
    Read-only audit of Frappe Employee records — Phase 1 of the Employee
    Data Integrity Plan.

    Returns three categories with counts and details:

      - ghosts: Employees with blank first_name. Created by pull_employees
        from incomplete greytHR data (mapper accepted record with employeeId
        but no firstName; pull task used ignore_mandatory=True). Should be
        healed via Phase 2: HR opens each in greytHR portal, fills missing
        data, next sync auto-populates Frappe.

      - mapped_clean: Employees with first_name AND a greytHR mapping. The
        well-formed records — most of the 332.

      - frappe_only: Employees with first_name but NO greytHR mapping.
        Likely manually created in Frappe (e.g., test records), never
        synced from greytHR. Investigate before any action.

    No DB writes. Safe to call repeatedly. Output is JSON; HR can review
    in the browser or pipe to a CSV externally.

    Call from any HR Manager / System Manager session:
        /api/method/greythr_bridge.utils.data_quality.list_ghost_employees
    """
    _check_audit_role()

    # ── Ghosts: empty first_name ──────────────────────────────────────────────
    # Use or_filters so SQL becomes (first_name IS NULL OR first_name = '').
    # The earlier `["in", ["", None]]` form didn't handle NULL correctly because
    # SQL's `IN ('', NULL)` is undefined for NULL.
    ghosts = frappe.get_all(
        "Employee",
        or_filters=[
            ["first_name", "is", "not set"],
            ["first_name", "=", ""],
        ],
        fields=[
            "name", "employee_number", "custom_greythr_employee_id",
            "company_email", "status", "custom_greythr_last_synced",
            "creation", "owner",
        ],
        limit_page_length=0,
    )

    # ── Employees with first_name populated ───────────────────────────────────
    # AND-combined filters so SQL becomes (first_name IS NOT NULL AND first_name != '').
    # The earlier `["not in", ["", None]]` form returned 0 rows because SQL's
    # `NOT IN ('', NULL)` is always undefined (never true) for any value.
    employees_with_data = frappe.get_all(
        "Employee",
        filters=[
            ["first_name", "is", "set"],
            ["first_name", "!=", ""],
        ],
        fields=[
            "name", "first_name", "last_name", "employee_number",
            "custom_greythr_employee_id", "company_email", "status",
            "custom_greythr_last_synced",
        ],
        limit_page_length=0,
    )

    # ── All Frappe Employees that have a greytHR mapping ──────────────────────
    mapping_rows = frappe.get_all(
        "greytHR Employee Mapping",
        fields=["frappe_employee"],
        limit_page_length=0,
    )
    mapped_names = {row["frappe_employee"] for row in mapping_rows}

    # ── Categorise ────────────────────────────────────────────────────────────
    mapped_clean = [
        e for e in employees_with_data if e["name"] in mapped_names
    ]
    frappe_only = [
        e for e in employees_with_data if e["name"] not in mapped_names
    ]

    total_employees = len(ghosts) + len(employees_with_data)

    return {
        "summary": {
            "total_employees": total_employees,
            "ghosts": len(ghosts),
            "mapped_clean": len(mapped_clean),
            "frappe_only": len(frappe_only),
            "total_mappings": len(mapped_names),
        },
        "ghosts": ghosts,
        "mapped_clean": mapped_clean,
        "frappe_only": frappe_only,
    }


@frappe.whitelist()
def list_employees_missing_holiday_list() -> dict:
    """
    Read-only audit — surface Employees whose `holiday_list` field is blank.

    Why this matters: Frappe HR requires `holiday_list` on every Employee
    before an Employee Separation can be created (validate hook). The
    setup_letter_placeholders task backfills all existing employees + the
    before_insert hook auto-assigns the default on new ones — so a non-zero
    count here means either:
      - setup_letter_placeholders hasn't been run yet, OR
      - An Employee was created via a code path that bypassed our hook
        (rare — possible if HR uses an import / bulk update tool)

    Returns counts + per-employee details. Restricted to HR / System Manager.

    Call:
      /api/method/greythr_bridge.utils.data_quality.list_employees_missing_holiday_list
    """
    _check_audit_role()

    missing = frappe.get_all(
        "Employee",
        filters=[["holiday_list", "is", "not set"]],
        fields=["name", "employee_name", "first_name", "status",
                "company", "date_of_joining"],
        ignore_permissions=True,
        limit_page_length=0,
    )
    return {
        "summary": {
            "count_missing_holiday_list": len(missing),
            "next_step": (
                "Run setup_letter_placeholders to create the default Holiday "
                "List + backfill missing assignments. URL: /api/method/"
                "greythr_bridge.tasks.setup_letter_placeholders."
                "setup_letter_placeholders"
            ) if missing else "All Employees have a holiday_list — no action needed.",
        },
        "employees": missing,
    }
