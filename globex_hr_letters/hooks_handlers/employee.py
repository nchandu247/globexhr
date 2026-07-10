"""
Handlers for the Employee doctype.

1. Naming hook (`set_name_from_employee_number`) — fires on
   `Employee.before_insert` (wired in hooks.py). When `employee_number` is
   set, uses it as the Frappe primary key so letters and attachments carry
   the human-facing ID (e.g. GDS0021). Otherwise falls back to Frappe HR's
   default naming series (HR-EMP-####).

2. Holiday list default (same hook) — satisfies Frappe HR's mandatory
   holiday_list requirement so Employee records save without setup friction.
   Set to the "Calendar-Only (No Holidays)" placeholder created by
   setup_letter_placeholders.
"""
import frappe

from ..tasks.setup_letter_placeholders import DEFAULT_HOLIDAY_LIST


def set_name_from_employee_number(doc, method=None):
    """
    Two-in-one Employee `before_insert` hook:

    A) Use employee_number as the Frappe Employee primary key (name).
       Idempotent: only sets `doc.name` if employee_number is populated AND
       name is not already set. Falls through to Frappe HR's default naming
       series (HR-EMP-####) when employee_number is empty.

    B) Auto-assign the default Holiday List if blank. Frappe HR requires
       holiday_list on several downstream flows. The placeholder list
       ("Calendar-Only (No Holidays)") is created by the
       setup_letter_placeholders task — we only assign if it exists, so a
       fresh environment doesn't crash with an FK error.
    """
    # (A) Naming
    if doc.employee_number and not doc.name:
        doc.name = doc.employee_number
        # Tell Frappe naming logic to skip autoname (defensive — set_new_name
        # in Frappe also checks `if not doc.name`, but flags.name_set is
        # the explicit "I know what I'm doing" signal).
        doc.flags.name_set = True

    # (B) Default holiday_list (Frappe HR mandatory)
    if not doc.holiday_list:
        if frappe.db.exists("Holiday List", DEFAULT_HOLIDAY_LIST):
            doc.holiday_list = DEFAULT_HOLIDAY_LIST
        # else: silently skip — HR hasn't run setup_letter_placeholders yet.
        # Frappe HR's validate will surface the missing setup explicitly.
