"""
Maps greytHR salary repository (tree structure) to Frappe Salary Component records.

greytHR returns salary components as a tree with 3 top-level nodes (Earnings,
Deductions, and typically a net/summary node). Each node has {id, name, type,
parent, children, taxable, description}. This mapper recursively flattens the
tree into a list of individual components ready to create in Frappe.
"""


# ── type mapping ──────────────────────────────────────────────────────────────

_TYPE_MAP = {
    "earning":                "Earning",
    "earnings":               "Earning",
    "deduction":              "Deduction",
    "deductions":             "Deduction",
    "employers_contribution": "Earning",   # employer PF/ESI — treated as Earning
    "employer_contribution":  "Earning",
}

_KNOWN_ABBR = {
    "Basic":                    "BAS",
    "Basic Pay":                "BAS",
    "HRA":                      "HRA",
    "House Rent Allowance":     "HRA",
    "Special Allowance":        "SA",
    "Provident Fund":           "PF",
    "Employee PF":              "EPF",
    "Employer PF":              "ERPF",
    "ESI":                      "ESI",
    "Employee ESI":             "EESI",
    "Employer ESI":             "ERESI",
    "Professional Tax":         "PT",
    "TDS":                      "TDS",
    "LTA":                      "LTA",
    "Leave Travel Allowance":   "LTA",
    "Medical Allowance":        "MED",
    "Gross":                    "GRS",
    "Net Pay":                  "NET",
    "Net Salary":               "NET",
}


# ── public API ────────────────────────────────────────────────────────────────

def flatten_repository(repository_data: list) -> list:
    """
    Recursively walk the greytHR salary tree and return a flat list of components.

    All nodes (including intermediate grouping nodes) are returned so that
    Frappe HR can represent the full component hierarchy. Nodes without a type
    inherit the type from their nearest typed ancestor.

    Args:
        repository_data: The value of result["data"] from get_salary_repository()

    Returns:
        Flat list of component dicts with keys:
        greythr_id, name, description, component_type, is_tax_applicable
    """
    components = []
    for root_node in repository_data:
        _walk(root_node, components, inherited_type=None)
    return components


def component_to_frappe(component: dict) -> dict:
    """
    Convert a flattened greytHR component dict to Frappe Salary Component fields.

    Returns a dict ready to set on a Frappe Salary Component document.
    """
    name = component.get("name", "").strip()
    return {
        "salary_component":       name,
        "salary_component_abbr":  _abbreviation(name),
        "description":            component.get("description") or "",
        "type":                   component.get("component_type", "Earning"),
        "is_tax_applicable":      1 if component.get("is_tax_applicable") else 0,
    }


# ── internals ─────────────────────────────────────────────────────────────────

def _walk(node: dict, result: list, inherited_type: str) -> None:
    """Recursive DFS walk of the greytHR salary tree."""
    raw_type = node.get("type", "")
    component_type = _TYPE_MAP.get(raw_type.lower(), None) if raw_type else None
    effective_type = component_type or inherited_type or "Earning"

    node_id = node.get("id")
    if node_id:
        result.append(
            {
                "greythr_id":        node_id,
                "name":              (node.get("name") or "").strip(),
                "description":       node.get("description") or "",
                "component_type":    effective_type,
                "is_tax_applicable": bool(node.get("taxable")),
                "parent_id":         node.get("parent"),
            }
        )

    for child in node.get("children", []):
        _walk(child, result, inherited_type=effective_type)


def _abbreviation(name: str) -> str:
    """
    Generate a unique abbreviation for a salary component name.

    Checks the known abbreviation table first; falls back to initials
    or a prefix. The caller is responsible for deduplicating if two
    unknown components produce the same abbreviation.
    """
    if name in _KNOWN_ABBR:
        return _KNOWN_ABBR[name]

    words = name.split()
    if len(words) == 1:
        return name[:4].upper()

    # Initials of up to 4 words
    abbr = "".join(w[0].upper() for w in words[:4])
    return abbr or name[:4].upper()
