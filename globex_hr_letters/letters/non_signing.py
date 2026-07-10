"""
Helper for the 5 PDF-only letter types: Increment, Promotion, Experience,
Relieving, Service Certificate.

These letters skip Zoho Sign — HR's signature is embedded as an image in the
PDF. After generation:
  1. PDF attached as a private File against the source DocType record
  2. Email sent to the employee (with fallback chain for email address)
  3. Marker field optionally set on source doc

All callers MUST invoke generate_and_deliver() from inside frappe.enqueue()
so the synchronous handler / button-click returns within 5 seconds.
"""
import os
import frappe

from .merger import merge_to_pdf_via_html
from ..utils.logging import log_error


def generate_and_deliver(
    template_filename: str,
    context: dict,
    attach_to: tuple[str, str],
    file_label: str,
    employee_doc=None,
    email_subject: str = "",
    email_body_html: str = "",
    prefer_personal_email: bool = False,
    also_attach_to: tuple[str, str] | None = None,
    file_name_suffix: str | None = None,
) -> bytes:
    """
    Render PDF, attach to source doc, email to employee.

    Args:
        template_filename: e.g. "increment_letter.html"
        context:           dict of Jinja2 variables for the template
        attach_to:         (doctype, docname) — the PRIMARY source record
        file_label:        human-friendly name shown in attachment list,
                           e.g. "Increment Letter"
        employee_doc:      Frappe Employee doc — used to resolve email address.
                           Pass None to skip email entirely.
        email_subject:     Subject line if sending email
        email_body_html:   HTML body if sending email
        prefer_personal_email:
            True  → personal_email > company_email > skip (separation letters)
            False → company_email > personal_email > skip (active-employee letters)
        also_attach_to:    optional (doctype, docname) — a SECOND record to
                           also attach the same PDF to. e.g., for separation
                           letters: primary = Employee (so the letter lives on
                           the employee's permanent record), secondary =
                           Employee Separation (so HR's separation workflow
                           view also has it).
        file_name_suffix:  optional override for the filename suffix. If None,
                           uses `attach_to`'s docname. Pass the employee's
                           GDS#### identifier here when attach_to is the
                           Separation but you want the filename to read
                           "Relieving Letter - GDS0021.pdf" not
                           "Relieving Letter - HR-EMP-SEP-2026-00001.pdf".

    Returns: PDF bytes (also attached + emailed as side effects).
    """
    # 1. Render PDF
    pdf_bytes = merge_to_pdf_via_html(template_filename, context)
    if not pdf_bytes or len(pdf_bytes) < 5000:
        raise RuntimeError(
            f"non_signing: PDF for {template_filename} suspiciously small "
            f"({len(pdf_bytes) if pdf_bytes else 0} bytes)"
        )

    # 2. Build the file_name once — used for both attachments AND email.
    #    Prefer the explicit suffix when provided so HR sees the employee
    #    identifier (GDS####) in the filename regardless of which record the
    #    file is attached to.
    doctype, docname = attach_to
    safe_label = file_label.replace("/", "-")
    name_slug = file_name_suffix or docname
    file_name = f"{safe_label} - {name_slug}.pdf"

    # 3. Attach to the PRIMARY record (writes content to disk).
    primary_file = _create_file_attachment(file_name, pdf_bytes, doctype, docname)

    # 4. (Optional) attach to a SECOND record. To avoid the hash-suffix bug
    #    (where Frappe's storage layer appends "70526e" etc. when writing a
    #    duplicate filename), the secondary attachment LINKS to the primary
    #    file's URL instead of writing new content. Same clean filename
    #    on both attachments, single physical file on disk.
    if also_attach_to:
        also_dt, also_dn = also_attach_to
        try:
            _create_file_attachment(
                file_name, pdf_bytes, also_dt, also_dn,
                file_url=getattr(primary_file, "file_url", None),
            )
        except Exception as exc:
            # Secondary attachment is best-effort — don't fail the whole
            # letter generation if it errors. Primary attachment + email
            # still succeed.
            log_error(
                f"non_signing: secondary attach to {also_dt}/{also_dn} "
                f"failed: {str(exc)[:200]}",
                "greytHR Letter Secondary Attach Error",
            )

    # 5. Resolve email and send (if employee_doc + addresses available)
    if employee_doc is not None:
        recipient = _resolve_email(employee_doc, prefer_personal_email)
        if recipient:
            try:
                frappe.sendmail(
                    recipients=[recipient],
                    subject=email_subject or f"{file_label} — Globex Digital Solutions",
                    message=email_body_html or _default_email_body(file_label),
                    attachments=[{
                        "fname": file_name,
                        "fcontent": pdf_bytes,
                    }],
                    now=True,
                    reference_doctype=doctype,
                    reference_name=docname,
                )
            except Exception as exc:
                log_error(
                    f"non_signing: sendmail failed for {docname} → {recipient}: "
                    f"{str(exc)[:200]}",
                    "greytHR Letter Email Error",
                )
        else:
            log_error(
                f"non_signing: no email address found for {employee_doc.name}; "
                f"PDF attached to {docname} but not emailed.",
                "greytHR Letter Email Skipped",
            )

    return pdf_bytes


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
        attachments to avoid Frappe appending hash suffixes when writing
        a duplicate filename.

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
        # Link mode — no duplicate write, no hash suffix
        payload["file_url"] = file_url
    else:
        # Write mode — Frappe writes content to disk
        payload["content"] = pdf_bytes
    file_doc = frappe.get_doc(payload)
    file_doc.insert(ignore_permissions=True)
    return file_doc


def _resolve_email(employee_doc, prefer_personal: bool) -> str | None:
    """
    Email-address fallback chain.

    For onboarding / active-employee letters (prefer_personal=False):
        company_email → personal_email → None
    For separation letters (prefer_personal=True), where company_email may
    already be deactivated:
        personal_email → company_email → None
    """
    company = getattr(employee_doc, "company_email", None) or None
    personal = getattr(employee_doc, "personal_email", None) or None
    if prefer_personal:
        return personal or company
    return company or personal


def _default_email_body(file_label: str) -> str:
    """Plain-language email body shown to the employee."""
    return f"""
    <p>Hello,</p>
    <p>Please find your <strong>{file_label}</strong> attached.</p>
    <p>For any queries, contact us at <strong>hr@globexdigital.ai</strong>
    or call <strong>040-3551 1959</strong>.</p>
    <p>Regards,<br>Globex Digital Solutions Pvt Ltd</p>
    """
