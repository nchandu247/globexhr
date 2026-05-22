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

        # ── 4. Identify the source document by request_id ──────────────────────
        # We no longer parse the description field (Zoho's char filter rejects
        # JSON). Instead, look up which Job Offer / future doc this request_id
        # belongs to using the custom_zoho_sign_* fields we set when sending.
        operation_type = notifications.get("operation_type", "")
        request_id = notifications.get("request_id", "")
        docname, letter_type = _resolve_source_doc(request_id)

        # ── 5. Dispatch — all real work is enqueued ────────────────────────────
        if operation_type == "RequestCompleted":
            if letter_type == "offer_letter" and docname:
                # Update Job Offer status + signed timestamp INDEPENDENTLY.
                # Each set_value commits on success — see _safe_set_value
                # docstring for the silent-failure history that drove this.
                _safe_set_value(
                    "Job Offer", docname, "status", "Accepted"
                )
                _safe_set_value(
                    "Job Offer", docname, "custom_zoho_sign_signed_at",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                )
                # Download the fully-signed PDF from Zoho and attach to the
                # Job Offer as a File record. Done in background so webhook
                # response stays under 5 seconds.
                frappe.enqueue(
                    "greythr_bridge.webhooks.zoho_sign._download_and_attach_signed_pdf",
                    queue="short",
                    docname=docname,
                    request_id=request_id,
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


# ── defensive db helpers ──────────────────────────────────────────────────────

def _safe_set_value(doctype: str, name: str, field: str, value) -> bool:
    """
    Set a single field on a document, isolated from other writes.

    Why this exists (root cause of 2026-05-22 silent webhook bug):
    `frappe.db.set_value` to a non-existent field raises a SQL/meta error.
    When called inside a transaction that already updated other fields
    (e.g. status), MariaDB rolls back the WHOLE transaction. The outer
    try/except in callback() swallows the error and returns 200 OK to
    Zoho — but no fields actually saved. Stuck on "Awaiting Response".

    This helper:
      1. Checks the field exists in the doctype meta first (avoids SQL error)
      2. Commits on success (per-field durability — partial failure is OK)
      3. Rolls back + logs on failure (next call still works)

    Returns True if the value was saved, False if skipped/failed.
    """
    try:
        if not frappe.get_meta(doctype).has_field(field):
            log_error(
                f"_safe_set_value: skipped — field '{field}' missing on '{doctype}'. "
                f"Add it as a Custom Field (check fixtures/custom_field.json). "
                f"docname={name}",
                "greytHR Webhook Field Missing",
            )
            return False
        frappe.db.set_value(doctype, name, field, value)
        frappe.db.commit()
        return True
    except Exception as exc:
        try:
            frappe.db.rollback()
        except Exception:
            pass
        log_error(
            f"_safe_set_value: UPDATE failed for {doctype}.{field} on {name}: "
            f"{str(exc)[:200]}",
            "greytHR Webhook Update Error",
        )
        return False


# ── background handlers ───────────────────────────────────────────────────────

def _handle_declined(docname: str, operation_type: str) -> None:
    """Mark Job Offer as Rejected and notify HR Manager."""
    try:
        # Frappe HR Job Offer.status values: Awaiting Response, Accepted, Rejected
        _safe_set_value("Job Offer", docname, "status", "Rejected")
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


def _download_and_attach_signed_pdf(docname: str, request_id: str) -> None:
    """
    Background: download the fully-signed PDF from Zoho Sign and attach it
    as a File against the Job Offer record.

    Called from the on-RequestCompleted webhook path. The signed PDF is the
    legally-binding artifact we need to retain regardless of whether Zoho
    Sign data is retained long-term.
    """
    try:
        from ..api.zoho_sign import get_signed_document

        pdf_bytes = get_signed_document(request_id)
        if not pdf_bytes:
            log_error(
                f"_download_and_attach_signed_pdf: {docname} got empty PDF",
                "greytHR Webhook Error",
            )
            return

        # Save the PDF as a Frappe File attached to the Job Offer
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"Offer Letter - Signed - {docname}.pdf",
            "attached_to_doctype": "Job Offer",
            "attached_to_name": docname,
            "content": pdf_bytes,
            "is_private": 1,
        })
        file_doc.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Job Offer", docname, "custom_signed_pdf_pushed", 1
        )
    except Exception as exc:
        log_error(
            f"_download_and_attach_signed_pdf: {docname} error={str(exc)[:200]}",
            "greytHR Webhook Error",
        )


@frappe.whitelist()
def force_complete_offer(offer_name: str) -> dict:
    """
    System-Manager-only endpoint to manually finalise a Job Offer where the
    webhook either didn't fire or fired against an older code path that
    never updated the Status field.

    What it does (idempotent):
      1. Sets Job Offer.status = "Accepted"
      2. Sets custom_zoho_sign_signed_at = now (if not already set)
      3. Downloads + attaches the signed PDF from Zoho (if request_id present)

    Use this once per stranded offer (Rajesh, Bhuvan, Rajyalakshmi).
    """
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Only System Manager can force-complete offers.")

    offer = frappe.get_doc("Job Offer", offer_name)
    request_id = getattr(offer, "custom_zoho_sign_request_id", None)

    # Per-field writes via _safe_set_value so a missing field doesn't
    # roll back the status update.
    _safe_set_value("Job Offer", offer_name, "status", "Accepted")
    if not getattr(offer, "custom_zoho_sign_signed_at", None):
        _safe_set_value(
            "Job Offer", offer_name, "custom_zoho_sign_signed_at",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    if request_id:
        frappe.enqueue(
            "greythr_bridge.webhooks.zoho_sign._download_and_attach_signed_pdf",
            queue="short",
            docname=offer_name,
            request_id=request_id,
        )

    return {
        "status": "completed",
        "offer_name": offer_name,
        "request_id": request_id,
        "signed_pdf_enqueued": bool(request_id),
    }


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


# ── source-document lookup ────────────────────────────────────────────────────

def _resolve_source_doc(request_id: str) -> tuple[str, str]:
    """
    Find which document this Zoho Sign request_id belongs to.

    Returns (docname, letter_type) or ("", "") if no match.

    Priority order — add new letter types here as we wire them in later phases:
      1. Job Offer.custom_zoho_sign_request_id      -> offer_letter
      2. Job Offer.custom_zoho_sign_nda_request_id  -> nda (NOT used in Phase 5)
    """
    if not request_id:
        return ("", "")

    # Job Offer — offer letter
    offer_name = frappe.db.get_value(
        "Job Offer", {"custom_zoho_sign_request_id": request_id}, "name"
    )
    if offer_name:
        return (offer_name, "offer_letter")

    # Job Offer — NDA (reserved for future use; currently NDA flow is disabled)
    nda_offer = frappe.db.get_value(
        "Job Offer", {"custom_zoho_sign_nda_request_id": request_id}, "name"
    )
    if nda_offer:
        return (nda_offer, "nda")

    return ("", "")


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
