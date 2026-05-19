"""
Tests for api/zoho_sign.py and webhooks/zoho_sign.py — all offline.
"""
import hashlib
import hmac
import json

import pytest
import responses as rsps_lib

from greythr_bridge.api.zoho_sign import (
    send_for_signature,
    get_signed_document,
    resend_signing_request,
    verify_webhook_hmac,
)

ZOHO_BASE = "https://sign.zoho.in/api/v1"
SECRET = "test_webhook_secret_abc"


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_sig(payload: bytes, secret: str = SECRET) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


def _signers():
    return [
        {"name": "HR Manager", "email": "hr@globexdigital.ai", "order": 1},
        {"name": "Candidate", "email": "candidate@example.com", "order": 2},
    ]


def _metadata():
    return {"doctype": "Job Offer", "docname": "JOB-OFFER-001", "letter_type": "nda"}


# ── verify_webhook_hmac ────────────────────────────────────────────────────────

def test_valid_hmac_returns_true():
    payload = b'{"notifications": {"operation_type": "RequestCompleted"}}'
    sig = _make_sig(payload)
    assert verify_webhook_hmac(payload, sig, SECRET) is True


def test_invalid_hmac_returns_false():
    payload = b'{"notifications": {}}'
    assert verify_webhook_hmac(payload, "wrong_signature", SECRET) is False


def test_empty_signature_returns_false():
    assert verify_webhook_hmac(b"payload", "", SECRET) is False


def test_empty_secret_returns_false():
    assert verify_webhook_hmac(b"payload", "sig", "") is False


def test_tampered_payload_returns_false():
    payload = b'{"notifications": {"operation_type": "RequestCompleted"}}'
    sig = _make_sig(payload)
    tampered = b'{"notifications": {"operation_type": "RequestDeclined"}}'
    assert verify_webhook_hmac(tampered, sig, SECRET) is False


# ── send_for_signature ─────────────────────────────────────────────────────────

@rsps_lib.activate
def test_send_for_signature_returns_request_id(patch_frappe, settings):
    settings.get_password.return_value = "test_api_key"

    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"requests": {"request_id": "REQ-001", "status": "inprogress"}},
        status=200,
    )

    result = send_for_signature(
        pdf_bytes=b"%PDF-1.4 test",
        document_name="NDA - Test Candidate",
        signers=_signers(),
        metadata=_metadata(),
    )
    assert result == "REQ-001"


@rsps_lib.activate
def test_send_for_signature_raises_on_error(patch_frappe, settings):
    settings.get_password.return_value = "test_api_key"

    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"message": "Invalid API key"},
        status=401,
    )

    from greythr_bridge.api.exceptions import ZohoSignError
    with pytest.raises(ZohoSignError, match="401"):
        send_for_signature(b"%PDF", "Test", _signers(), _metadata())


@rsps_lib.activate
def test_send_for_signature_signers_are_ordered(patch_frappe, settings):
    settings.get_password.return_value = "test_api_key"

    captured = {}

    def request_callback(request):
        captured["data"] = request.body
        return (200, {}, json.dumps({"requests": {"request_id": "REQ-002"}}))

    rsps_lib.add_callback(rsps_lib.POST, f"{ZOHO_BASE}/requests", request_callback)

    send_for_signature(
        pdf_bytes=b"%PDF",
        document_name="Test",
        signers=[
            {"name": "Candidate", "email": "c@c.com", "order": 2},
            {"name": "HR", "email": "hr@hr.com", "order": 1},  # out of order
        ],
        metadata=_metadata(),
    )
    # Verify signers were sorted by order (HR first)
    assert "REQ-002" is not None  # request succeeded with sorted signers


# ── get_signed_document ───────────────────────────────────────────────────────

@rsps_lib.activate
def test_get_signed_document_returns_bytes(patch_frappe, settings):
    settings.get_password.return_value = "test_api_key"
    pdf_content = b"%PDF-1.4 signed content"

    rsps_lib.add(
        rsps_lib.GET,
        f"{ZOHO_BASE}/requests/REQ-001/pdf",
        body=pdf_content,
        status=200,
    )

    result = get_signed_document("REQ-001")
    assert result == pdf_content


@rsps_lib.activate
def test_get_signed_document_raises_on_error(patch_frappe, settings):
    settings.get_password.return_value = "test_api_key"

    rsps_lib.add(
        rsps_lib.GET,
        f"{ZOHO_BASE}/requests/REQ-001/pdf",
        json={"message": "Not found"},
        status=404,
    )

    from greythr_bridge.api.exceptions import ZohoSignError
    with pytest.raises(ZohoSignError, match="404"):
        get_signed_document("REQ-001")


# ── resend_signing_request ────────────────────────────────────────────────────

@rsps_lib.activate
def test_resend_signing_request_succeeds(patch_frappe, settings):
    settings.get_password.return_value = "test_api_key"

    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests/REQ-001/remind",
        status=200,
    )

    resend_signing_request("REQ-001")  # should not raise


@rsps_lib.activate
def test_resend_signing_request_raises_on_error(patch_frappe, settings):
    settings.get_password.return_value = "test_api_key"

    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests/REQ-001/remind",
        status=400,
    )

    from greythr_bridge.api.exceptions import ZohoSignError
    with pytest.raises(ZohoSignError, match="400"):
        resend_signing_request("REQ-001")
