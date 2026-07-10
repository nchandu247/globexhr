import frappe


def log_error(message: str, title: str) -> None:
    """
    Log to Frappe Error Log.

    Message must contain only: document names, employee IDs, operation names,
    HTTP status codes, timestamps. Never pass names, emails, mobile numbers,
    Aadhaar, PAN, or any other PII — DPDP Act compliance requirement.
    """
    frappe.log_error(message=message, title=title)


def log_info(message: str) -> None:
    """Log an informational message. Same PII rules apply."""
    frappe.logger().info(message)


@frappe.whitelist()
def get_recent_errors(limit: int = 10, filter_title: str = "greytHR") -> list:
    """
    Browser-accessible endpoint to fetch the last N error log entries.

    System Manager only. Use when the Frappe Error Log UI isn't accessible.

    Call from a logged-in browser:
        https://<site>/api/method/globex_hr_letters.utils.logging.get_recent_errors
        https://<site>/api/method/globex_hr_letters.utils.logging.get_recent_errors?limit=20
        https://<site>/api/method/globex_hr_letters.utils.logging.get_recent_errors?filter_title=Zoho
    """
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Only System Manager can read the error log.")

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10
    limit = max(1, min(limit, 100))  # clamp 1..100

    filters = {}
    if filter_title:
        filters["title"] = ["like", f"%{filter_title}%"]

    rows = frappe.get_all(
        "Error Log",
        filters=filters,
        fields=["name", "creation", "title", "error"],
        order_by="creation desc",
        limit=limit,
    )

    # Truncate the error field so the response stays readable in a browser
    for r in rows:
        if r.get("error"):
            r["error"] = r["error"][:2000]
        if r.get("creation"):
            r["creation"] = str(r["creation"])

    return rows
