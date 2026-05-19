"""
Tests for employee_mapper.py — pure unit tests, no HTTP or frappe calls.
"""
from greythr_bridge.mappers.employee_mapper import greythr_to_frappe, _parse_date


# ── _parse_date ────────────────────────────────────────────────────────────────

def test_parse_date_valid():
    errors = []
    assert _parse_date("15-03-2024", errors) == "2024-03-15"
    assert errors == []


def test_parse_date_invalid_format():
    errors = []
    result = _parse_date("2024-03-15", errors)
    assert result is None
    assert len(errors) == 1


def test_parse_date_empty():
    errors = []
    assert _parse_date("", errors) is None
    assert _parse_date(None, errors) is None
    assert errors == []


# ── greythr_to_frappe ──────────────────────────────────────────────────────────

def _sample():
    return {
        "employeeId": "EMP001",
        "employeeNo": "G001",
        "firstName": "Priya",
        "middleName": "",
        "lastName": "Sharma",
        "email": "priya@globexdigital.ai",
        "dateOfJoin": "01-04-2023",
        "leavingDate": None,
    }


def test_active_employee_maps_correctly():
    result = greythr_to_frappe(_sample())
    assert result["custom_greythr_employee_id"] == "EMP001"
    assert result["employee_number"] == "G001"
    assert result["first_name"] == "Priya"
    assert result["last_name"] == "Sharma"
    assert result["company_email"] == "priya@globexdigital.ai"
    assert result["date_of_joining"] == "2023-04-01"
    assert result["status"] == "Active"
    assert "_mapping_errors" in result
    assert result["_mapping_errors"] == []


def test_separated_employee_sets_left_status():
    emp = {**_sample(), "leavingDate": "31-03-2024"}
    result = greythr_to_frappe(emp)
    assert result["status"] == "Left"
    assert result["relieving_date"] == "2024-03-31"


def test_missing_employee_id_records_error():
    emp = {**_sample(), "employeeId": None}
    result = greythr_to_frappe(emp)
    assert any("employeeId" in e for e in result["_mapping_errors"])


def test_missing_first_name_records_error():
    emp = {**_sample(), "firstName": None}
    result = greythr_to_frappe(emp)
    assert any("firstName" in e for e in result["_mapping_errors"])


def test_invalid_date_records_error():
    emp = {**_sample(), "dateOfJoin": "2023-04-01"}  # wrong format
    result = greythr_to_frappe(emp)
    assert "date_of_joining" not in result
    assert len(result["_mapping_errors"]) > 0


def test_fit_to_rehire_true():
    emp = {**_sample(), "fitToBeRehired": True}
    result = greythr_to_frappe(emp)
    assert result["custom_fit_to_rehire"] == 1


def test_fit_to_rehire_false():
    emp = {**_sample(), "fitToBeRehired": False}
    result = greythr_to_frappe(emp)
    assert result["custom_fit_to_rehire"] == 0


def test_fit_to_rehire_absent():
    result = greythr_to_frappe(_sample())
    assert "custom_fit_to_rehire" not in result


def test_middle_name_omitted_when_empty():
    result = greythr_to_frappe(_sample())
    assert "middle_name" not in result


def test_middle_name_included_when_present():
    emp = {**_sample(), "middleName": "Kumar"}
    result = greythr_to_frappe(emp)
    assert result["middle_name"] == "Kumar"


def test_leaving_reason_mapped():
    emp = {**_sample(), "leavingDate": "31-03-2024", "leavingReason": "Resignation"}
    result = greythr_to_frappe(emp)
    assert result["reason_for_leaving"] == "Resignation"
