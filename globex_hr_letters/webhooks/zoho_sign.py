"""
Zoho Sign webhook callback endpoint.

Registered in Zoho Sign console as:
  https://<site>/api/method/globex_hr_letters.webhooks.zoho_sign.callback

Security:
  1. HMAC-SHA256 signature verified against zoho_sign_webhook_secret in Settings
  2. Timestamp checked within 5 minutes (replay protection)
  3. Returns 200 immediately — all real work is enqueued

Flow:
  RequestCompleted   → HR Letter status = Signed, signed PDF attached
  Declined/Cancelled → HR notified (cancel + amend to resend)
  RequestExpired     → HR notified
"""
import json
from datetime import datetime

import frappe

from ..api.zoho_sign import verify_webhook_hmac
from ..utils.logging import log_error


@frappe.whitelist(allow_guest=True)
def callback():
    """Zoho Sign webhook entry point. Must return within 5 seconds."""
    try:
        payload_bytes = frappe.request.get_data()
        settings = frappe.get_single("HR Letters Settings")
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

        # ── 4. Identify the HR Letter by request_id ────────────────────────────
        operation_type = notifications.get("operation_type", "")
        request_id = notifications.get("request_id", "")
        letter_name = _resolve_hr_letter(request_id)

        # ── 5. Dispatch — all real work is enqueued ────────────────────────────
        if not letter_name:
            return {"status": "ok"}  # not ours — ack so Zoho stops retrying

        if operation_type == "RequestCompleted":
            frappe.enqueue(
                "globex_hr_letters.webhooks.zoho_sign._handle_completed",
                queue="short",
                letter_name=letter_name,
                request_id=request_id,
            )
        elif operation_type in ("RequestDeclined", "RequestCancelled"):
            frappe.enqueue(
                "globex_hr_letters.webhooks.zoho_sign._handle_declined",
                queue="short",
                letter_name=letter_name,
                operation_type=operation_type,
            )
        elif operation_type == "RequestExpired":
            frappe.enqueue(
                "globex_hr_letters.webhooks.zoho_sign._handle_expired",
                queue="short",
                letter_name=letter_name,
            )

        # Always return 200 immediately
        return {"status": "ok"}

    except Exception as exc:
        log_error(
            f"zoho_sign.callback: unhandled error: {str(exc)[:300]}",
            "HR Letters Webhook Error",
        )
        # Return 200 even on internal error — Zoho Sign retries on non-200
        return {"status": "error logged"}


# ── defensive db helpers ──────────────────────────────────────────────────────

def _safe_set_value(doctype: str, name: str, field: str, value) -> bool:
    """
    Set a single field on a document, isolated from other writes.

    Why: `frappe.db.set_value` to a non-existent field raises a SQL/meta
    error. Inside a transaction that already updated other fields, MariaDB
    rolls back the WHOLE transaction while the outer try/except returns
    200 OK — nothing saved, stuck status. This helper:
      1. Checks the field exists in the doctype meta first
      2. Commits on success (per-field durability)
      3. Rolls back + logs on failure (next call still works)
    """
    try:
        if not frappe.get_meta(doctype).has_field(field):
            log_error(
                f"_safe_set_value: skipped — field '{field}' missing on '{doctype}'. "
                f"docname={name}",
                "HR Letters Webhook Field Missing",
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
            "HR Letters Webhook Update Error",
        )
        return False


# ── background handlers ───────────────────────────────────────────────────────

def _handle_completed(letter_name: str, request_id: str) -> None:
    """Mark the HR Letter Signed and attach the fully-signed PDF from Zoho.

    The signed PDF is the legally-binding artifact — retained on the HR
    Letter (and the Employee record for employee letters) regardless of
    Zoho's own retention."""
    try:
        from ..api.zoho_sign import get_signed_document
        from ..letters.delivery import attach_pdf

        _safe_set_value("HR Letter", letter_name, "status", "Signed")
        _safe_set_value(
            "HR Letter", letter_name, "issued_on",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        letter = frappe.get_doc("HR Letter", letter_name)

        # A signed candidate letter is an accepted offer (decision A2,
        # 2026-07-13). Runs before the PDF download so a Zoho fetch
        # failure can't lose the acceptance.
        if letter.recipient_type == "Job Applicant":
            _mark_offer_accepted(letter)

        pdf_bytes = get_signed_document(request_id)
        if not pdf_bytes:
            log_error(
                f"_handle_completed: {letter_name} got empty signed PDF",
                "HR Letters Webhook Error",
            )
            return

        letter_type = letter.letter_type.replace("/", "-")
        file_doc = attach_pdf(
            f"{letter_type} - Signed - {letter.recipient}.pdf",
            pdf_bytes,
            "HR Letter",
            letter_name,
            # Signed PDF also lands on the person's record — Employee or
            # Job Applicant — so the signed-offer trail follows them.
            also_attach_to=(
                (letter.recipient_type, letter.recipient)
                if letter.recipient_type in ("Employee", "Job Applicant")
                else None
            ),
        )
        _safe_set_value("HR Letter", letter_name, "generated_pdf", file_doc.file_url)
    except Exception as exc:
        log_error(
            f"_handle_completed: {letter_name} error={str(exc)[:200]}",
            "HR Letters Webhook Error",
        )


def _handle_declined(letter_name: str, operation_type: str) -> None:
    """Surface a declined/cancelled signing to HR."""
    try:
        _notify_hr(
            f"Signing {operation_type.replace('Request', '').lower()} for "
            f"{letter_name}. Review the HR Letter and cancel + amend to resend.",
        )
        log_error(
            f"_handle_declined: {letter_name} {operation_type}",
            "HR Letters Signing Declined",
        )
    except Exception as exc:
        log_error(
            f"_handle_declined: {letter_name} error={str(exc)[:200]}",
            "HR Letters Webhook Error",
        )


def _handle_expired(letter_name: str) -> None:
    """Notify HR that a signing request expired."""
    try:
        _notify_hr(
            f"Signing request for {letter_name} has expired. "
            "Open the HR Letter and click 'Resend Signing Request'.",
        )
    except Exception as exc:
        log_error(
            f"_handle_expired: {letter_name} error={str(exc)[:200]}",
            "HR Letters Webhook Error",
        )


def _mark_offer_accepted(letter) -> None:
    """
    Decision A2 (2026-07-13): candidate signing = offer accepted. Flip the
    Job Applicant (and their latest Job Offer, if any) to Accepted and
    open a ToDo per HR Manager so the joining-day onboarding — create
    Employee, record greytHR ID — has a worklist instead of relying on
    someone noticing the Signed letter.
    """
    _safe_set_value("Job Applicant", letter.recipient, "status", "Accepted")
    try:
        offers = frappe.get_all(
            "Job Offer",
            filters={"job_applicant": letter.recipient, "docstatus": ["<", 2]},
            fields=["name"],
            order_by="modified desc",
            limit=1,
        )
        if offers:
            _safe_set_value("Job Offer", offers[0]["name"], "status", "Accepted")

        for user in _hr_manager_users():
            todo = frappe.new_doc("ToDo")
            todo.allocated_to = user
            todo.reference_type = "HR Letter"
            todo.reference_name = letter.name
            todo.description = (
                f"Candidate signed {letter.letter_type} ({letter.name}). "
                f"On joining day: onboard {letter.recipient} as an Employee "
                "and record the greytHR Employee ID."
            )
            todo.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as exc:
        try:
            frappe.db.rollback()
        except Exception:
            pass
        log_error(
            f"_mark_offer_accepted: {letter.name} error={str(exc)[:200]}",
            "HR Letters Webhook Error",
        )


def _hr_manager_users() -> list:
    """User IDs holding the HR Manager role."""
    rows = frappe.get_all(
        "Has Role",
        filters={"role": "HR Manager", "parenttype": "User"},
        fields=["parent"],
    )
    return [row["parent"] for row in rows]


def _notify_hr(message: str) -> None:
    """Send a Frappe alert to all HR Managers."""
    for user in _hr_manager_users():
        frappe.publish_realtime(
            "eval_js",
            f'frappe.show_alert({{message: {frappe.as_json(message)}, indicator: "orange"}})',
            user=user,
        )


# ── source-document lookup ────────────────────────────────────────────────────

def _resolve_hr_letter(request_id: str) -> str:
    """Find the HR Letter this Zoho Sign request_id belongs to ('' if none)."""
    if not request_id:
        return ""
    return frappe.db.get_value(
        "HR Letter", {"zoho_request_id": request_id}, "name"
    ) or ""


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
