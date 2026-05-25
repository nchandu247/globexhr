"""
Document event handler for Employee Separation.

On submit, auto-generates Experience Letter and/or Relieving Letter based on
the custom_send_experience_letter and custom_send_relieving_letter checkboxes
on the Separation record. Both letters can be generated together.

For separation letters, email delivery prefers personal_email since the
employee's company_email may already be deactivated by IT.

All generation in background jobs so on_submit returns within 5 seconds.
"""
import frappe

from ..letters.merger import build_experience_context, build_relieving_context
from ..letters.non_signing import generate_and_deliver
from ..utils.logging import log_error


def on_separation_submitted(doc, method):
    """Triggered on Employee Separation submit."""
    settings = frappe.get_single("greytHR Settings")
    if not settings.enabled:
        return

    if getattr(doc, "custom_send_experience_letter", 0):
        frappe.enqueue(
            "greythr_bridge.hooks_handlers.employee_separation.send_experience_letter",
            queue="short",
            separation_name=doc.name,
        )

    if getattr(doc, "custom_send_relieving_letter", 0):
        frappe.enqueue(
            "greythr_bridge.hooks_handlers.employee_separation.send_relieving_letter",
            queue="short",
            separation_name=doc.name,
        )


def send_experience_letter(separation_name: str) -> None:
    """Background job: generate Experience Letter PDF, attach, email.

    Attaches to BOTH the Employee record (primary — permanent file on the
    person) AND the Employee Separation (secondary — HR's separation
    workflow view). Filename uses the employee's GDS#### identifier.
    """
    try:
        separation = frappe.get_doc("Employee Separation", separation_name)
        if not separation.employee:
            log_error(
                f"send_experience_letter: {separation_name} skipped — "
                f"no employee linked to separation",
                "greytHR Letter Config Error",
            )
            return

        employee = frappe.get_doc("Employee", separation.employee)
        context = build_experience_context(separation)

        generate_and_deliver(
            template_filename="experience_letter.html",
            context=context,
            attach_to=("Employee", employee.name),  # primary: belongs to the person
            also_attach_to=("Employee Separation", separation_name),  # also in HR's workflow
            file_label="Experience Letter",
            file_name_suffix=employee.name,  # GDS#### in filename
            employee_doc=employee,
            email_subject="Your Experience Letter — Globex Digital Solutions",
            prefer_personal_email=True,  # separation — company email may be off
        )
    except Exception as exc:
        log_error(
            f"send_experience_letter: {separation_name} error={str(exc)[:200]}",
            "greytHR Letter Generation Error",
        )


def send_relieving_letter(separation_name: str) -> None:
    """Background job: generate Relieving Letter PDF, attach, email.

    Same dual-attachment pattern as send_experience_letter.
    """
    try:
        separation = frappe.get_doc("Employee Separation", separation_name)
        if not separation.employee:
            log_error(
                f"send_relieving_letter: {separation_name} skipped — "
                f"no employee linked to separation",
                "greytHR Letter Config Error",
            )
            return

        employee = frappe.get_doc("Employee", separation.employee)
        context = build_relieving_context(separation)

        generate_and_deliver(
            template_filename="relieving_letter.html",
            context=context,
            attach_to=("Employee", employee.name),
            also_attach_to=("Employee Separation", separation_name),
            file_label="Relieving Letter",
            file_name_suffix=employee.name,
            employee_doc=employee,
            email_subject="Your Relieving Letter — Globex Digital Solutions",
            prefer_personal_email=True,
        )
    except Exception as exc:
        log_error(
            f"send_relieving_letter: {separation_name} error={str(exc)[:200]}",
            "greytHR Letter Generation Error",
        )
