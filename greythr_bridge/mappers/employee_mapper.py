from datetime import datetime


def greythr_to_frappe(greythr_employee: dict) -> dict:
    """
    Convert a greytHR employee record to Frappe Employee field values.

    Returns a dict of fields ready to set on a Frappe Employee document.
    Fields missing from greytHR are omitted — never overwrites Frappe fields with None.
    A '_mapping_errors' key lists fields that could not be mapped; caller decides
    whether to skip or proceed with the partial result.

    Field decisions:
      - email → company_email (confirmed work email from greytHR)
      - leavingDate non-null → status "Left" (no separate separation endpoint call needed)
      - fitToBeRehired → custom_fit_to_rehire (HR decision: capture this field)
      - onboardingStatus → intentionally ignored (Frappe HR owns onboarding)
      - Dates: greytHR dd-MM-yyyy → Frappe YYYY-MM-DD (converted here, never in caller)
    """
    errors = []
    result = {}

    # ── identity ──────────────────────────────────────────────────────────────
    if emp_id := greythr_employee.get("employeeId"):
        result["custom_greythr_employee_id"] = emp_id
    else:
        errors.append("employeeId missing — cannot create mapping")

    if emp_no := greythr_employee.get("employeeNo"):
        result["employee_number"] = emp_no

    # ── name — use decomposed fields, never parse the full 'name' string ───────
    if first := greythr_employee.get("firstName"):
        result["first_name"] = first
    else:
        errors.append("firstName missing")

    if last := greythr_employee.get("lastName"):
        result["last_name"] = last

    if middle := greythr_employee.get("middleName"):
        result["middle_name"] = middle

    # ── contact ───────────────────────────────────────────────────────────────
    if email := greythr_employee.get("email"):
        result["company_email"] = email

    # ── dates ─────────────────────────────────────────────────────────────────
    if doj := greythr_employee.get("dateOfJoin"):
        parsed = _parse_date(doj, errors, field="dateOfJoin")
        if parsed:
            result["date_of_joining"] = parsed

    # ── status — inferred from leavingDate on the employee list ───────────────
    # leavingDate present on the main employee list — no separate separation call needed.
    # Only set status="Left" if we can also set relieving_date; Frappe requires both.
    leaving_date = greythr_employee.get("leavingDate")
    if leaving_date:
        parsed_ld = _parse_date(leaving_date, errors, field="leavingDate")
        if parsed_ld:
            result["status"] = "Left"
            result["relieving_date"] = parsed_ld
        else:
            # Date unparseable — mark active to avoid Frappe's relieving_date validation.
            # The mapping error is already recorded; HR can correct manually.
            result["status"] = "Active"
    else:
        result["status"] = "Active"

    # ── separation details (when called with separation endpoint data) ─────────
    if reason := greythr_employee.get("leavingReason"):
        result["reason_for_leaving"] = reason

    # fitToBeRehired → custom field (HR decision: capture for rehire screening)
    if "fitToBeRehired" in greythr_employee:
        result["custom_fit_to_rehire"] = 1 if greythr_employee["fitToBeRehired"] else 0

    result["_mapping_errors"] = errors
    return result


def _parse_date(date_str: str, errors: list, field: str = "date") -> str | None:
    """
    Convert greytHR date format (dd-MM-yyyy) to Frappe format (YYYY-MM-DD).
    Returns None and records an error if the string cannot be parsed.
    Conversion always happens in the mapper — never in tasks or the API client.
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        errors.append(f"{field}: unrecognised date format {date_str!r}")
        return None
