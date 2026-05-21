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
    submit_request,
    get_signed_document,
    resend_signing_request,
    verify_webhook_hmac,
)

ZOHO_BASE = "https://sign.zoho.in/api/v1"
ZOHO_TOKEN_URL = "https://accounts.zoho.in/oauth/v2/token"
SECRET = "test_webhook_secret_abc"


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_sig(payload: bytes, secret: str = SECRET) -> str:
    import base64
    return base64.b64encode(
        hmac.new(secret.encode(), payload, hashlib.sha256).digest()
    ).decode("utf-8")


def _add_token_mock():
    """Register a mock OAuth token response."""
    rsps_lib.add(
        rsps_lib.POST,
        ZOHO_TOKEN_URL,
        json={"access_token": "test_access_token", "expires_in": 3600},
        status=200,
    )


def _add_submit_mock(request_id: str, status: int = 200):
    """Register a mock for the /requests/{request_id}/submit endpoint."""
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests/{request_id}/submit",
        json={"requests": {"request_id": request_id, "status": "inprogress"}},
        status=status,
    )


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
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"requests": {"request_id": "REQ-001", "status": "inprogress"}},
        status=200,
    )
    _add_submit_mock("REQ-001")

    result = send_for_signature(
        file_bytes=b"%PDF-1.4 test",
        document_name="NDA - Test Candidate",
        signers=_signers(),
        metadata=_metadata(),
    )
    assert result == "REQ-001"


@rsps_lib.activate
def test_send_for_signature_accepts_docx(patch_frappe, settings):
    """DOCX uploads should work — preferred path (no LibreOffice needed)."""
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"requests": {"request_id": "REQ-DOCX-001"}},
        status=200,
    )
    _add_submit_mock("REQ-DOCX-001")

    result = send_for_signature(
        file_bytes=b"PK\x03\x04 fake docx",
        document_name="Offer Letter - Test Candidate",
        signers=_signers(),
        metadata=_metadata(),
        file_extension="docx",
    )
    assert result == "REQ-DOCX-001"


@rsps_lib.activate
def test_send_for_signature_rejects_unknown_extension(patch_frappe, settings):
    """Unknown file_extension should raise before hitting Zoho."""
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"
    _add_token_mock()

    from greythr_bridge.api.exceptions import ZohoSignError
    with pytest.raises(ZohoSignError, match="Unsupported file_extension"):
        send_for_signature(
            file_bytes=b"data",
            document_name="X",
            signers=_signers(),
            metadata=_metadata(),
            file_extension="xyz",
        )


@rsps_lib.activate
def test_send_for_signature_raises_on_error(patch_frappe, settings):
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"message": "Bad request"},
        status=400,
    )

    from greythr_bridge.api.exceptions import ZohoSignError
    with pytest.raises(ZohoSignError, match="400"):
        send_for_signature(b"%PDF", "Test", _signers(), _metadata())


@rsps_lib.activate
def test_token_refresh_called_when_no_cache(patch_frappe, settings):
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"requests": {"request_id": "REQ-003"}},
        status=200,
    )
    _add_submit_mock("REQ-003")

    send_for_signature(b"%PDF", "Test", _signers(), _metadata())
    token_calls = [c for c in rsps_lib.calls if ZOHO_TOKEN_URL in c.request.url]
    # send_for_signature makes 2 API calls (create + submit). The mock's
    # frappe.db.set_value doesn't actually persist the cached token between
    # calls, so each request triggers a fresh OAuth refresh. The contract
    # being tested is "refresh DOES happen when cache is missing".
    assert len(token_calls) >= 1


# ── submit step (Phase 4 — fixes 'all drafts, no emails' bug) ────────────────

@rsps_lib.activate
def test_send_for_signature_calls_submit_after_create(patch_frappe, settings):
    """
    Regression test: send_for_signature MUST call the /submit endpoint
    after creating the request. Without this step, documents stay as DRAFT
    in Zoho Sign and no emails are sent to signers.
    """
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"requests": {"request_id": "REQ-SUBMIT-TEST"}},
        status=200,
    )
    _add_submit_mock("REQ-SUBMIT-TEST")

    send_for_signature(b"%PDF", "Test", _signers(), _metadata())

    submit_calls = [
        c for c in rsps_lib.calls
        if f"{ZOHO_BASE}/requests/REQ-SUBMIT-TEST/submit" in c.request.url
    ]
    assert len(submit_calls) == 1, "submit endpoint was not called exactly once"


@rsps_lib.activate
def test_send_for_signature_raises_when_submit_fails(patch_frappe, settings):
    """If the submit step fails, send_for_signature must raise — we should
    NOT return success for a stuck draft."""
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"requests": {"request_id": "REQ-STUCK"}},
        status=200,
    )
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests/REQ-STUCK/submit",
        json={"message": "Internal Server Error"},
        status=500,
    )

    from greythr_bridge.api.exceptions import ZohoSignError
    with pytest.raises(ZohoSignError, match="submit_request failed"):
        send_for_signature(b"%PDF", "Test", _signers(), _metadata())


@rsps_lib.activate
def test_send_for_signature_includes_signature_fields_for_each_signer(patch_frappe, settings):
    """
    Regression test for Zoho error 9101 'Add atleast one field for a signer'.
    Each action MUST include at least one Signature field or /submit fails.
    """
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(
        rsps_lib.POST,
        f"{ZOHO_BASE}/requests",
        json={"requests": {"request_id": "REQ-FIELDS-TEST"}},
        status=200,
    )
    _add_submit_mock("REQ-FIELDS-TEST")

    send_for_signature(b"%PDF", "Test", _signers(), _metadata())

    create_call = next(
        c for c in rsps_lib.calls
        if c.request.url == f"{ZOHO_BASE}/requests"
    )
    # The body is multipart/form-data; parse out the 'data' field.
    body_text = create_call.request.body.decode(errors="replace")
    assert '"fields"' in body_text, "fields array missing from request payload"
    assert '"Signature"' in body_text, "Signature field_type_name missing"
    assert body_text.count('"field_type_name"') == 2, "expected one field per signer"


@rsps_lib.activate
def test_submit_request_can_be_called_standalone(patch_frappe, settings):
    """Orphan-recovery path: submit an existing draft by request_id."""
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    _add_submit_mock("167481000000045108")

    # Should not raise
    submit_request("167481000000045108")

    submit_calls = [
        c for c in rsps_lib.calls
        if "/submit" in c.request.url
    ]
    assert len(submit_calls) == 1


# ── get_signed_document ───────────────────────────────────────────────────────

@rsps_lib.activate
def test_get_signed_document_returns_bytes(patch_frappe, settings):
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"
    pdf_content = b"%PDF-1.4 signed content"

    _add_token_mock()
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
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
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
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(rsps_lib.POST, f"{ZOHO_BASE}/requests/REQ-001/remind", status=200)

    resend_signing_request("REQ-001")  # should not raise


@rsps_lib.activate
def test_resend_signing_request_raises_on_error(patch_frappe, settings):
    settings.get_password.return_value = "test_refresh_token"
    settings.zoho_sign_access_token = None
    settings.zoho_sign_token_expires_at = None
    settings.zoho_sign_client_id = "client_id"

    _add_token_mock()
    rsps_lib.add(rsps_lib.POST, f"{ZOHO_BASE}/requests/REQ-001/remind", status=400)

    from greythr_bridge.api.exceptions import ZohoSignError
    with pytest.raises(ZohoSignError, match="400"):
        resend_signing_request("REQ-001")
