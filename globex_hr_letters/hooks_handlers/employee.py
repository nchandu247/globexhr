"""
Handlers for the Employee doctype.

1. `validate_employee_number` — Employee `validate`. The greytHR Employee
   ID is generated in the external greytHR system after joining and
   recorded manually in `employee_number`. Format: GDS + 3-6 digits.
   Anything else is a hard save error (decision B4, 2026-07-13 — replaces
   the old silent list filter that hid malformed records). Empty stays
   allowed: the ID arrives only after joining; letters that need it are
   guarded at generation time instead (engine `_require_greythr_id`).

2. `apply_employee_defaults` — Employee `before_insert`. Auto-assigns the
   placeholder Holiday List ("Calendar-Only (No Holidays)", created by
   setup_letter_placeholders) so records save without setup friction.

The old insert-time naming hook (employee_number as the Frappe primary
key) was retired 2026-07-13 (decision B3): Employees keep the internal
HR-EMP-#### identity; letters print the greytHR ID from the field via the
`greythr_employee_id` / `employee_id` placeholders.
"""
import re

import frappe

from ..tasks.setup_letter_placeholders import DEFAULT_HOLIDAY_LIST

# Canonical greytHR Employee ID: GDS + 3-6 digits (confirmed 2026-07-13).
GREYTHR_ID_RE = re.compile(r"^GDS\d{3,6}$", re.IGNORECASE)


def validate_employee_number(doc, method=None):
    """
    Reject malformed greytHR IDs at save with an actionable error, and
    normalise accepted values to uppercase (manual entry produces
    "gds0115" variants). Empty is allowed — see module docstring.
    """
    emp_no = (doc.employee_number or "").strip()
    if not emp_no:
        return
    if not GREYTHR_ID_RE.match(emp_no):
        frappe.throw(
            f"'{emp_no}' is not a valid greytHR Employee ID. Expected "
            "format: GDS followed by 3-6 digits (e.g. GDS0115). Correct "
            "the Employee Number and save again.",
            title="Invalid greytHR Employee ID",
        )
    doc.employee_number = emp_no.upper()


def apply_employee_defaults(doc, method=None):
    """
    Employee `before_insert`: default the mandatory holiday_list to the
    placeholder list when blank. Only assigns if the list exists, so a
    fresh environment doesn't crash with an FK error.
    """
    if not doc.holiday_list:
        if frappe.db.exists("Holiday List", DEFAULT_HOLIDAY_LIST):
            doc.holiday_list = DEFAULT_HOLIDAY_LIST
        # else: silently skip — HR hasn't run setup_letter_placeholders yet.
        # Frappe HR's validate will surface the missing setup explicitly.
