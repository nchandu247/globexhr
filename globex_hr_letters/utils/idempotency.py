def make_key(doctype: str, docname: str, operation: str) -> str:
    """
    Generate an idempotency key from a Frappe document name.

    The Frappe document name is the canonical idempotency key — it's unique
    per record and stable across retries.

    Example:
        make_key("Job Offer", "JOB-OFFER-00042", "push_signed_pdf")
        → "Job Offer:JOB-OFFER-00042:push_signed_pdf"
    """
    return f"{doctype}:{docname}:{operation}"
