"""
Document event handlers for Job Offer.

Registered in hooks.py under doc_events (wired in Phase 5).
All real work is enqueued — handlers must return within 5 seconds.
"""
import frappe
from ..api.zoho_sign import send_for_signature
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
    Generate and send the Offer Letter after NDA is fully signed.
    Enqueued by the Zoho Sign webhook handler on NDA completion.
    """
    try:
        doc = frappe.get_doc("Job Offer", offer_name)
        settings = frappe.get_single("greytHR Settings")

        signatory = frappe.get_doc("User", settings.default_signatory)
        applicant_email = _get_applicant_email(doc)

        offer_pdf = _generate_pdf(doc, "Offer Letter")
        if not offer_pdf:
            return

        signers = [
            {"name": signatory.full_name, "email": signatory.email, "order": 1},
            {"name": doc.applicant_name, "email": applicant_email, "order": 2},
        ]

        request_id = send_for_signature(
            pdf_bytes=offer_pdf,
            document_name=f"Offer Letter - {doc.applicant_name}",
            signers=signers,
            metadata={
                "doctype": "Job Offer",
                "docname": offer_name,
                "letter_type": "offer_letter",
            },
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


def _generate_pdf(doc, print_format_name: str) -> bytes | None:
    """Generate PDF bytes from a Frappe Print Format."""
    try:
        from frappe.utils.pdf import get_pdf
        html = frappe.get_print(
            doctype=doc.doctype,
            name=doc.name,
            print_format=print_format_name,
        )
        return get_pdf(html)
    except Exception as exc:
        log_error(
            f"_generate_pdf: format={print_format_name!r} doc={doc.name} "
            f"error={str(exc)[:200]}",
            "greytHR PDF Generation Error",
        )
        return None
