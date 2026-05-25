"""
Convert greytHR employee records to Frappe Employee field values.

Field decisions:
  - email → company_email (confirmed work email from greytHR)
  - leavingDate non-null OR leftorg=true → status "Left"
  - fitToBeRehired → custom_fit_to_rehire (HR decision: capture this field)
  - onboardingStatus → intentionally ignored (Frappe HR owns onboarding)
  - designation → intentionally skipped here (Link to Designation doctype;
    needs target records to pre-exist — handled in a separate task)
  - Dates: try BOTH `dd-MM-yyyy` (legacy) AND ISO `yyyy-MM-dd` (what greytHR
    actually returns in 2026) — verified via diagnostic on 2026-05-23
"""
from datetime import datetime


# greytHR returns single-letter gender; Frappe HR's `gender` is a Link
# to the `Gender` doctype which uses full names.
_GENDER_MAP = {
    "M": "Male",
    "F": "Female",
    "O": "Other",
}


def greythr_to_frappe(greythr_employee: dict) -> dict:
    """
    Convert a greytHR employee record to Frappe Employee field values.

    Returns a dict of fields ready to set on a Frappe Employee document.
    Fields missing from greytHR are omitted — never overwrites Frappe fields
    with None. A '_mapping_errors' key lists fields that could not be mapped;
    caller decides whether to skip or proceed with the partial result.
    """
    errors = []
    result = {}

    # ── identity ──────────────────────────────────────────────────────────────
    # greytHR returns employeeId as INTEGER (e.g. 270). Frappe Data field
    # expects string. Stringify defensively so save() doesn't silently coerce.
    if emp_id := greythr_employee.get("employeeId"):
        result["custom_greythr_employee_id"] = str(emp_id)
    else:
        errors.append("employeeId missing — cannot create mapping")

    if emp_no := greythr_employee.get("employeeNo"):
        result["employee_number"] = emp_no

    # ── name — fallback chain for greytHR's combined name field ───────────────
    # Diagnostic on 2026-05-23 confirmed greytHR's /employees/{id} endpoint
    # returns firstName/lastName/middleName as NULL, with the full name in
    # the combined `name` field (e.g., "Gandla Sanjeev"). Default strategy:
    # put the full name into first_name and leave last_name empty. Indian
    # naming conventions vary; HR can manually split important records.
    # The original combined value is also preserved in custom_greythr_full_name
    # for audit/verification.
    if first := greythr_employee.get("firstName"):
        result["first_name"] = first
        if last := greythr_employee.get("lastName"):
            result["last_name"] = last
        if middle := greythr_employee.get("middleName"):
            result["middle_name"] = middle
    elif full_name := greythr_employee.get("name"):
        # Whole name into first_name. last_name stays empty.
        result["first_name"] = full_name.strip()
    else:
        errors.append("firstName and name both missing — record will have no name")

    if full_name := greythr_employee.get("name"):
        result["custom_greythr_full_name"] = full_name.strip()

    # ── contact ───────────────────────────────────────────────────────────────
    if email := greythr_employee.get("email"):
        result["company_email"] = email

    if personal := greythr_employee.get("personalEmail"):
        result["personal_email"] = personal

    if mobile := greythr_employee.get("mobile"):
        # Frappe Employee uses `cell_number` for mobile
        result["cell_number"] = str(mobile)

    # ── demographics ──────────────────────────────────────────────────────────
    if g := greythr_employee.get("gender"):
        if g in _GENDER_MAP:
            result["gender"] = _GENDER_MAP[g]
        else:
            errors.append(f"gender: unrecognised value {g!r}")

    if dob := greythr_employee.get("dateOfBirth"):
        parsed = _parse_date(dob, errors, field="dateOfBirth")
        if parsed:
            result["date_of_birth"] = parsed

    # ── dates ─────────────────────────────────────────────────────────────────
    if doj := greythr_employee.get("dateOfJoin"):
        parsed = _parse_date(doj, errors, field="dateOfJoin")
        if parsed:
            result["date_of_joining"] = parsed

    # ── status — inferred from leavingDate AND/OR leftorg ─────────────────────
    # greytHR exposes two signals: leavingDate (the date) and leftorg (boolean).
    # Status="Left" requires Frappe's relieving_date to be set, so we only mark
    # Left when we have a parseable leaving date. The leftorg flag is informational
    # — without a date we can't satisfy Frappe's relieving_date requirement.
    #
    # Whenever the mapper produces status="Active", it also explicitly emits
    # `relieving_date = None` so _sync_one's update loop CLEARS any stale
    # relieving_date on the existing Frappe record. Without the explicit
    # None, mapper-absence vs mapper-clear are indistinguishable to the
    # update logic — and a stale relieving_date from a previous "Left" period
    # would survive a reactivation, breaking Frappe HR's validate hook on
    # the next date_of_joining update. (Bug seen with rehire scenarios on
    # 2026-05-25 — emp 389/388/271 stuck on "Relieving Date must be after
    # Date of Joining".)
    leaving_date = greythr_employee.get("leavingDate")
    left_org_flag = greythr_employee.get("leftorg") or greythr_employee.get("leftOrg")
    if leaving_date:
        parsed_ld = _parse_date(leaving_date, errors, field="leavingDate")
        if parsed_ld:
            result["status"] = "Left"
            result["relieving_date"] = parsed_ld
        else:
            # Date unparseable — mark active to avoid Frappe's relieving_date validation.
            result["status"] = "Active"
            result["relieving_date"] = None
    elif left_org_flag:
        # leftorg=true but no leavingDate. Can't set status=Left without
        # relieving_date. HR may need to add the date manually.
        result["status"] = "Active"
        result["relieving_date"] = None
        errors.append("leftorg=true but no leavingDate — cannot set status=Left")
    else:
        result["status"] = "Active"
        result["relieving_date"] = None

    # ── separation details (when called with separation endpoint data) ─────────
    if reason := greythr_employee.get("leavingReason"):
        result["reason_for_leaving"] = reason

    # fitToBeRehired → custom field (HR decision: capture for rehire screening)
    if "fitToBeRehired" in greythr_employee:
        result["custom_fit_to_rehire"] = 1 if greythr_employee["fitToBeRehired"] else 0

    # ── Sanity check: a "Left" record needs BOTH a date_of_joining AND a
    # relieving_date >= date_of_joining. Frappe HR's Employee.validate hook
    # rejects any save that violates this, which previously caused the whole
    # record to fail on every sync. To keep the rest of the data syncable,
    # downgrade status to Active and drop the bad relieving_date.
    #
    # Two observed greytHR data-quality classes drive this check:
    #   1. Inverted dates — GDS0022 / employeeId 32: dateOfJoin "2017-11-12",
    #      leavingDate "2017-08-10" (left 3 months BEFORE joining).
    #   2. Missing dateOfJoin — employeeId 389: leavingDate set but dateOfJoin
    #      absent or unparseable, so the mapper produces relieving_date with
    #      no date_of_joining for Frappe to compare against. Frappe HR still
    #      rejects the save (Left requires both). Same family of bug.
    rd = result.get("relieving_date")
    doj = result.get("date_of_joining")
    if rd and (not doj or rd < doj):
        emp_id = greythr_employee.get("employeeId")
        if not doj:
            errors.append(
                f"relieving_date ({rd}) set but date_of_joining missing/"
                f"unparseable — keeping status Active; HR must populate "
                f"dateOfJoin in greytHR for employeeId={emp_id}"
            )
        else:
            errors.append(
                f"relieving_date ({rd}) is before date_of_joining ({doj}) — "
                f"keeping status Active; HR must fix the dates in greytHR "
                f"for employeeId={emp_id}"
            )
        # Explicit None (not pop) so _sync_one's update loop clears any stale
        # relieving_date on the existing Frappe record — see Bug #2 note above.
        result["relieving_date"] = None
        result["status"] = "Active"

    result["_mapping_errors"] = errors
    return result


def _parse_date(date_str: str, errors: list, field: str = "date") -> str | None:
    """
    Parse greytHR date string into Frappe format (YYYY-MM-DD).

    greytHR has been observed returning dates in two formats:
      - Legacy `dd-MM-yyyy` (e.g., "01-06-2023") — assumed by earlier code
      - ISO `yyyy-MM-dd` (e.g., "2024-01-02") — what /employees/{id} actually
        returns as of 2026-05-23 (confirmed via diagnostic)

    Try both formats. Records error only if neither parses.
    """
    if not date_str:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    errors.append(f"{field}: unrecognised date format {date_str!r}")
    return None
