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

        signatory = frappe.get_doc("User", settings.default_signatory)
        applicant_email = _get_applicant_email(doc)

        offer_docx = _generate_document(doc)
        if not offer_docx:
            return

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


# ── helpers ───────────────────────────────────────────────────────────────────

def _get_applicant_email(offer_doc) -> str | None:
    """Get candidate email from the linked Job Applicant."""
    try:
        if offer_doc.applicant:
            applicant = frappe.get_doc("Job Applicant", offer_doc.applicant)
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
