"""
Document event handlers for Job Offer.

Registered in hooks.py under doc_events (wired in Phase 5).
All real work is enqueued — handlers must return within 5 seconds.
"""
import time

import frappe
from ..api.zoho_sign import send_for_signature, submit_request
from ..letters.merger import build_offer_context, merge_to_docx
from ..utils.logging import log_error


def on_offer_submitted(doc, method):
    """
    Triggered when a Job Offer is submitted.
    Sends the Offer Letter directly for signature (no NDA step).
    """
    settings = frappe.get_single("greytHR Settings")
    if not settings.enabled:
        return

    frappe.enqueue(
        "greythr_bridge.hooks_handlers.job_offer.send_offer_letter",
        queue="short",
        offer_name=doc.name,
    )


def send_offer_letter(offer_name: str, force: bool = False) -> None:
    """
    Generate the Offer Letter DOCX from the template and send to Zoho Sign.
    Zoho Sign converts to PDF server-side. Enqueued by on_offer_submitted.

    Idempotent: if the Job Offer already has custom_zoho_sign_request_id
    set, this is a no-op (the candidate has already been emailed). Pass
    force=True to bypass this check — only use after the existing Zoho
    request has been cancelled in the Zoho console.
    """
    try:
        doc = frappe.get_doc("Job Offer", offer_name)
        settings = frappe.get_single("greytHR Settings")

        # ── Idempotency check ────────────────────────────────────────────────
        existing_request = getattr(doc, "custom_zoho_sign_request_id", None)
        if existing_request and not force:
            log_error(
                f"send_offer_letter: {offer_name} skipped — already sent to "
                f"Zoho (request_id={existing_request}). Use force=True to "
                f"resend (cancel the existing Zoho request first).",
                "greytHR Offer Letter Skipped",
            )
            return

        # ── Pre-flight checks (fail-fast with clear messages) ────────────────
        if not settings.default_signatory:
            log_error(
                f"send_offer_letter: {offer_name} aborted — "
                f"greytHR Settings → Default Signatory is not configured. "
                f"Set it to a User (e.g. HR head) and resubmit.",
                "greytHR Offer Letter Config Error",
            )
            return

        applicant_email = _get_applicant_email(doc)
        if not applicant_email:
            log_error(
                f"send_offer_letter: {offer_name} aborted — "
                f"candidate email is empty. Set Applicant Email on Job Offer "
                f"or email_id on Job Applicant "
                f"{getattr(doc, 'job_applicant', '?')} and resubmit.",
                "greytHR Offer Letter Config Error",
            )
            return

        if not getattr(doc, "custom_date_of_joining", None):
            log_error(
                f"send_offer_letter: {offer_name} aborted — "
                f"Date of Joining is empty. Set 'Date of Joining' on the "
                f"Job Offer and resubmit. (Defense-in-depth — should also "
                f"be enforced at form level via reqd=1 fixture.)",
                "greytHR Offer Letter Config Error",
            )
            return

        signatory = frappe.get_doc("User", settings.default_signatory)
        if not signatory.full_name or not signatory.email:
            log_error(
                f"send_offer_letter: {offer_name} aborted — "
                f"default signatory User {settings.default_signatory} is missing "
                f"full_name or email.",
                "greytHR Offer Letter Config Error",
            )
            return

        # ── Generate document ────────────────────────────────────────────────
        offer_docx = _generate_document(doc)
        if not offer_docx:
            return  # _generate_document already logged

        # ── Send to Zoho Sign ────────────────────────────────────────────────
        signers = [
            {"name": signatory.full_name, "email": signatory.email, "order": 1},
            {"name": doc.applicant_name, "email": applicant_email, "order": 2},
        ]

        request_id = send_for_signature(
            file_bytes=offer_docx,
            document_name=f"Offer Letter - {doc.applicant_name}",
            signers=signers,
            metadata={
                "doctype": "Job Offer",
                "docname": offer_name,
                "letter_type": "offer_letter",
            },
            file_extension="docx",
        )

        # ── Persist request_id (with deadlock retry — concurrent jobs can race) ──
        _save_request_id_with_retry(offer_name, request_id)

    except Exception as exc:
        log_error(
            f"send_offer_letter: {offer_name} error={str(exc)[:200]}",
            "greytHR Offer Letter Send Error",
        )


@frappe.whitelist()
def submit_orphan_draft(request_id: str) -> dict:
    """
    Submit an existing Zoho Sign draft by request_id.

    Use this to recover the 'orphan drafts' created before we added the
    automatic submit step. Cancels nothing — just sends out the existing draft.

    Call from any logged-in browser session:
        https://<site>/api/method/greythr_bridge.hooks_handlers.job_offer.submit_orphan_draft?request_id=167481000000045108
    """
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Only System Manager can submit drafts.")

    try:
        submit_request(request_id)
        return {"status": "submitted", "request_id": request_id}
    except Exception as exc:
        log_error(
            f"submit_orphan_draft: {request_id} error={str(exc)[:200]}",
            "greytHR Zoho Sign Submit Error",
        )
        frappe.throw(f"Submit failed: {str(exc)[:200]}")


@frappe.whitelist()
def force_resend_offer(offer_name: str) -> dict:
    """
    Manually trigger send_offer_letter for an already-submitted Job Offer.

    Useful for retrying after a configuration fix (e.g., Default Signatory
    was empty when the offer was first submitted). Only System Managers
    can call this — Frappe enforces via @frappe.whitelist() + role checks.

    **WARNING:** This passes force=True, which bypasses the idempotency check
    and WILL create a duplicate Zoho Sign request if one already exists.
    Cancel the existing Zoho request first if you want a clean resend.

    Call from any logged-in browser session:
        https://<site>/api/method/greythr_bridge.hooks_handlers.job_offer.force_resend_offer?offer_name=HR-OFF-2026-00003
    """
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Only System Manager can force-resend offers.")

    frappe.enqueue(
        "greythr_bridge.hooks_handlers.job_offer.send_offer_letter",
        queue="short",
        offer_name=offer_name,
        force=True,
    )
    return {"status": "enqueued", "offer_name": offer_name, "force": True}


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_applicant_email(offer_doc) -> str | None:
    """
    Get candidate email. Prefers Job Offer's own `applicant_email` field
    (it's right there — no extra lookup), falls back to Job Applicant.email_id.
    """
    direct = getattr(offer_doc, "applicant_email", None)
    if direct:
        return direct
    try:
        job_applicant = getattr(offer_doc, "job_applicant", None)
        if job_applicant:
            applicant = frappe.get_doc("Job Applicant", job_applicant)
            return applicant.email_id
    except Exception:
        pass
    return None


def _generate_document(doc) -> bytes | None:
    """Merge the DOCX template with Job Offer data and return DOCX bytes."""
    try:
        context = build_offer_context(doc)
        return merge_to_docx("offer_letter.docx", context)
    except Exception as exc:
        log_error(
            f"_generate_document: doc={doc.name} error={str(exc)[:200]}",
            "greytHR Letter Generation Error",
        )
        return None


def _save_request_id_with_retry(offer_name: str, request_id: str, max_attempts: int = 3) -> None:
    """
    Write custom_zoho_sign_request_id with retry on MariaDB deadlock (errno 1213).

    Deadlock can occur if two send_offer_letter jobs race on the same Job Offer
    (e.g. accidental double-click of force_resend). MariaDB picks one transaction
    as the victim and aborts it; the victim retries with exponential backoff.

    If we still can't save after max_attempts, we MUST raise — the calling code
    needs to know we have a Zoho request_id that didn't get persisted (orphan).
    """
    for attempt in range(max_attempts):
        try:
            frappe.db.set_value(
                "Job Offer", offer_name, "custom_zoho_sign_request_id", request_id
            )
            frappe.db.commit()
            return
        except Exception as e:
            is_deadlock = "1213" in str(e) or "Deadlock" in str(e)
            if is_deadlock and attempt < max_attempts - 1:
                time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, 2s
                continue
            log_error(
                f"_save_request_id_with_retry: {offer_name} request_id={request_id} "
                f"failed after {attempt + 1} attempts. ORPHANED — manually copy "
                f"this request_id into the Job Offer's custom_zoho_sign_request_id "
                f"field. error={str(e)[:200]}",
                "greytHR Offer Letter Save Error",
            )
            raise
