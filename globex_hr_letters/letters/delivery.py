"""
Attachment + email delivery helpers for generated letters.

Used by letters/engine.py after a PDF is rendered:
  1. PDF attached as a private File against the HR Letter (and optionally a
     second record, e.g. the Employee, so the letter lives on the person's
     permanent record too)
  2. Email sent to the recipient (with a fallback chain for the address)

Callers MUST invoke email sending from inside frappe.enqueue() so button
clicks return within seconds.
"""
import frappe

from ..utils.logging import log_error


def attach_pdf(file_name: str, pdf_bytes: bytes, doctype: str, docname: str,
               also_attach_to: tuple | None = None):
    """
    Attach *pdf_bytes* as a private File to (doctype, docname).

    Returns the primary File doc. When *also_attach_to* is given, a second
    File record is created that LINKS to the primary file's URL instead of
    writing new content — avoids the hash-suffix bug where Frappe's storage
    layer appends "70526e" etc. when writing a duplicate filename. Same
    clean filename on both attachments, single physical file on disk.
    """
    primary_file = _create_file_attachment(file_name, pdf_bytes, doctype, docname)

    if also_attach_to:
        also_dt, also_dn = also_attach_to
        try:
            _create_file_attachment(
                file_name, pdf_bytes, also_dt, also_dn,
                file_url=getattr(primary_file, "file_url", None),
            )
        except Exception as exc:
            # Secondary attachment is best-effort — don't fail the whole
            # letter generation if it errors.
            log_error(
                f"delivery: secondary attach to {also_dt}/{also_dn} "
                f"failed: {str(exc)[:200]}",
                "HR Letters Secondary Attach Error",
            )

    return primary_file


def email_letter(recipient_email: str, file_name: str, pdf_bytes: bytes,
                 file_label: str, reference: tuple,
                 email_subject: str = "", email_body_html: str = "") -> bool:
    """
    Email the letter PDF to *recipient_email*. Returns True when sent.

    reference: (doctype, docname) recorded on the Communication for audit.
    """
    doctype, docname = reference
    if not recipient_email:
        log_error(
            f"delivery: no email address; PDF attached to {docname} but not emailed.",
            "HR Letters Email Skipped",
        )
        return False

    try:
        frappe.sendmail(
            recipients=[recipient_email],
            subject=email_subject or f"{file_label} — Globex Digital Solutions",
            message=email_body_html or _default_email_body(file_label),
            attachments=[{"fname": file_name, "fcontent": pdf_bytes}],
            now=True,
            reference_doctype=doctype,
            reference_name=docname,
        )
        return True
    except Exception as exc:
        log_error(
            f"delivery: sendmail failed for {docname}: {str(exc)[:200]}",
            "HR Letters Email Error",
        )
        return False


def resolve_recipient_email(recipient_type: str, recipient_doc,
                            prefer_personal: bool = False) -> str:
    """
    Email-address fallback chain.

    Employee letters (prefer_personal=False):
        company_email → personal_email → user_id → ""
    Exit letters (prefer_personal=True), where company_email may already be
    deactivated:
        personal_email → company_email → user_id → ""
    Job Applicant letters: email_id → ""
    """
    if recipient_type == "Job Applicant":
        return getattr(recipient_doc, "email_id", None) or ""

    company = getattr(recipient_doc, "company_email", None) or None
    personal = getattr(recipient_doc, "personal_email", None) or None
    user = getattr(recipient_doc, "user_id", None) or None
    if prefer_personal:
        return personal or company or user or ""
    return company or personal or user or ""


def _create_file_attachment(file_name: str, pdf_bytes: bytes,
                            doctype: str, docname: str,
                            file_url: str | None = None):
    """
    Insert a File doc attaching to (doctype, docname).

    Two modes:
      - WRITE mode (default, file_url=None): writes pdf_bytes to disk via
        Frappe's storage layer. Used for the primary attachment.
      - LINK mode (file_url provided): no new file written; the new File
        doc just references the existing file_url. Used for secondary
        attachments.

    Returns the inserted File doc (caller can read file_url for chaining).
    """
    payload = {
        "doctype": "File",
        "file_name": file_name,
        "attached_to_doctype": doctype,
        "attached_to_name": docname,
        "is_private": 1,
    }
    if file_url:
        payload["file_url"] = file_url
    else:
        payload["content"] = pdf_bytes
    file_doc = frappe.get_doc(payload)
    file_doc.insert(ignore_permissions=True)
    return file_doc


def _default_email_body(file_label: str) -> str:
    """Plain-language email body shown to the recipient."""
    return f"""
    <p>Hello,</p>
    <p>Please find your <strong>{file_label}</strong> attached.</p>
    <p>For any queries, contact us at <strong>hr@globexdigital.ai</strong>
    or call <strong>040-3551 1959</strong>.</p>
    <p>Regards,<br>Globex Digital Solutions Pvt Ltd</p>
    """
