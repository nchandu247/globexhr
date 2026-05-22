"""
Manual-trigger handlers for letters issued from the Employee form.

These are whitelisted methods invoked from Client Scripts (buttons) on the
Employee form:
  - send_promotion_letter: requires old/new designation + effective date + notes
  - send_service_certificate: just needs the employee_name argument

Both restricted to System Manager / HR Manager roles. All work runs in
background jobs so the dialog returns immediately.
"""
from datetime import date
import frappe

from ..letters.merger import (
    build_promotion_context,
    build_service_certificate_context,
)
from ..letters.non_signing import generate_and_deliver
from ..utils.logging import log_error


def _check_hr_role():
    """Raise if current user isn't HR Manager or System Manager."""
    roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in roles and "System Manager" not in roles:
        frappe.throw("Only HR Manager or System Manager can generate this letter.")


@frappe.whitelist()
def send_promotion_letter(
    employee_name: str,
    old_designation: str,
    new_designation: str,
    effective_date: str,
    notes: str = "",
) -> dict:
    """
    Enqueue Promotion Letter generation for an Employee.

    Args (all from the Client Script dialog):
        employee_name:    Employee.name (e.g. "HR-EMP-00001")
        old_designation:  Previous designation
        new_designation:  New designation
        effective_date:   Date string, e.g. "2026-06-01"
        notes:            Optional manager notes
    """
    _check_hr_role()

    if not all([employee_name, old_designation, new_designation, effective_date]):
        frappe.throw("Missing required field. Provide all fields in the dialog.")

    frappe.enqueue(
        "greythr_bridge.hooks_handlers.employee._send_promotion_letter_job",
        queue="short",
        employee_name=employee_name,
        old_designation=old_designation,
        new_designation=new_designation,
        effective_date=effective_date,
        notes=notes,
    )
    return {"status": "enqueued", "employee_name": employee_name}


def _send_promotion_letter_job(employee_name: str, old_designation: str,
                                new_designation: str, effective_date: str,
                                notes: str) -> None:
    """Background job: render Promotion Letter, attach, email."""
    try:
        employee = frappe.get_doc("Employee", employee_name)
        context = build_promotion_context(
            employee, old_designation, new_designation, effective_date, notes,
        )

        generate_and_deliver(
            template_filename="promotion_letter.html",
            context=context,
            attach_to=("Employee", employee_name),
            file_label="Promotion Letter",
            employee_doc=employee,
            email_subject="Your Promotion Letter — Globex Digital Solutions",
            prefer_personal_email=False,
        )

        frappe.db.set_value(
            "Employee", employee_name, "custom_promotion_letter_attached", 1
        )
    except Exception as exc:
        log_error(
            f"_send_promotion_letter_job: {employee_name} error={str(exc)[:200]}",
            "greytHR Letter Generation Error",
        )


@frappe.whitelist()
def send_service_certificate(employee_name: str) -> dict:
    """
    Enqueue Service Certificate generation for an Employee.

    Args:
        employee_name: Employee.name (e.g. "HR-EMP-00001")
    """
    _check_hr_role()

    if not employee_name:
        frappe.throw("Missing employee_name.")

    # Sanity: only for active employees
    status = frappe.db.get_value("Employee", employee_name, "status")
    if status and status != "Active":
        frappe.throw(
            f"Service Certificate can only be issued to Active employees. "
            f"This employee status is: {status}."
        )

    frappe.enqueue(
        "greythr_bridge.hooks_handlers.employee._send_service_certificate_job",
        queue="short",
        employee_name=employee_name,
    )
    return {"status": "enqueued", "employee_name": employee_name}


def _send_service_certificate_job(employee_name: str) -> None:
    """Background job: render Service Certificate, attach, email."""
    try:
        employee = frappe.get_doc("Employee", employee_name)
        context = build_service_certificate_context(employee)

        generate_and_deliver(
            template_filename="service_certificate.html",
            context=context,
            attach_to=("Employee", employee_name),
            file_label="Service Certificate",
            employee_doc=employee,
            email_subject="Your Service Certificate — Globex Digital Solutions",
            prefer_personal_email=False,
        )

        frappe.db.set_value(
            "Employee", employee_name, "custom_service_certificate_issued_at",
            date.today().strftime("%Y-%m-%d"),
        )
    except Exception as exc:
        log_error(
            f"_send_service_certificate_job: {employee_name} error={str(exc)[:200]}",
            "greytHR Letter Generation Error",
        )
