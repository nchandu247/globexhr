"""
Document event handlers for Job Offer.

Registered in hooks.py under doc_events (wired in Phase 5).
All real work is enqueued — handlers must return within 5 seconds.
"""
import frappe
from ..api.zoho_sign import send_for_signature
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


def send_offer_letter(offer_name: str) -> None:
    """
    Generate the Offer Letter DOCX from the template and send to Zoho Sign.
    Zoho Sign converts to PDF server-side. Enqueued by on_offer_submitted.
    """
    try:
        doc = frappe.get_doc("Job Offer", offer_name)
        settings = frappe.get_single("greytHR Settings")

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

        frappe.db.set_value(
            "Job Offer", offer_name, "custom_zoho_sign_request_id", request_id
        )

    except Exception as exc:
        log_error(
            f"send_offer_letter: {offer_name} error={str(exc)[:200]}",
            "greytHR Offer Letter Send Error",
        )


@frappe.whitelist()
def force_resend_offer(offer_name: str) -> dict:
    """
    Manually trigger send_offer_letter for an already-submitted Job Offer.

    Useful for retrying after a configuration fix (e.g., Default Signatory
    was empty when the offer was first submitted). Only System Managers
    can call this — Frappe enforces via @frappe.whitelist() + role checks.

    Call from any logged-in browser session:
        https://<site>/api/method/greythr_bridge.hooks_handlers.job_offer.force_resend_offer?offer_name=HR-OFF-2026-00003
    """
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Only System Manager can force-resend offers.")

    frappe.enqueue(
        "greythr_bridge.hooks_handlers.job_offer.send_offer_letter",
        queue="short",
        offer_name=offer_name,
    )
    return {"status": "enqueued", "offer_name": offer_name}


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
