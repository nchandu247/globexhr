"""
Detect Job Offers where Zoho Sign requests have stalled.

Runs daily. Finds Job Offers where:
  - custom_zoho_sign_request_id is set (offer letter was sent for signing)
  - custom_signed_pdf_pushed is False (signing never completed)
  - custom_zoho_sign_signed_at is null (no signature received)
  - offer is older than 28 days

Notifies HR Manager so they can resend or cancel.
"""
import frappe
from datetime import datetime, timedelta
from ..api.zoho_sign import resend_signing_request
from ..utils.logging import log_error


def run():
    """Scheduled entry point — called daily."""
    _check_stalled()


@frappe.whitelist()
def run_now():
    """Bench-callable for manual triggering."""
    frappe.enqueue(
        "globex_hr_letters.tasks.stalled_signings._check_stalled",
        queue="default",
    )


def _check_stalled() -> None:
    settings = frappe.get_single("HR Letters Settings")
    if not settings.enabled:
        return

    cutoff = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d %H:%M:%S")

    stalled = frappe.get_all(
        "Job Offer",
        filters={
            "custom_zoho_sign_request_id": ["!=", ""],
            "custom_signed_pdf_pushed": 0,
            "custom_zoho_sign_signed_at": ["in", ["", None]],
            "creation": ["<", cutoff],
        },
        fields=["name", "applicant_name", "custom_zoho_sign_request_id"],
    )

    if not stalled:
        return

    names = ", ".join(f"{s['name']} ({s['applicant_name']})" for s in stalled)
    _notify_hr_managers(
        f"{len(stalled)} offer letter(s) have been pending signature for over 28 days: "
        f"{names}. Open each Job Offer and click 'Resend Signing Request' or cancel."
    )

    log_error(
        f"stalled_signings: {len(stalled)} stalled offers found: {names[:200]}",
        "greytHR Stalled Signings",
    )


def _notify_hr_managers(message: str) -> None:
    managers = frappe.get_all(
        "Has Role",
        filters={"role": "HR Manager", "parenttype": "User"},
        fields=["parent"],
    )
    for row in managers:
        frappe.publish_realtime(
            "eval_js",
            f'frappe.show_alert({{message: {frappe.as_json(message)}, indicator: "orange"}})',
            user=row["parent"],
        )
