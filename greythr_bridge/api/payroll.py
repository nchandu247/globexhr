from .client import GreytHRClient


def get_salary_repository() -> dict:
    """
    GET /payroll/v2/salary/repository

    Returns a tree of salary components with 3 top-level nodes.
    Response shape: {"data": [{id, name, type, parent, children, taxable, description}, ...]}
    The mapper must do a recursive tree-walk to flatten before creating Frappe records.
    """
    return GreytHRClient().get("/payroll/v2/salary/repository")


def get_employee_salary(employee_id: str) -> dict:
    """
    GET /payroll/v2/salary/employees/{id}

    Returns the current salary breakdown for one employee.
    NOTE: Endpoint availability on Essential plan not yet confirmed — verify before Phase 6.
    """
    return GreytHRClient().get(f"/payroll/v2/salary/employees/{employee_id}")


def list_employee_salaries(page: int = 1, size: int = 50) -> dict:
    """
    GET /payroll/v2/salary/employees

    Returns salary data for all employees (paginated).
    NOTE: Endpoint availability on Essential plan not yet confirmed — verify before Phase 6.
    """
    return GreytHRClient().get(
        "/payroll/v2/salary/employees", params={"page": page, "size": size}
    )
