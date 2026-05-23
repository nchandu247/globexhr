"""
Tests for employee_mapper.py — pure unit tests, no HTTP or frappe calls.
"""
from greythr_bridge.mappers.employee_mapper import greythr_to_frappe, _parse_date


# ── _parse_date ────────────────────────────────────────────────────────────────

def test_parse_date_valid():
    errors = []
    assert _parse_date("15-03-2024", errors) == "2024-03-15"
    assert errors == []


def test_parse_date_iso_format_also_accepted():
    """As of 2026-05-23 greytHR returns ISO yyyy-MM-dd on /employees/{id}.
    Mapper must accept both legacy dd-MM-yyyy AND ISO formats."""
    errors = []
    assert _parse_date("2024-01-02", errors) == "2024-01-02"
    assert errors == []


def test_parse_date_neither_format_records_error():
    errors = []
    result = _parse_date("01/02/2024", errors)  # slashes — neither format
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


def test_iso_date_format_now_accepted():
    """v4 change: greytHR's actual response uses ISO yyyy-MM-dd. Mapper
    must parse it correctly, not fall back to error."""
    emp = {**_sample(), "dateOfJoin": "2024-01-02"}
    result = greythr_to_frappe(emp)
    assert result["date_of_joining"] == "2024-01-02"
    # ISO date should not be in errors
    assert not any("dateOfJoin" in e for e in result["_mapping_errors"])


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


# ── v4 fixes for the real greytHR /employees/{id} response shape ───────────────
# These verify behaviours added 2026-05-23 after diagnostic confirmed the actual
# greytHR API returns shapes different from the test fixtures' earlier assumptions.

def _real_greythr_response():
    """Mirrors an actual greytHR /employees/{id} response (captured 2026-05-23
    via inspect_sync_for_employee for HR-EMP-00869 / GDS0234)."""
    return {
        "employeeId": 270,                    # INT, not string
        "name": "Gandla Sanjeev",             # full combined name
        "firstName": None, "middleName": None, "lastName": None,  # decomposed null
        "email": "sanjeevgandla22@gmail.com",
        "employeeNo": "GDS0234",
        "dateOfJoin": "2024-01-02",           # ISO yyyy-MM-dd
        "leavingDate": "2024-09-02",
        "leftorg": True,
        "dateOfBirth": "1994-03-15",
        "gender": "M",
        "personalEmail": None,
        "mobile": "9154064022",
        "designation": "System Admin",
    }


def test_integer_employee_id_stringified():
    """greytHR returns employeeId as INTEGER (270, not '270'). Frappe field is
    Data type — must store as string for consistency with the mapping table."""
    result = greythr_to_frappe(_real_greythr_response())
    assert result["custom_greythr_employee_id"] == "270"
    assert isinstance(result["custom_greythr_employee_id"], str)


def test_combined_name_falls_into_first_name():
    """When firstName/lastName are null, full `name` goes into first_name only.
    Avoids guessing wrong with Indian name conventions."""
    result = greythr_to_frappe(_real_greythr_response())
    assert result["first_name"] == "Gandla Sanjeev"
    assert "last_name" not in result
    # Original preserved for audit
    assert result["custom_greythr_full_name"] == "Gandla Sanjeev"


def test_decomposed_name_takes_priority_over_combined():
    """If greytHR ever DOES populate firstName/lastName, mapper uses them."""
    payload = {**_real_greythr_response(),
               "firstName": "Sanjeev", "lastName": "Gandla", "middleName": "K"}
    result = greythr_to_frappe(payload)
    assert result["first_name"] == "Sanjeev"
    assert result["last_name"] == "Gandla"
    assert result["middle_name"] == "K"
    # Combined name still preserved as audit
    assert result["custom_greythr_full_name"] == "Gandla Sanjeev"


def test_iso_date_of_joining_parsed():
    result = greythr_to_frappe(_real_greythr_response())
    assert result["date_of_joining"] == "2024-01-02"


def test_iso_date_of_birth_parsed():
    result = greythr_to_frappe(_real_greythr_response())
    assert result["date_of_birth"] == "1994-03-15"


def test_gender_m_maps_to_male():
    result = greythr_to_frappe(_real_greythr_response())
    assert result["gender"] == "Male"


def test_gender_f_maps_to_female():
    payload = {**_real_greythr_response(), "gender": "F"}
    result = greythr_to_frappe(payload)
    assert result["gender"] == "Female"


def test_gender_unknown_recorded_as_error_not_set():
    """If greytHR sends a value not in the M/F/O map, omit from result and
    log to mapper_errors — never set an invalid value that would break the
    Frappe Gender Link validation."""
    payload = {**_real_greythr_response(), "gender": "X"}
    result = greythr_to_frappe(payload)
    assert "gender" not in result
    assert any("gender" in e for e in result["_mapping_errors"])


def test_mobile_maps_to_cell_number():
    result = greythr_to_frappe(_real_greythr_response())
    assert result["cell_number"] == "9154064022"


def test_personal_email_mapped_when_present():
    payload = {**_real_greythr_response(),
               "personalEmail": "personal@example.com"}
    result = greythr_to_frappe(payload)
    assert result["personal_email"] == "personal@example.com"


def test_personal_email_omitted_when_null():
    """The mapper's preserve-null pattern — don't overwrite Frappe edits with null."""
    result = greythr_to_frappe(_real_greythr_response())  # personalEmail: null
    assert "personal_email" not in result


def test_leftorg_true_with_leaving_date_sets_status_left():
    """leftorg=true + parseable leavingDate → status=Left + relieving_date set."""
    result = greythr_to_frappe(_real_greythr_response())
    assert result["status"] == "Left"
    assert result["relieving_date"] == "2024-09-02"


def test_leftorg_true_without_leaving_date_stays_active_with_error():
    """leftorg=true but no leavingDate → can't set status=Left without
    relieving_date. Record stays Active; error logged for HR."""
    payload = {**_real_greythr_response(), "leavingDate": None}
    result = greythr_to_frappe(payload)
    assert result["status"] == "Active"
    assert any("leftorg" in e for e in result["_mapping_errors"])


def test_leftorg_camelcase_variant_also_handled():
    """Defensive: accept both `leftorg` and `leftOrg` field names."""
    payload = {**_real_greythr_response(),
               "leftorg": None, "leftOrg": True, "leavingDate": None}
    result = greythr_to_frappe(payload)
    # leftOrg=True without leavingDate → Active + error (same path as leftorg)
    assert result["status"] == "Active"
    assert any("leftorg" in e for e in result["_mapping_errors"])


def test_full_real_response_produces_no_blocking_errors():
    """End-to-end smoke test with the real greytHR response shape."""
    result = greythr_to_frappe(_real_greythr_response())
    # All key fields populated
    for required in ("custom_greythr_employee_id", "employee_number", "first_name",
                     "company_email", "date_of_joining", "status",
                     "custom_greythr_full_name"):
        assert required in result, f"missing required field: {required}"
    # No mapper errors that would block sync
    assert result["_mapping_errors"] == []
