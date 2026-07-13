"""
Generic letter generation engine.

Flow (driven from the HR Letter form):

  HR Letter (Draft) → [Generate]
    1. Load the Letter Type's template (HTML file or attached .docx)
    2. Scan placeholders
    3. Resolve in order:
         recipient doc fields (Employee or Job Applicant)
         → HR Letters Settings / letterhead fields
         → compensation child table (when the type uses one)
         → HR-supplied filled_values (from the generate dialog)
    4. Any placeholder still unresolved is a HARD ERROR — a letter is never
       rendered with silent blanks.
    5. Render → attach PDF → status = Generated
    6a. requires_signature → dispatch via api/zoho_sign.py (enqueued)
        → status = Sent for Signature → webhook callback → Signed
    6b. else → [Issue] → email to recipient (enqueued) → status = Issued

DPDP note: log document names and operation names only — never placeholder
values, recipient emails, or rendered content.
"""
import json
import os
import re

import frappe

from .merger import (
    fmt_date,
    fmt_inr,
    format_person_name,
    merge_docx_file,
    merge_to_pdf_via_html,
    docx_bytes_to_pdf,
    scan_docx_placeholders,
    scan_html_placeholders,
    tenure_str,
    today_str,
)
from ..hooks_handlers.employee import GREYTHR_ID_RE
from ..utils.logging import log_error

# Placeholders every render receives without HR needing to supply them.
# Kept in sync with build_context() below.
_ALWAYS_PROVIDED = {
    "ref_number", "current_date", "letter_date", "requires_signature",
    "recipient_name", "compensation",
    "gross_monthly", "gross_annual", "annual_ctc", "monthly_ctc",
    "signatory_name", "signatory_designation", "signature_image",
}


# ── placeholder resolution ────────────────────────────────────────────────────

def get_template_placeholders(letter_type_doc) -> set:
    """All Jinja2 variables the Letter Type's template expects."""
    if letter_type_doc.render_engine == "HTML":
        return scan_html_placeholders(letter_type_doc.html_template)
    return scan_docx_placeholders(_docx_template_path(letter_type_doc))


def get_missing_placeholders(hr_letter) -> list:
    """
    Placeholders the template needs that neither the recipient doc, the
    Settings, the compensation table, nor previously filled values can
    supply. These are prompted to HR in the generate dialog.
    """
    letter_type = frappe.get_doc("Letter Type", hr_letter.letter_type)
    wanted = get_template_placeholders(letter_type)
    context = build_context(hr_letter, letter_type)
    return sorted(wanted - set(context.keys()))


def build_context(hr_letter, letter_type_doc=None) -> dict:
    """
    Build the Jinja2 context for an HR Letter. Resolution order (later
    layers never overwrite earlier ones is NOT the rule here — later,
    more-specific layers win):

      1. company_* + default signatory from HR Letters Settings
      2. recipient doc fields (formatted by fieldtype)
      3. computed conveniences (tenure, last_working_day, ...)
      4. Job Offer terms (candidate letters — decision A1, 2026-07-13)
      5. compensation table + totals
      6. HR-supplied filled_values (highest precedence)
    """
    letter_type = letter_type_doc or frappe.get_doc("Letter Type", hr_letter.letter_type)
    settings = frappe.get_single("HR Letters Settings")

    context = {}
    context.update(_company_context(settings))
    context.update(_signatory_context(letter_type, settings))

    recipient_doc = frappe.get_doc(hr_letter.recipient_type, hr_letter.recipient)
    context.update(_recipient_context(hr_letter.recipient_type, recipient_doc))

    # Offered terms beat raw applicant fields (e.g. offered designation vs
    # the Job Opening's), but compensation and filled_values still win.
    context.update(_job_offer_context(hr_letter.recipient_type, hr_letter.recipient))

    if letter_type.uses_compensation_table:
        context.update(_compensation_context(hr_letter))

    context.update({
        "ref_number": hr_letter.name,
        "current_date": today_str(),
        "letter_date": fmt_date(hr_letter.letter_date),
        "requires_signature": bool(letter_type.requires_signature),
    })

    # HR-supplied values win over everything (e.g. HR corrects a designation
    # spelling for one letter without touching the Employee record).
    for key, value in _parse_filled_values(hr_letter).items():
        context[key] = value

    return context


def _parse_filled_values(hr_letter) -> dict:
    raw = hr_letter.filled_values
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


def _company_context(settings) -> dict:
    return {
        "company_name": settings.company_name or "",
        "company_address": settings.company_address or "",
        "company_phone": settings.company_phone or "",
        "company_email": settings.company_email or "",
        "company_website": settings.company_website or "",
    }


def _signatory_context(letter_type, settings) -> dict:
    if letter_type.signatory_source == "Custom" and letter_type.signatory_name:
        return {
            "signatory_name": letter_type.signatory_name or "",
            "signatory_designation": letter_type.signatory_designation or "",
            "signature_image": _signature_image_data_uri(letter_type.signature_image),
        }
    return {
        "signatory_name": settings.signatory_name or "Authorised Signatory",
        "signatory_designation": settings.signatory_designation or "",
        "signature_image": _signature_image_data_uri(settings.signature_image),
    }


_IMAGE_MIME_BY_EXT = {
    "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "gif": "image/gif", "svg": "image/svg+xml",
}


def _signature_image_data_uri(file_url) -> str:
    """
    Resolve an Attach Image file_url (usually /private/files/...) to a
    data: URI. The signature is stamped on every letter at generation
    (approved internally before creation — decision 2026-07-13), and
    WeasyPrint can't fetch private URLs: its base_url points at the
    template dir, not the site.
    """
    if not file_url or not isinstance(file_url, str):
        return ""
    if file_url.startswith("data:"):
        return file_url
    try:
        import base64
        content = frappe.get_doc("File", {"file_url": file_url}).get_content()
        if isinstance(content, str):
            content = content.encode()
        ext = os.path.splitext(file_url)[1].lower().lstrip(".")
        mime = _IMAGE_MIME_BY_EXT.get(ext, "image/png")
        return f"data:{mime};base64,{base64.b64encode(content).decode()}"
    except Exception as exc:
        # Letter still renders (templates guard with {% if signature_image %});
        # log so HR learns why the stamp is missing.
        log_error(
            f"Signature image could not be embedded: {str(exc)[:120]}",
            "HR Letters Render",
        )
        return ""


def _recipient_context(recipient_type: str, doc) -> dict:
    """
    Expose the recipient document's fields as bare placeholder names,
    formatted by fieldtype (Date → '01 June 2026', Currency → Indian
    commas). Skips empty values so filled_values / prompts can supply them.
    """
    context = {}
    for df in doc.meta.fields:
        value = doc.get(df.fieldname)
        if value in (None, ""):
            continue
        if df.fieldtype == "Date":
            context[df.fieldname] = fmt_date(value)
        elif df.fieldtype in ("Currency", "Float", "Int") and df.fieldname != "employee_number":
            context[df.fieldname] = fmt_inr(value)
        elif df.fieldtype in ("Data", "Small Text", "Text", "Select", "Link"):
            context[df.fieldname] = str(value)
        # Other fieldtypes (Table, Attach, ...) are not letter content.

    # Curated conveniences on top of raw fields
    if recipient_type == "Employee":
        display_name = format_person_name(doc.get("employee_name") or doc.get("first_name"))
        # Letters print the greytHR Employee ID (employee_number), not the
        # internal Frappe name — decision B3, 2026-07-13. generate() guards
        # that the ID exists for Employee letters, so the doc.name fallback
        # only covers non-letter callers.
        greythr_id = doc.get("employee_number") or ""
        context["employee_id"] = greythr_id or doc.name
        context["greythr_employee_id"] = greythr_id
        context["employee_name"] = display_name
        context["recipient_name"] = display_name
        context["designation"] = format_person_name(doc.get("designation") or "")
        doj = doc.get("date_of_joining")
        lwd = doc.get("relieving_date")
        context["date_of_joining"] = fmt_date(doj)
        if lwd:
            context["last_working_day"] = fmt_date(lwd)
            context["tenure"] = tenure_str(doj, lwd)
        else:
            context["tenure"] = tenure_str(doj, None)  # None = up to today
    else:  # Job Applicant
        display_name = format_person_name(doc.get("applicant_name"))
        context["applicant_name"] = display_name
        context["candidate_name"] = display_name
        context["recipient_name"] = display_name
        context["candidate_email"] = doc.get("email_id") or ""

    return context


def _scrub_placeholder(label: str) -> str:
    """'Date of Joining' → 'date_of_joining' (local, offline-safe scrub)."""
    return re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")


def _format_term_value(term_label: str, value) -> str:
    """
    Job Offer Term values are free-typed Data strings. Keep letters
    consistently formatted: ISO dates render as '01 August 2026', and pure
    numbers on amount-ish terms get Indian commas. Anything else passes
    through as typed.
    """
    text = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return fmt_date(text)
    if re.match(r"^\d+(\.\d+)?$", text) and re.search(
        r"ctc|salary|amount|stipend|fee|pay", term_label, re.IGNORECASE
    ):
        return fmt_inr(text)
    return text


def _job_offer_context(recipient_type: str, recipient_name: str) -> dict:
    """
    Offer terms typed once on the candidate's Job Offer (decision A1,
    2026-07-13) resolve as placeholders for every candidate letter, so HR
    doesn't re-type the same facts into the Offer Letter and again into
    the Appointment Letter.

    Uses the latest non-rejected Job Offer linked to the Job Applicant:
      - doc fields: designation (offered role), offer_date, company
      - Job Offer Term rows: label scrubbed to a placeholder name
        ('Date of Joining' → date_of_joining), value formatted by
        _format_term_value.
    """
    if recipient_type != "Job Applicant":
        return {}
    offers = frappe.get_all(
        "Job Offer",
        filters={
            "job_applicant": recipient_name,
            "status": ["!=", "Rejected"],
            "docstatus": ["<", 2],
        },
        fields=["name"],
        order_by="modified desc",
        limit=1,
    )
    if not offers:
        return {}

    offer = frappe.get_doc("Job Offer", offers[0]["name"])
    context = {}
    if offer.get("designation"):
        context["designation"] = str(offer.get("designation"))
    if offer.get("offer_date"):
        context["offer_date"] = fmt_date(offer.get("offer_date"))
    if offer.get("company"):
        context["company"] = str(offer.get("company"))

    for row in (offer.get("offer_terms") or []):
        label = (getattr(row, "offer_term", None) or "").strip()
        value = getattr(row, "value", None)
        if not label or value in (None, ""):
            continue
        context[_scrub_placeholder(label)] = _format_term_value(label, value)

    return context


def _compensation_context(hr_letter) -> dict:
    """
    Compensation annexure data. Each row's annual auto-computes as 12×
    monthly when left blank. Totals:

      gross_monthly / gross_annual — sum of all rows
      annual_ctc / monthly_ctc     — aliases of the gross totals (letters
                                      typically headline these)

    Rows are exposed as `compensation`: a list of dicts with pre-formatted
    Indian-comma amounts, rendered in templates via
    {% for row in compensation %}.
    """
    rows = []
    gross_monthly = 0.0
    gross_annual = 0.0
    for row in (hr_letter.compensation or []):
        monthly = float(row.monthly_amount or 0)
        annual = float(row.annual_amount or 0) or monthly * 12
        gross_monthly += monthly
        gross_annual += annual
        rows.append({
            "component": row.component,
            "monthly": fmt_inr(monthly),
            "annual": fmt_inr(annual),
        })

    return {
        "compensation": rows,
        "gross_monthly": fmt_inr(gross_monthly),
        "gross_annual": fmt_inr(gross_annual),
        "annual_ctc": fmt_inr(gross_annual),
        "monthly_ctc": fmt_inr(round(gross_annual / 12) if gross_annual else 0),
    }


# ── generation ────────────────────────────────────────────────────────────────

def _require_greythr_id(employee_docname: str) -> None:
    """
    Employee letters must not go out without the greytHR Employee ID
    (decision B5, 2026-07-13): the ID is recorded manually after joining,
    and letters print it — generating earlier would emit the internal
    Frappe name instead.
    """
    employee = frappe.get_doc("Employee", employee_docname)
    emp_no = (employee.get("employee_number") or "").strip()
    if not GREYTHR_ID_RE.match(emp_no):
        frappe.throw(
            f"Employee {employee_docname} has no valid greytHR Employee ID. "
            "Record the Employee Number (GDS + 3-6 digits, generated in "
            "greytHR) on the Employee record before generating employee "
            "letters.",
            title="greytHR Employee ID Required",
        )


def generate(hr_letter) -> None:
    """
    Render the letter and attach the PDF. Runs synchronously (WeasyPrint
    renders in ~1-2s) so HR sees the result immediately; signature dispatch
    and email delivery are separate, enqueued steps.

    Raises frappe.ValidationError when placeholders are unresolved — the
    letter is never rendered with silent blanks.
    """
    letter_type = frappe.get_doc("Letter Type", hr_letter.letter_type)
    settings = frappe.get_single("HR Letters Settings")
    if not settings.enabled:
        frappe.throw("HR Letters is disabled in HR Letters Settings.")
    if not letter_type.is_active:
        frappe.throw(f"Letter Type '{letter_type.name}' is inactive.")
    if hr_letter.recipient_type == "Employee":
        _require_greythr_id(hr_letter.recipient)

    context = build_context(hr_letter, letter_type)
    missing = sorted(get_template_placeholders(letter_type) - set(context.keys()))
    if missing:
        frappe.throw(
            "Cannot generate — these template placeholders have no value: "
            + ", ".join(missing)
            + ". Fill them in the generate dialog.",
            title="Unresolved Placeholders",
        )

    if letter_type.render_engine == "HTML":
        pdf_bytes = merge_to_pdf_via_html(letter_type.html_template, context)
    else:
        docx_bytes = merge_docx_file(
            _docx_template_path(letter_type), context,
            append_signature_tags=bool(letter_type.requires_signature),
        )
        if letter_type.requires_signature:
            # Signature DOCX letters upload the DOCX to Zoho (which converts
            # to PDF server-side) — stash the DOCX for dispatch and keep a
            # local PDF only if LibreOffice is available.
            hr_letter.flags.rendered_docx = docx_bytes
            pdf_bytes = _try_docx_pdf(docx_bytes, letter_type.name)
        else:
            pdf_bytes = docx_bytes_to_pdf(docx_bytes)

    from .delivery import attach_pdf

    file_name = _letter_file_name(hr_letter, letter_type)
    if pdf_bytes:
        file_doc = attach_pdf(
            file_name, pdf_bytes, "HR Letter", hr_letter.name,
            also_attach_to=_secondary_attach_target(hr_letter),
        )
        hr_letter.db_set("generated_pdf", file_doc.file_url)
    hr_letter.db_set("status", "Generated")
    frappe.msgprint(f"Letter generated: {file_name}")


def _try_docx_pdf(docx_bytes: bytes, letter_type_name: str) -> bytes | None:
    """Best-effort local PDF preview for signature DOCX letters. The signed
    authoritative PDF comes back from Zoho, so a missing LibreOffice is not
    an error here."""
    try:
        return docx_bytes_to_pdf(docx_bytes)
    except Exception:
        log_error(
            f"engine: local PDF preview unavailable for {letter_type_name} "
            "(LibreOffice missing?) — proceeding, Zoho will convert.",
            "HR Letters PDF Preview Skipped",
        )
        return None


def dispatch_signature(hr_letter_name: str) -> None:
    """
    Background job: send the generated letter to Zoho Sign.

    Single signer: the recipient (R1). The company signature is stamped
    on the PDF at generation — the letter is approved internally before
    it is created, so the signatory does not e-sign in Zoho
    (decision 2026-07-13).
    Idempotent: skips when zoho_request_id is already set.
    """
    hr_letter = frappe.get_doc("HR Letter", hr_letter_name)
    if hr_letter.zoho_request_id:
        return  # already dispatched

    letter_type = frappe.get_doc("Letter Type", hr_letter.letter_type)
    settings = frappe.get_single("HR Letters Settings")

    recipient_doc = frappe.get_doc(hr_letter.recipient_type, hr_letter.recipient)
    from .delivery import resolve_recipient_email
    recipient_email = resolve_recipient_email(
        hr_letter.recipient_type, recipient_doc,
        prefer_personal=(letter_type.category == "Exit"),
    )
    if not recipient_email:
        frappe.throw(
            f"No email address found for {hr_letter.recipient_type} "
            f"{hr_letter.recipient}. Set one and retry."
        )
    context = build_context(hr_letter, letter_type)
    if letter_type.render_engine == "HTML":
        file_bytes = merge_to_pdf_via_html(letter_type.html_template, context)
        file_extension = "pdf"
    else:
        file_bytes = merge_docx_file(
            _docx_template_path(letter_type), context, append_signature_tags=True,
        )
        file_extension = "docx"

    from ..api.zoho_sign import send_for_signature

    request_id = send_for_signature(
        file_bytes=file_bytes,
        document_name=f"{letter_type.name} - {context.get('recipient_name', hr_letter.recipient)}",
        signers=[
            {"name": context.get("recipient_name", ""),
             "email": recipient_email, "order": 1},
        ],
        metadata={"doctype": "HR Letter", "docname": hr_letter.name,
                  "letter_type": hr_letter.letter_type},
        file_extension=file_extension,
    )

    hr_letter.db_set("zoho_request_id", request_id)
    hr_letter.db_set("status", "Sent for Signature")


def deliver_issued_letter(hr_letter_name: str) -> None:
    """
    Background job: email the generated PDF to the recipient after Issue.
    """
    hr_letter = frappe.get_doc("HR Letter", hr_letter_name)
    letter_type = frappe.get_doc("Letter Type", hr_letter.letter_type)

    if not hr_letter.generated_pdf:
        log_error(
            f"deliver_issued_letter: {hr_letter_name} has no generated PDF",
            "HR Letters Delivery Error",
        )
        return

    file_doc = frappe.get_doc("File", {"file_url": hr_letter.generated_pdf})
    pdf_bytes = file_doc.get_content()
    if isinstance(pdf_bytes, str):
        pdf_bytes = pdf_bytes.encode()

    recipient_doc = frappe.get_doc(hr_letter.recipient_type, hr_letter.recipient)
    from .delivery import email_letter, resolve_recipient_email
    recipient_email = resolve_recipient_email(
        hr_letter.recipient_type, recipient_doc,
        prefer_personal=(letter_type.category == "Exit"),
    )
    email_letter(
        recipient_email,
        _letter_file_name(hr_letter, letter_type),
        pdf_bytes,
        letter_type.name,
        reference=("HR Letter", hr_letter.name),
        email_subject=f"Your {letter_type.name} — Globex Digital Solutions",
    )


# ── helpers ───────────────────────────────────────────────────────────────────

def _docx_template_path(letter_type_doc) -> str:
    """Absolute filesystem path of the Letter Type's attached DOCX template."""
    if not letter_type_doc.template:
        frappe.throw(
            f"Letter Type '{letter_type_doc.name}' has no DOCX template attached."
        )
    file_doc = frappe.get_doc("File", {"file_url": letter_type_doc.template})
    path = file_doc.get_full_path()
    if not os.path.exists(path):
        frappe.throw(f"DOCX template file missing on disk for '{letter_type_doc.name}'.")
    return path


def _letter_file_name(hr_letter, letter_type) -> str:
    """'Offer Letter - GDS0021.pdf' — human-facing identifier, not the
    internal HR-LTR series."""
    safe_label = letter_type.name.replace("/", "-")
    return f"{safe_label} - {hr_letter.recipient}.pdf"


def _secondary_attach_target(hr_letter) -> tuple | None:
    """Employee letters also attach to the Employee record so the letter
    lives on the person's permanent file. Candidate letters have no second
    home."""
    if hr_letter.recipient_type == "Employee":
        return ("Employee", hr_letter.recipient)
    return None
