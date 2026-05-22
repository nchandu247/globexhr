"""
Document event handler for Salary Structure Assignment.

Auto-generates and emails the Increment Letter on SSA submit, with these
skip conditions (per spec §4.3):
  - custom_send_increment_letter checkbox is unchecked (HR decision)
  - No previous active SSA exists (this is the first salary, not an increment)
  - New CTC <= previous CTC (not an increment)

All generation happens in a background job so on_submit returns within 5 seconds.
"""
import frappe

from ..letters.merger import build_increment_context
from ..letters.non_signing import generate_and_deliver
from ..utils.logging import log_error


def on_ssa_submitted(doc, method):
    """Triggered on Salary Structure Assignment submit."""
    settings = frappe.get_single("greytHR Settings")
    if not settings.enabled:
        return

    if not getattr(doc, "custom_send_increment_letter", 0):
        # HR explicitly opted out for this SSA
        return

    frappe.enqueue(
        "greythr_bridge.hooks_handlers.salary_structure_assignment.send_increment_letter",
        queue="short",
        ssa_name=doc.name,
    )


def send_increment_letter(ssa_name: str) -> None:
    """Background job: generate Increment Letter PDF, attach, email."""
    try:
        ssa = frappe.get_doc("Salary Structure Assignment", ssa_name)

        # Pre-flight: skip if this isn't actually an increment
        new_ctc = float(getattr(ssa, "custom_annual_ctc", None) or 0)
        if new_ctc <= 0:
            log_error(
                f"send_increment_letter: {ssa_name} skipped — "
                f"custom_annual_ctc is empty. HR should set this before submit.",
                "greytHR Letter Config Error",
            )
            return

        previous = frappe.get_all(
            "Salary Structure Assignment",
            filters={"employee": ssa.employee, "docstatus": 1,
                     "name": ["!=", ssa_name]},
            fields=["name", "custom_annual_ctc"],
            order_by="from_date desc",
            limit=1,
        )
        if not previous:
            log_error(
                f"send_increment_letter: {ssa_name} skipped — no previous SSA "
                f"for employee {ssa.employee}. This appears to be first salary, "
                f"not an increment.",
                "greytHR Letter Info",
            )
            return

        old_ctc = float(previous[0].custom_annual_ctc or 0)
        if old_ctc and new_ctc <= old_ctc:
            log_error(
                f"send_increment_letter: {ssa_name} skipped — new CTC "
                f"({new_ctc}) is not greater than old CTC ({old_ctc}).",
                "greytHR Letter Info",
            )
            return

        # All checks passed — generate the letter
        employee = frappe.get_doc("Employee", ssa.employee)
        context = build_increment_context(ssa)

        generate_and_deliver(
            template_filename="increment_letter.html",
            context=context,
            attach_to=("Salary Structure Assignment", ssa_name),
            file_label="Increment Letter",
            employee_doc=employee,
            email_subject=f"Your Salary Increment Letter — Globex Digital Solutions",
            prefer_personal_email=False,  # employee is still active
        )

        # Mark as generated
        frappe.db.set_value(
            "Salary Structure Assignment", ssa_name,
            "custom_increment_letter_generated", 1
        )

    except Exception as exc:
        log_error(
            f"send_increment_letter: {ssa_name} error={str(exc)[:200]}",
            "greytHR Letter Generation Error",
        )
