"""
Zoho Sign REST API wrapper.

All Zoho Sign calls go through this module — never call Zoho Sign directly
from tasks, hooks, or webhooks (convention 3 in CLAUDE.md).

India DC base URL: https://sign.zoho.in/api/v1
Auth: Zoho-oauthtoken {api_key} in Authorization header.

NOTE: Verify the exact Authorization header format and webhook signature header
name against https://www.zoho.com/sign/api/ once your API key is available.
The structure here follows Zoho Sign REST API v1 conventions.
"""
import hashlib
import hmac
import json
import frappe
import requests

from .exceptions import ZohoSignError

_BASE = "https://sign.zoho.in/api/v1"
_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"


# ── OAuth token management ────────────────────────────────────────────────────

def _get_access_token() -> str:
    """
    Return a valid Zoho Sign access token, refreshing via OAuth if expired.

    Access tokens are valid for 1 hour. We cache them in HR Letters Settings and
    refresh automatically when they expire (or are within 5 minutes of expiry).
    The refresh token is long-lived and never expires.

    Token endpoint (India DC): https://accounts.zoho.in/oauth/v2/token
    """
    from datetime import datetime, timedelta
    from frappe.utils.password import set_encrypted_password

    settings = frappe.get_single("HR Letters Settings")
    now = datetime.now()

    # Check cached access token
    expires_at_str = settings.zoho_sign_token_expires_at
    expires_at = None
    if expires_at_str:
        try:
            expires_at = datetime.strptime(expires_at_str, "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            expires_at = None

    if (
        settings.zoho_sign_access_token
        and expires_at
        and expires_at > now + timedelta(minutes=5)
    ):
        return settings.get_password("zoho_sign_access_token")

    # Access token missing or expiring — exchange refresh token for new access token
    resp = requests.post(
        _TOKEN_URL,
        params={
            "grant_type":    "refresh_token",
            "client_id":     settings.zoho_sign_client_id,
            "client_secret": settings.get_password("zoho_sign_client_secret"),
            "refresh_token": settings.get_password("zoho_sign_refresh_token"),
        },
        timeout=15,
    )

    if resp.status_code != 200:
        raise ZohoSignError(
            f"Zoho Sign token refresh failed: HTTP {resp.status_code}: {resp.text[:200]}"
        )

    token_data = resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise ZohoSignError(f"No access_token in Zoho Sign response: {resp.text[:200]}")

    expires_in = token_data.get("expires_in", 3600)
    expires_at_new = (now + timedelta(seconds=expires_in)).strftime("%Y-%m-%d %H:%M:%S")

    # Store as encrypted password; store expiry as plain string
    set_encrypted_password("HR Letters Settings", "HR Letters Settings", "zoho_sign_access_token", access_token)
    frappe.db.set_value("HR Letters Settings", "HR Letters Settings", "zoho_sign_token_expires_at", expires_at_new)

    return access_token


def _headers() -> dict:
    return {"Authorization": f"Zoho-oauthtoken {_get_access_token()}"}


# ── public API ────────────────────────────────────────────────────────────────

_MIME_BY_EXT = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc":  "application/msword",
    "rtf":  "application/rtf",
}


def send_for_signature(
    file_bytes: bytes,
    document_name: str,
    signers: list[dict],
    metadata: dict,
    expiry_days: int = 30,
    file_extension: str = "pdf",
) -> str:
    """
    Upload a document to Zoho Sign and create a signing request.

    Zoho Sign accepts PDF, DOCX, DOC, RTF, JPG, PNG. For DOCX uploads,
    Zoho converts to PDF server-side — preferred because we don't need
    LibreOffice on the bench.

    Args:
        file_bytes:     Raw file content.
        document_name:  Human-readable title for the document in Zoho Sign.
        signers:        [{"name": ..., "email": ..., "order": 1}, ...]
                        order=1 signs first (company signatory),
                        order=2 signs after (candidate). Sequential.
        metadata:       Dict stored as document description; round-tripped
                        verbatim in the webhook payload so we can route
                        the callback. Include: {doctype, docname, letter_type}.
        expiry_days:    Signing link TTL in days (default 30).
        file_extension: "pdf" | "docx" | "doc" | "rtf" — controls upload
                        filename + MIME type (default "pdf").

    Returns:
        request_id (str) — store on the Job Offer.

    Raises:
        ZohoSignError on any non-2xx response or missing request_id.
    """
    ext = file_extension.lower().lstrip(".")
    mime_type = _MIME_BY_EXT.get(ext)
    if not mime_type:
        raise ZohoSignError(
            f"Unsupported file_extension '{file_extension}'. "
            f"Supported: {sorted(_MIME_BY_EXT.keys())}"
        )

    actions = [
        {
            "action_type": "SIGN",
            "recipient_name": s["name"],
            "recipient_email": s["email"],
            "signing_order": s["order"],
            "verify_recipient": False,
            # Signature fields are auto-detected from {{S:R1*}} / {{S:R2*}} text
            # tags embedded in the document (see letters/merger.py:_append_zoho_tags).
            # Hardcoded coordinate-based fields were tried in commit fc4a4dd but
            # failed with Zoho error 4004 because they need document_id/action_id
            # that only exist after the document is created.
        }
        for s in sorted(signers, key=lambda x: x["order"])
    ]

    # Zoho Sign's `description` field rejects JSON specials (quotes, braces,
    # colons) with error code 9013 "invalid characters". Use plain text and
    # let the webhook look up the source doc by request_id (see webhooks/zoho_sign.py).
    # `metadata` is kept in the signature for caller-side context only — it is
    # NOT sent to Zoho.
    _ = metadata  # silence unused-arg lint
    request_data = {
        "requests": {
            "request_name": document_name,
            "expiration_days": expiry_days,
            "is_sequential": True,
            "description": document_name,
            "actions": actions,
        }
    }

    resp = requests.post(
        f"{_BASE}/requests",
        headers=_headers(),
        files={"file": (f"{document_name}.{ext}", file_bytes, mime_type)},
        data={"data": json.dumps(request_data)},
        timeout=30,
    )

    if resp.status_code not in (200, 201):
        raise ZohoSignError(
            f"send_for_signature failed: HTTP {resp.status_code}: {resp.text[:200]}"
        )

    result = resp.json()
    request_id = result.get("requests", {}).get("request_id")
    if not request_id:
        raise ZohoSignError(
            f"No request_id in Zoho Sign response: {resp.text[:200]}"
        )

    # ── Step 2: SUBMIT the draft so signers actually receive emails ───────────
    # Zoho Sign's /requests endpoint only CREATES a draft. Without this submit
    # call, the document sits in Zoho as DRAFT forever and no emails go out.
    submit_request(request_id)

    return request_id


def submit_request(request_id: str) -> None:
    """
    Submit a draft Zoho Sign request — triggers the email to the first signer.

    Use directly to recover an orphan draft. Normally called automatically
    by send_for_signature.
    """
    resp = requests.post(
        f"{_BASE}/requests/{request_id}/submit",
        headers=_headers(),
        timeout=30,
    )
    if resp.status_code not in (200, 201, 204):
        raise ZohoSignError(
            f"submit_request failed for {request_id}: "
            f"HTTP {resp.status_code}: {resp.text[:200]}"
        )


def get_signed_document(request_id: str) -> bytes:
    """
    Download the completed signed PDF as raw bytes.

    Call this only after the webhook confirms RequestCompleted.
    """
    resp = requests.get(
        f"{_BASE}/requests/{request_id}/pdf",
        headers=_headers(),
        timeout=30,
    )
    if resp.status_code != 200:
        raise ZohoSignError(
            f"get_signed_document failed: HTTP {resp.status_code}: {resp.text[:200]}"
        )
    return resp.content


@frappe.whitelist()
def resend_signing_request(request_id: str) -> None:
    """
    Resend the signing email to all pending signers on an existing request.
    Used by the "Resend Signing Request" button on HR Letter and the
    stalled-signings scheduled task. HR Manager / System Manager only when
    called over HTTP.
    """
    roles = frappe.get_roles(frappe.session.user)
    if "HR Manager" not in roles and "System Manager" not in roles and frappe.session.user != "Administrator":
        frappe.throw("Only HR Manager or System Manager can resend signing requests.")
    resp = requests.post(
        f"{_BASE}/requests/{request_id}/remind",
        headers=_headers(),
        timeout=30,
    )
    if resp.status_code not in (200, 204):
        raise ZohoSignError(
            f"resend_signing_request failed: HTTP {resp.status_code}: {resp.text[:200]}"
        )


def verify_webhook_hmac(payload_bytes: bytes, received_signature: str, secret: str) -> bool:
    """
    Verify a Zoho Sign webhook HMAC-SHA256 signature.

    Zoho Sign sends the signature in the X-ZS-WEBHOOK-SIGNATURE header,
    encoded as base64 (not hex). The HMAC is computed over the raw request body
    using the webhook secret (whsec_... format) as the key.

    Uses constant-time comparison to prevent timing attacks.

    Returns True if valid, False if tampered or missing.
    """
    import base64
    if not received_signature or not secret:
        return False
    expected = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return hmac.compare_digest(expected, received_signature)
