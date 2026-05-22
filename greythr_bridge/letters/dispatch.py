"""
Letter-template dispatcher.

For DocTypes that may produce different letter variants (currently only
Job Offer, which can be Full-time / Consultant / Intern), this module
picks the correct HTML template + context builder based on a discriminator
field on the source document.

Adding a new variant in the future = add a branch here. Keeps the handler
(hooks_handlers/job_offer.py) free of conditional template-name logic.
"""
from .merger import (
    build_offer_context,
    build_consultant_offer_context,
    build_intern_offer_context,
)


def dispatch_offer_letter(doc) -> tuple[str, dict]:
    """
    For a Job Offer doc, return (template_filename, context_dict) based
    on `custom_offer_type`.

    Defaults to "Full-time" (standard offer letter) if the field is missing
    or has an unrecognised value.
    """
    offer_type = (getattr(doc, "custom_offer_type", None) or "Full-time").strip()

    if offer_type == "Consultant":
        return "consultant_offer_letter.html", build_consultant_offer_context(doc)
    if offer_type == "Intern":
        return "intern_offer_letter.html", build_intern_offer_context(doc)
    # Default — Full-time, including any unknown value (defensive)
    return "offer_letter.html", build_offer_context(doc)
