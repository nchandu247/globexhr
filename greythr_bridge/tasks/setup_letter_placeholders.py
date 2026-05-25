"""
One-time setup task for the placeholder records that satisfy Frappe HR's
mandatory-field validations on Employee Separation and Salary Structure
Assignment.

Why this exists
----------------
Frappe HR enforces that:
  - Every Employee has a `holiday_list` set (used by Frappe HR's leave /
    attendance / final-settlement features).
  - Every Salary Structure Assignment links to a `salary_structure` (used by
    Frappe HR's payroll-slip generation).

Globex runs payroll, leave, and attendance in greytHR — Frappe HR is a
mirror + letter-generation layer. We don't need the semantic content of
these fields; we just need the validations to pass so the on_submit hooks
that trigger Experience / Relieving / Increment letters can fire.

The clean solution (Option A from the 2026-05-25 design discussion):
create empty/minimal PLACEHOLDER records and auto-assign them. Frappe HR's
data model stays consistent (no validation overrides); other Frappe HR
features (Leave Application, Salary Slip, etc.) remain usable if HR ever
wants them — they'd just operate on "zero holidays" and "one nominal
component" defaults that HR can replace with real records later.

What this task creates (idempotent — safe to re-run):
  1. Salary Component "CTC" — type Earning, no formula
  2. Salary Structure "Letter Trigger Structure" — INR, Monthly, one CTC
     earning component, submitted
  3. Holiday List "Calendar-Only (No Holidays)" — empty, full current year

Then backfills:
  4. Sets `holiday_list = "Calendar-Only (No Holidays)"` on every Frappe
     Employee that doesn't already have one set.

Restricted to System Manager — privileged setup.
"""
from datetime import date

import frappe

from ..utils.logging import log_error


# ── Constants ─────────────────────────────────────────────────────────────────
# These names are referenced from hooks_handlers/employee.py and
# tasks/pull_employees.py to auto-assign holiday_list on new Employees.
# If you rename here, update those call sites too.

DEFAULT_HOLIDAY_LIST = "Calendar-Only (No Holidays)"
DEFAULT_SALARY_COMPONENT = "CTC"
DEFAULT_SALARY_STRUCTURE = "Letter Trigger Structure"


def _check_role() -> None:
    """System Manager only — privileged setup."""
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(
            "Only System Manager can run setup_letter_placeholders. "
            "This task creates Salary Component / Salary Structure / "
            "Holiday List records and backfills holiday_list on all employees."
        )


@frappe.whitelist()
def setup_letter_placeholders() -> dict:
    """
    Whitelisted entry point — HR runs ONCE after deploy via:

        /api/method/greythr_bridge.tasks.setup_letter_placeholders.setup_letter_placeholders

    Idempotent: subsequent runs are no-ops (the `if not exists` checks
    skip already-created records, and the backfill skips employees that
    already have a holiday_list).

    Returns a JSON summary with what was created and how many employees
    were backfilled.
    """
    _check_role()

    summary = {
        "salary_component_created": False,
        "salary_structure_created": False,
        "holiday_list_created": False,
        "employees_backfilled": 0,
        "employees_already_set": 0,
        "errors": [],
    }

    # ── 1. Salary Component "CTC" ────────────────────────────────────────────
    try:
        if not frappe.db.exists("Salary Component", DEFAULT_SALARY_COMPONENT):
            comp = frappe.new_doc("Salary Component")
            comp.salary_component = DEFAULT_SALARY_COMPONENT
            comp.salary_component_abbr = "CTC"
            comp.type = "Earning"
            comp.is_tax_applicable = 0
            comp.depends_on_payment_days = 0
            comp.do_not_include_in_total = 0
            comp.statistical_component = 0
            comp.round_to_the_nearest_integer = 1
            comp.description = (
                "Placeholder component for the Letter Trigger Structure. "
                "greytHR runs actual payroll; do NOT use this for real "
                "salary slips. See tasks/setup_letter_placeholders.py."
            )
            comp.insert(ignore_permissions=True)
            summary["salary_component_created"] = True
    except Exception as exc:
        summary["errors"].append(f"Salary Component create failed: {exc}")
        log_error(
            f"setup_letter_placeholders: Salary Component error: {str(exc)[:300]}",
            "greytHR Setup Placeholders",
        )

    # ── 2. Holiday List "Calendar-Only (No Holidays)" ────────────────────────
    try:
        if not frappe.db.exists("Holiday List", DEFAULT_HOLIDAY_LIST):
            hl = frappe.new_doc("Holiday List")
            hl.holiday_list_name = DEFAULT_HOLIDAY_LIST
            current_year = date.today().year
            hl.from_date = f"{current_year}-01-01"
            hl.to_date = f"{current_year}-12-31"
            # Intentionally empty: no weekly_off, no holidays
            hl.insert(ignore_permissions=True)
            summary["holiday_list_created"] = True
    except Exception as exc:
        summary["errors"].append(f"Holiday List create failed: {exc}")
        log_error(
            f"setup_letter_placeholders: Holiday List error: {str(exc)[:300]}",
            "greytHR Setup Placeholders",
        )

    # ── 3. Salary Structure "Letter Trigger Structure" ───────────────────────
    # Submittable doctype — must insert then submit. Skip if it already
    # exists (whether draft or submitted).
    try:
        if not frappe.db.exists("Salary Structure", DEFAULT_SALARY_STRUCTURE):
            company = frappe.defaults.get_user_default("Company") or \
                frappe.db.get_single_value("Global Defaults", "default_company")
            if not company:
                summary["errors"].append(
                    "Could not determine default Company — set one in Global "
                    "Defaults before running this task."
                )
            else:
                ss = frappe.new_doc("Salary Structure")
                ss.name = DEFAULT_SALARY_STRUCTURE
                ss.company = company
                ss.currency = "INR"
                ss.payroll_frequency = "Monthly"
                ss.is_active = "Yes"
                ss.append("earnings", {
                    "salary_component": DEFAULT_SALARY_COMPONENT,
                    "abbr": "CTC",
                    "amount_based_on_formula": 0,
                    "amount": 0,
                    "do_not_include_in_total": 0,
                    "statistical_component": 0,
                })
                ss.flags.ignore_mandatory = True
                ss.insert(ignore_permissions=True)
                ss.submit()
                summary["salary_structure_created"] = True
    except Exception as exc:
        summary["errors"].append(f"Salary Structure create failed: {exc}")
        log_error(
            f"setup_letter_placeholders: Salary Structure error: {str(exc)[:300]}",
            "greytHR Setup Placeholders",
        )

    # ── 4. Backfill holiday_list on all Employees ────────────────────────────
    # Only update employees missing the field; skip those already set.
    # Uses db.set_value (bypasses Employee validate hook — we don't want
    # to trigger status-flip side effects on this bulk update).
    if frappe.db.exists("Holiday List", DEFAULT_HOLIDAY_LIST):
        try:
            employees = frappe.get_all(
                "Employee",
                fields=["name", "holiday_list"],
                ignore_permissions=True,
                limit_page_length=0,  # no limit
            )
            for emp in employees:
                if not emp.get("holiday_list"):
                    frappe.db.set_value(
                        "Employee", emp["name"], "holiday_list",
                        DEFAULT_HOLIDAY_LIST, update_modified=False,
                    )
                    summary["employees_backfilled"] += 1
                else:
                    summary["employees_already_set"] += 1
            frappe.db.commit()
        except Exception as exc:
            summary["errors"].append(f"Backfill failed: {exc}")
            log_error(
                f"setup_letter_placeholders: backfill error: {str(exc)[:300]}",
                "greytHR Setup Placeholders",
            )

    log_error(
        f"setup_letter_placeholders completed: "
        f"component={summary['salary_component_created']}, "
        f"structure={summary['salary_structure_created']}, "
        f"holiday_list={summary['holiday_list_created']}, "
        f"backfilled={summary['employees_backfilled']}, "
        f"already_set={summary['employees_already_set']}, "
        f"errors={len(summary['errors'])}",
        "greytHR Setup Placeholders",
    )

    return summary
