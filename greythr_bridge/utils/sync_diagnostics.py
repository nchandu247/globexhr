"""
Diagnostic endpoints for greytHR ↔ Frappe employee sync.

These show what greytHR's API actually returns for one employee, what the
mapper extracts from it, and what would (or did) change on the Frappe
record. Used to debug "sync claims success but records aren't enriched"
class of failures.

All endpoints are read-only by default. The save attempt is opt-in via
an explicit `save_dry_run=False` query param, and even then runs inside
a transaction we can roll back if needed (caller controls).

Restricted to System Manager — exposes greytHR API tokens indirectly via
response shape and is intended for debugging only.
"""
import traceback
from datetime import datetime

import frappe

from ..api.employee import get_employee
from ..mappers.employee_mapper import greythr_to_frappe


def _check_admin_role() -> None:
    """System Manager only — diagnostics expose detail useful for debugging
    but also useful for poking at the sync pipeline."""
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw("Only System Manager can run sync diagnostics.")


def _coerce_bool(value, default: bool = True) -> bool:
    """Frappe HTTP params arrive as strings; coerce explicitly."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("false", "0", "no", "")
    return default


@frappe.whitelist()
def inspect_sync_for_employee(employee_name: str, save_dry_run=True) -> dict:
    """
    Full diagnostic for one Frappe Employee: pulls its greytHR ID from the
    mapping, calls greytHR for that single employee, runs the mapper, and
    reports exactly what would change.

    Args:
        employee_name: Frappe Employee `name` (e.g., "HR-EMP-00869")
        save_dry_run: if True (default), only reports — no save() called.
                      If "false" / "0" / "no" / False, attempts to save and
                      returns the result (or exception traceback).

    Output:
        - frappe_record_now: current values of key fields on this record
        - greythr_mapping: the Mapping doc linking Frappe → greytHR
        - greythr_api_response: raw bytes from greytHR's /employees/{id} endpoint
        - extracted_employee_payload: the employee dict extracted from the response
        - mapper_output: what the mapper produced from that payload
        - mapper_errors: fields the mapper couldn't extract (e.g., missing firstName)
        - would_change_fields: list of {field, current, would_set_to} per field
                               whose value would change
        - save_attempted: True if save_dry_run was disabled
        - save_result: "OK" / "FAILED: <error>" / None

    Call:
        /api/method/greythr_bridge.utils.sync_diagnostics.inspect_sync_for_employee
            ?employee_name=HR-EMP-00869
            [&save_dry_run=false]   # optional, defaults to true (safe)
    """
    _check_admin_role()
    save_dry_run = _coerce_bool(save_dry_run, default=True)

    # ── Current Frappe state ──────────────────────────────────────────────────
    try:
        employee_doc = frappe.get_doc("Employee", employee_name)
    except frappe.DoesNotExistError:
        return {"error": f"Employee '{employee_name}' not found in Frappe."}

    snapshot_fields = (
        "name", "employee_number", "first_name", "last_name", "company_email",
        "status", "date_of_joining",
        "custom_greythr_employee_id", "custom_greythr_last_synced",
        "modified",
    )
    frappe_record_now = {
        field: employee_doc.get(field) for field in snapshot_fields
    }

    # ── Mapping lookup ────────────────────────────────────────────────────────
    mapping_rows = frappe.get_all(
        "greytHR Employee Mapping",
        filters={"frappe_employee": employee_name},
        fields=["name", "greythr_employee_id", "greythr_employee_no",
                "sync_status", "last_sync_error", "last_synced_at"],
        limit=1,
    )
    if not mapping_rows:
        return {
            "frappe_record_now": frappe_record_now,
            "error": (
                f"No greytHR Employee Mapping for {employee_name}. "
                f"Cannot fetch from greytHR without an employee ID."
            ),
        }
    mapping = mapping_rows[0]
    greythr_id = mapping["greythr_employee_id"]

    if not greythr_id:
        return {
            "frappe_record_now": frappe_record_now,
            "greythr_mapping": mapping,
            "error": (
                "Mapping row exists but greythr_employee_id is empty. "
                "This mapping is broken — the bulk-import on 2026-05-19 likely "
                "created placeholder mapping rows without populating the ID."
            ),
        }

    # ── greytHR API call ──────────────────────────────────────────────────────
    raw_response = None
    api_error = None
    try:
        raw_response = get_employee(greythr_id)
    except Exception as exc:
        api_error = f"{type(exc).__name__}: {str(exc)[:300]}"

    if api_error:
        return {
            "frappe_record_now": frappe_record_now,
            "greythr_mapping": mapping,
            "greythr_api_error": api_error,
        }

    # greytHR endpoints sometimes wrap a single doc in {"data": [...]} too
    extracted = raw_response.get("data") if isinstance(raw_response, dict) else raw_response
    if isinstance(extracted, list) and extracted:
        extracted = extracted[0]
    elif not extracted:
        extracted = raw_response  # already the bare doc

    # ── Mapper output ─────────────────────────────────────────────────────────
    mapped = greythr_to_frappe(extracted or {})
    mapper_errors = mapped.pop("_mapping_errors", [])

    # ── Compute would-change diff ─────────────────────────────────────────────
    would_change = []
    for field, new_value in mapped.items():
        current = employee_doc.get(field)
        if current != new_value:
            would_change.append({
                "field": field,
                "current": current,
                "would_set_to": new_value,
            })

    # ── Optional: actually attempt the save ───────────────────────────────────
    save_result = None
    if not save_dry_run:
        try:
            for field, value in mapped.items():
                if not field.startswith("_"):
                    employee_doc.set(field, value)
            employee_doc.custom_greythr_last_synced = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            employee_doc.flags.ignore_mandatory = True
            employee_doc.save(ignore_permissions=True)
            frappe.db.commit()
            save_result = "OK"
        except Exception as exc:
            try:
                frappe.db.rollback()
            except Exception:
                pass
            save_result = (
                f"FAILED: {type(exc).__name__}: {str(exc)[:300]}\n\n"
                f"Traceback:\n{traceback.format_exc()[:2000]}"
            )

    return {
        "frappe_record_now": frappe_record_now,
        "greythr_mapping": mapping,
        "greythr_api_response": raw_response,
        "extracted_employee_payload": extracted,
        "mapper_output": mapped,
        "mapper_errors": mapper_errors,
        "would_change_fields": would_change,
        "would_change_count": len(would_change),
        "save_attempted": not save_dry_run,
        "save_result": save_result,
    }


@frappe.whitelist()
def inspect_greythr_employee(greythr_id: str) -> dict:
    """
    Show what greytHR returns for a given employeeId and what the mapper
    extracts. NO Frappe Employee lookup, NO save — pure read.

    Use when investigating a record that's failing the sync BEFORE it can
    be created in Frappe (so no Mapping exists yet). Companion to
    inspect_sync_for_employee, which needs an existing Frappe Employee.

    Args:
        greythr_id: the greytHR employeeId, as a string (e.g., "389")

    Output:
        - greythr_id: echo of the input
        - greythr_api_response: raw bytes from /employees/{id}
        - extracted_employee_payload: the employee dict pulled out of the response
        - mapper_output: what the mapper would produce for this record
                         (relieving_date intentionally dropped if invalid)
        - mapper_errors: sanity-check messages + any field-mapping errors

    Call:
        /api/method/greythr_bridge.utils.sync_diagnostics.inspect_greythr_employee
            ?greythr_id=389
    """
    _check_admin_role()

    if not greythr_id:
        return {"error": "greythr_id is required"}

    try:
        raw_response = get_employee(greythr_id)
    except Exception as exc:
        return {
            "greythr_id": greythr_id,
            "greythr_api_error": f"{type(exc).__name__}: {str(exc)[:300]}",
        }

    extracted = (
        raw_response.get("data") if isinstance(raw_response, dict) else raw_response
    )
    if isinstance(extracted, list) and extracted:
        extracted = extracted[0]
    elif not extracted:
        extracted = raw_response

    mapped = greythr_to_frappe(extracted or {})
    mapper_errors = mapped.pop("_mapping_errors", [])

    return {
        "greythr_id": greythr_id,
        "greythr_api_response": raw_response,
        "extracted_employee_payload": extracted,
        "mapper_output": mapped,
        "mapper_errors": mapper_errors,
    }


@frappe.whitelist()
def list_recent_sync_errors(limit: int = 20) -> dict:
    """
    Recent Error Log entries related to greytHR sync/employee operations.
    Read-only. Restricted to System Manager.

    Helpful companion to the audit endpoint when investigating why records
    aren't being enriched.
    """
    _check_admin_role()
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 20

    errors = frappe.get_all(
        "Error Log",
        filters=[
            ["title", "like", "%greytHR%"],
        ],
        fields=["name", "title", "creation", "error"],
        order_by="creation desc",
        limit_page_length=limit,
    )

    # Truncate error stack traces to keep response readable
    for e in errors:
        if e.get("error") and len(e["error"]) > 500:
            e["error"] = e["error"][:500] + "...(truncated)"

    return {"count": len(errors), "errors": errors}
