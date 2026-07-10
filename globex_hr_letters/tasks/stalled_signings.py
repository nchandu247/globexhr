"""
Detect HR Letters where Zoho Sign requests have stalled.

Runs daily. Finds HR Letters where:
  - status = "Sent for Signature"
  - modified older than the configured threshold (Settings, default 3 days)

Sends a reminder to pending signers via Zoho and notifies HR Managers.
"""
from datetime import datetime, timedelta

import frappe

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

    threshold_days = int(settings.stalled_threshold_days or 3)
    cutoff = (datetime.now() - timedelta(days=threshold_days)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    stalled = frappe.get_all(
        "HR Letter",
        filters={
            "status": "Sent for Signature",
            "modified": ["<", cutoff],
        },
        fields=["name", "letter_type", "zoho_request_id"],
    )

    if not stalled:
        return

    for letter in stalled:
        if letter.get("zoho_request_id"):
            try:
                resend_signing_request(letter["zoho_request_id"])
            except Exception as exc:
                log_error(
                    f"stalled_signings: remind failed for {letter['name']}: "
                    f"{str(exc)[:200]}",
                    "HR Letters Stalled Signings",
                )

    names = ", ".join(s["name"] for s in stalled)
    _notify_hr_managers(
        f"{len(stalled)} letter(s) pending signature for over {threshold_days} "
        f"days: {names}. Signers have been sent a reminder."
    )

    log_error(
        f"stalled_signings: {len(stalled)} stalled letters: {names[:200]}",
        "HR Letters Stalled Signings",
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
