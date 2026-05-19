"""
Tests for salary_mapper.py — pure unit tests, no HTTP or frappe calls.
"""
from greythr_bridge.mappers.salary_mapper import (
    flatten_repository,
    component_to_frappe,
    _abbreviation,
)


# ── sample data ───────────────────────────────────────────────────────────────

def _tree():
    """Minimal salary tree matching greytHR's confirmed response shape."""
    return [
        {
            "id": "1",
            "name": "Earnings",
            "type": "earning",
            "parent": None,
            "taxable": False,
            "description": "All earnings",
            "children": [
                {
                    "id": "11",
                    "name": "Basic",
                    "type": "earning",
                    "parent": "1",
                    "taxable": True,
                    "description": "Basic pay",
                    "children": [],
                },
                {
                    "id": "12",
                    "name": "HRA",
                    "type": "earning",
                    "parent": "1",
                    "taxable": False,
                    "description": "House rent allowance",
                    "children": [],
                },
            ],
        },
        {
            "id": "2",
            "name": "Deductions",
            "type": "deduction",
            "parent": None,
            "taxable": False,
            "description": "All deductions",
            "children": [
                {
                    "id": "21",
                    "name": "Provident Fund",
                    "type": "deduction",
                    "parent": "2",
                    "taxable": False,
                    "description": "PF deduction",
                    "children": [],
                },
            ],
        },
    ]


# ── flatten_repository ────────────────────────────────────────────────────────

def test_flatten_returns_all_nodes():
    result = flatten_repository(_tree())
    names = [c["name"] for c in result]
    assert "Earnings" in names
    assert "Basic" in names
    assert "HRA" in names
    assert "Deductions" in names
    assert "Provident Fund" in names
    assert len(result) == 5


def test_flatten_maps_earning_type():
    result = flatten_repository(_tree())
    basic = next(c for c in result if c["name"] == "Basic")
    assert basic["component_type"] == "Earning"


def test_flatten_maps_deduction_type():
    result = flatten_repository(_tree())
    pf = next(c for c in result if c["name"] == "Provident Fund")
    assert pf["component_type"] == "Deduction"


def test_flatten_inherits_type_from_parent():
    """Child nodes without explicit type inherit from parent."""
    tree = [
        {
            "id": "1",
            "name": "Earnings",
            "type": "earning",
            "parent": None,
            "taxable": False,
            "description": "",
            "children": [
                {
                    "id": "11",
                    "name": "Special Allowance",
                    "type": "",          # no type on child
                    "parent": "1",
                    "taxable": False,
                    "description": "",
                    "children": [],
                }
            ],
        }
    ]
    result = flatten_repository(tree)
    sa = next(c for c in result if c["name"] == "Special Allowance")
    assert sa["component_type"] == "Earning"  # inherited from parent


def test_flatten_taxable_flag():
    result = flatten_repository(_tree())
    basic = next(c for c in result if c["name"] == "Basic")
    hra = next(c for c in result if c["name"] == "HRA")
    assert basic["is_tax_applicable"] is True
    assert hra["is_tax_applicable"] is False


def test_flatten_empty_data():
    assert flatten_repository([]) == []


def test_flatten_no_children():
    tree = [
        {
            "id": "1",
            "name": "Basic",
            "type": "earning",
            "parent": None,
            "taxable": True,
            "description": "Basic pay",
            "children": [],
        }
    ]
    result = flatten_repository(tree)
    assert len(result) == 1
    assert result[0]["name"] == "Basic"


# ── component_to_frappe ───────────────────────────────────────────────────────

def test_component_to_frappe_earning():
    component = {
        "name": "Basic",
        "description": "Basic pay",
        "component_type": "Earning",
        "is_tax_applicable": True,
    }
    result = component_to_frappe(component)
    assert result["salary_component"] == "Basic"
    assert result["salary_component_abbr"] == "BAS"
    assert result["type"] == "Earning"
    assert result["is_tax_applicable"] == 1
    assert result["description"] == "Basic pay"


def test_component_to_frappe_deduction():
    component = {
        "name": "Provident Fund",
        "description": "PF",
        "component_type": "Deduction",
        "is_tax_applicable": False,
    }
    result = component_to_frappe(component)
    assert result["salary_component"] == "Provident Fund"
    assert result["salary_component_abbr"] == "PF"
    assert result["type"] == "Deduction"
    assert result["is_tax_applicable"] == 0


def test_component_to_frappe_no_taxable():
    component = {
        "name": "HRA",
        "description": "",
        "component_type": "Earning",
        "is_tax_applicable": False,
    }
    result = component_to_frappe(component)
    assert result["is_tax_applicable"] == 0


# ── _abbreviation ─────────────────────────────────────────────────────────────

def test_known_abbreviations():
    assert _abbreviation("Basic") == "BAS"
    assert _abbreviation("HRA") == "HRA"
    assert _abbreviation("Professional Tax") == "PT"
    assert _abbreviation("TDS") == "TDS"
    assert _abbreviation("Provident Fund") == "PF"


def test_unknown_single_word():
    assert _abbreviation("Gratuity") == "GRAT"


def test_unknown_multi_word():
    assert _abbreviation("Long Term Incentive") == "LTI"


def test_empty_name():
    result = _abbreviation("")
    assert isinstance(result, str)
