from .client import GreytHRClient


def list_employees(page: int = 1, size: int = 50, updated_after: str = None) -> dict:
    """
    GET /employee/v2/employees

    Returns {"data": [...]} with employeeId, name, firstName, middleName, lastName,
    email (work), employeeNo, dateOfJoin, leavingDate.

    updated_after: ISO datetime string or None. Verify support in greytHR API docs
    before relying on this filter — see NOTES_greythr_api.md open questions.
    """
    params = {"page": page, "size": size}
    if updated_after:
        params["updatedAfter"] = updated_after
    return GreytHRClient().get("/employee/v2/employees", params=params)


def get_employee(employee_id: str) -> dict:
    """GET /employee/v2/employees/{id} — single employee detail."""
    return GreytHRClient().get(f"/employee/v2/employees/{employee_id}")


def list_employee_work_details(page: int = 1, size: int = 50) -> dict:
    """
    GET /employee/v2/employees/work

    Returns confirmDate, originalHireDate, noticePeriod, extendedProbationDays,
    probationExtendedBy, lastPromotionDate, lastPrevEmployment, onboardingStatus.
    onboardingStatus is intentionally NOT mapped to Frappe — Frappe HR owns onboarding.
    """
    return GreytHRClient().get("/employee/v2/employees/work", params={"page": page, "size": size})


def list_employee_separations(page: int = 1, size: int = 50) -> dict:
    """
    GET /employee/v2/employees/separation

    Returns leavingDate, leavingReason, submittedResignation, submissionDate,
    exitInterviewDate, finalSettlementDate, fitToBeRehired, tentativeLeavingDate,
    tentativeRelieveDate, leftOrg, retirementDate.
    Feeds Phase 6 letter generation (Experience, Relieving letters).
    """
    return GreytHRClient().get("/employee/v2/employees/separation", params={"page": page, "size": size})
