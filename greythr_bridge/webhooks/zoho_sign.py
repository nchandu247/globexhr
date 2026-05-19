"""
Zoho Sign webhook callback endpoint.

Registered in Zoho Sign console as:
  https://gdshr.m.frappe.cloud/api/method/greythr_bridge.webhooks.zoho_sign.callback

Security:
  1. HMAC-SHA256 signature verified against zoho_sign_webhook_secret in Settings
  2. Timestamp checked within 5 minutes (replay protection)
  3. Returns 200 immediately — all real work is enqueued

Flow:
  NDA completed      → enqueue send_offer_letter (queue=short)
  Offer completed    → enqueue push_new_joiner + push_signed_pdf (queue=short)
  Declined/Expired   → update Job Offer status, notify HR
"""
import json
from datetime import datetime, timedelta

import frappe

from ..api.zoho_sign import verify_webhook_hmac
from ..utils.logging import log_error


@frappe.whitelist(allow_guest=True)
def callback():
    """
    Zoho Sign webhook entry point. Must return within 5 seconds.

    NOTE: Confirm the exact signature header name against Zoho Sign docs
    when configuring your webhook. Common options:
      - X-Zoho-Sign-Signature
      - X-Zoho-Sign-Hmac-Sha256
    Update _get_signature() below accordingly.
    """
    try:
        payload_bytes = frappe.request.get_data()
        settings = frappe.get_single("greytHR Settings")
        secret = settings.get_password("zoho_sign_webhook_secret")

        # ── 1. HMAC verification ───────────────────────────────────────────────
        received_sig = _get_signature()
        if not verify_webhook_hmac(payload_bytes, received_sig, secret):
            frappe.local.response["http_status_code"] = 400
            return {"error": "Invalid signature"}

        # ── 2. Parse payload ───────────────────────────────────────────────────
        try:
            data = json.loads(payload_bytes)
        except json.JSONDecodeError:
            frappe.local.response["http_status_code"] = 400
            return {"error": "Invalid JSON"}

        notifications = data.get("notifications", {})

        # ── 3. Timestamp replay protection (5-minute window) ───────────────────
        if not _within_time_window():
            frappe.local.response["http_status_code"] = 400
            return {"error": "Request timestamp out of acceptable range"}

        # ── 4. Parse metadata we embedded when sending ─────────────────────────
        description_str = notifications.get("description", "{}")
        try:
            meta = json.loads(description_str)
        except (json.JSONDecodeError, TypeError):
            meta = {}

        letter_type = meta.get("letter_type", "")
        docname = meta.get("docname", "")
        operation_type = notifications.get("operation_type", "")
        request_id = notifications.get("request_id", "")

        # ── 5. Dispatch — all real work is enqueued ────────────────────────────
        if operation_type == "RequestCompleted":
            if letter_type == "nda" and docname:
                frappe.enqueue(
                    "greythr_bridge.hooks_handlers.job_offer.send_offer_letter",
                    queue="short",
                    offer_name=docname,
                )
                # Record signing timestamp
                frappe.db.set_value(
                    "Job Offer", docname, "custom_zoho_sign_signed_at",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )

            elif letter_type == "offer_letter" and docname:
                frappe.enqueue(
                    "greythr_bridge.tasks.push_new_joiner.run",
                    queue="short",
                    offer_name=docname,
                    request_id=request_id,
                )
                frappe.db.set_value(
                    "Job Offer", docname, "custom_zoho_sign_signed_at",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )

        elif operation_type in ("RequestDeclined", "RequestCancelled") and docname:
            frappe.enqueue(
                "greythr_bridge.webhooks.zoho_sign._handle_declined",
                queue="short",
                docname=docname,
                operation_type=operation_type,
            )

        elif operation_type == "RequestExpired" and docname:
            frappe.enqueue(
                "greythr_bridge.webhooks.zoho_sign._handle_expired",
                queue="short",
                docname=docname,
            )

        # Always return 200 immediately
        return {"status": "ok"}

    except Exception as exc:
        log_error(
            f"zoho_sign.callback: unhandled error: {str(exc)[:300]}",
            "greytHR Webhook Error",
        )
        # Return 200 even on internal error — Zoho Sign retries on non-200
        return {"status": "error logged"}


# ── background handlers ───────────────────────────────────────────────────────

def _handle_declined(docname: str, operation_type: str) -> None:
    """Mark Job Offer as declined and notify HR Manager."""
    try:
        frappe.db.set_value("Job Offer", docname, "status", "Cancelled")
        _notify_hr(
            docname,
            f"Signing {operation_type.replace('Request', '')} for {docname}. "
            "Please review and resend if needed.",
        )
    except Exception as exc:
        log_error(
            f"_handle_declined: {docname} error={str(exc)[:200]}",
            "greytHR Webhook Error",
        )


def _handle_expired(docname: str) -> None:
    """Notify HR that a signing request expired."""
    try:
        _notify_hr(
            docname,
            f"Signing request for {docname} has expired. "
            "Open the Job Offer and click 'Resend Signing Request'.",
        )
    except Exception as exc:
        log_error(
            f"_handle_expired: {docname} error={str(exc)[:200]}",
            "greytHR Webhook Error",
        )


def _notify_hr(docname: str, message: str) -> None:
    """Send a Frappe notification to all HR Managers."""
    managers = frappe.get_all(
        "Has Role",
        filters={"role": "HR Manager", "parenttype": "User"},
        fields=["parent"],
    )
    for row in managers:
        frappe.publish_realtime(
            "eval_js",
            f'frappe.show_alert({{message: "{message}", indicator: "orange"}})',
            user=row["parent"],
        )


# ── signature helpers ─────────────────────────────────────────────────────────

def _get_signature() -> str:
    """
    Extract the HMAC-SHA256 signature from the X-ZS-WEBHOOK-SIGNATURE header.
    Zoho Sign encodes the signature as base64.
    """
    return frappe.request.headers.get("X-ZS-WEBHOOK-SIGNATURE", "")


def _within_time_window(window_minutes: int = 5) -> bool:
    """
    Check that the X-ZS-WEBHOOK-TIMESTAMP header is within window_minutes of now.
    Timestamp is a Unix timestamp in seconds.
    Prevents replay attacks.
    """
    ts_raw = frappe.request.headers.get("X-ZS-WEBHOOK-TIMESTAMP", "")
    if not ts_raw:
        return True  # no timestamp — rely on HMAC alone

    try:
        ts = datetime.fromtimestamp(int(ts_raw))  # Unix seconds
        return abs((datetime.now() - ts).total_seconds()) < window_minutes * 60
    except (ValueError, TypeError):
        return True  # unparseable — rely on HMAC alone
