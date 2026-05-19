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

    Access tokens are valid for 1 hour. We cache them in greytHR Settings and
    refresh automatically when they expire (or are within 5 minutes of expiry).
    The refresh token is long-lived and never expires.

    Token endpoint (India DC): https://accounts.zoho.in/oauth/v2/token
    """
    from datetime import datetime, timedelta
    from frappe.utils.password import set_encrypted_password

    settings = frappe.get_single("greytHR Settings")
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
    set_encrypted_password("greytHR Settings", "greytHR Settings", "zoho_sign_access_token", access_token)
    frappe.db.set_value("greytHR Settings", "greytHR Settings", "zoho_sign_token_expires_at", expires_at_new)

    return access_token


def _headers() -> dict:
    return {"Authorization": f"Zoho-oauthtoken {_get_access_token()}"}


# ── public API ────────────────────────────────────────────────────────────────

def send_for_signature(
    pdf_bytes: bytes,
    document_name: str,
    signers: list[dict],
    metadata: dict,
    expiry_days: int = 30,
) -> str:
    """
    Upload a PDF to Zoho Sign and create a signing request.

    Args:
        pdf_bytes:     Raw PDF file content.
        document_name: Human-readable title for the document in Zoho Sign.
        signers:       [{"name": ..., "email": ..., "order": 1}, ...]
                       order=1 signs first (company signatory), order=2 signs after (candidate).
                       Signing is sequential (is_sequential=True).
        metadata:      Dict stored as the document description; passed back verbatim
                       in the webhook payload so we can route the callback correctly.
                       Should include: {"doctype": ..., "docname": ..., "letter_type": ...}
        expiry_days:   Signing link TTL in days (default 30).

    Returns:
        request_id (str) — store in custom_zoho_sign_*_request_id on the Job Offer.

    Raises:
        ZohoSignError on any non-2xx response or missing request_id.
    """
    actions = [
        {
            "action_type": "SIGN",
            "recipient_name": s["name"],
            "recipient_email": s["email"],
            "signing_order": s["order"],
            "verify_recipient": False,
        }
        for s in sorted(signers, key=lambda x: x["order"])
    ]

    request_data = {
        "requests": {
            "request_name": document_name,
            "expiration_days": expiry_days,
            "is_sequential": True,
            "description": json.dumps(metadata),  # routed back to us via webhook
            "actions": actions,
        }
    }

    resp = requests.post(
        f"{_BASE}/requests",
        headers=_headers(),
        files={"file": (f"{document_name}.pdf", pdf_bytes, "application/pdf")},
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
    return request_id


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


def resend_signing_request(request_id: str) -> None:
    """
    Resend the signing email to all pending signers on an existing request.
    Used by the "Resend" button on Job Offer and the stalled-signing scheduled task.
    """
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

    Computes HMAC-SHA256(key=secret, msg=payload_bytes) and compares
    with the received signature using a constant-time comparison to
    prevent timing attacks.

    NOTE: Confirm the exact header name Zoho Sign uses for the signature
    (e.g. X-Zoho-Sign-Signature) once your webhook is configured in the console.

    Returns True if valid, False if tampered or missing.
    """
    if not received_signature or not secret:
        return False
    expected = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)
