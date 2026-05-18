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
