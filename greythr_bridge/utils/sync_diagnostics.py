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
from .logging import log_error


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
def force_resync_employee(frappe_employee: str, greythr_id: str) -> dict:
    """
    HR repair tool: force-resync a Frappe Employee from an EXPLICITLY-NAMED
    greytHR record, bypassing _find_frappe_employee and the defensive
    matching check. Use ONLY when you've verified that:

      1. The Frappe Employee at `frappe_employee` (the slot) is the right
         place for greytHR record `greythr_id`'s data, AND
      2. The existing mapping/fields on that Frappe Employee are wrong
         (typically because past sync hijacks corrupted them by linking
         the slot to the wrong greytHR record).

    Example use case (2026-05-25): Frappe slots GDS0215/0216/0228/0282 had
    their mappings stuck on the OLDER greytHR employment ID for each
    rehired person, so every sync re-overwrote them with the old
    employment's data. v5's defensive check correctly REFUSED to keep
    overwriting but couldn't auto-correct (can't distinguish "fix this
    corrupted slot" from "leave this different-person slot alone"). HR
    used this endpoint to point each slot at its correct greytHR ID, after
    which normal sync re-stabilised.

    Args:
        frappe_employee: Frappe Employee `name` (the primary key / slot)
        greythr_id: the CORRECT greytHR `employeeId` for this slot

    What it does:
        1. Fetches greytHR's data for `greythr_id` (NOT via the existing
           mapping — uses the explicit ID you provide)
        2. Runs the mapper on it
        3. Updates the Frappe Employee's fields to match (overwrite — this
           is the whole point)
        4. Updates the mapping row's `greythr_employee_id` and
           `greythr_employee_no` to match (creates the mapping if absent)
        5. Logs an audit entry under "greytHR Forced Resync"
        6. Returns a summary of what changed

    Skips _find_frappe_employee + _is_different_employment ENTIRELY — this
    is the explicit override. Use sparingly; misuse can re-corrupt records.

    Call (System Manager only):
        /api/method/greythr_bridge.utils.sync_diagnostics.force_resync_employee
            ?frappe_employee=GDS0215&greythr_id=250
    """
    _check_admin_role()

    if not frappe_employee:
        return {"error": "frappe_employee is required"}
    if not greythr_id:
        return {"error": "greythr_id is required"}

    # ── 1. Verify Frappe Employee exists ──────────────────────────────────────
    try:
        employee_doc = frappe.get_doc("Employee", frappe_employee)
    except frappe.DoesNotExistError:
        return {
            "error": f"Frappe Employee '{frappe_employee}' not found. "
                     f"This endpoint requires an existing slot — it does NOT "
                     f"create new Employees. Use the regular sync for that."
        }

    # ── 2. Fetch greytHR data for the EXPLICIT ID (not the mapping's stale one) ─
    try:
        raw_response = get_employee(greythr_id)
    except Exception as exc:
        return {
            "frappe_employee": frappe_employee,
            "greythr_id": greythr_id,
            "error": f"greytHR API failed: {type(exc).__name__}: {str(exc)[:300]}",
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

    # Sanity check: mapper must have a greytHR ID, and it must match what we
    # were told. If they disagree, greytHR's `/employees/{id}` endpoint
    # returned data for a different record — abort.
    mapped_gid = str(mapped.get("custom_greythr_employee_id") or "")
    if mapped_gid and mapped_gid != str(greythr_id):
        return {
            "error": f"greytHR API returned data for ID {mapped_gid!r} when "
                     f"we asked for ID {greythr_id!r}. Aborting to avoid "
                     f"applying mismatched data.",
            "frappe_employee": frappe_employee,
            "requested_greythr_id": greythr_id,
            "returned_greythr_id": mapped_gid,
        }

    # ── 3. Snapshot what's about to change (for audit + response) ─────────────
    snapshot_fields = (
        "employee_number", "first_name", "last_name", "company_email",
        "personal_email", "status", "date_of_joining", "relieving_date",
        "custom_greythr_employee_id",
    )
    before = {f: employee_doc.get(f) for f in snapshot_fields}

    # ── 4. Apply mapped fields to the Frappe Employee ─────────────────────────
    try:
        for field, value in mapped.items():
            if field.startswith("_"):
                continue
            employee_doc.set(field, value)
        employee_doc.custom_greythr_last_synced = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        employee_doc.flags.ignore_mandatory = True
        employee_doc.save(ignore_permissions=True)
    except Exception as exc:
        try:
            frappe.db.rollback()
        except Exception:
            pass
        return {
            "error": f"Failed to save Frappe Employee fields: "
                     f"{type(exc).__name__}: {str(exc)[:300]}",
            "traceback": traceback.format_exc()[:2000],
            "frappe_employee": frappe_employee,
            "greythr_id": greythr_id,
        }

    # ── 5. Update (or create) the mapping row to point at the correct ID ──────
    greythr_no = (extracted or {}).get("employeeNo") or mapped.get("employee_number")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mapping_action = None

    existing_mapping_rows = frappe.get_all(
        "greytHR Employee Mapping",
        filters={"frappe_employee": frappe_employee},
        fields=["name", "greythr_employee_id", "greythr_employee_no"],
        limit=1,
        ignore_permissions=True,
    )
    try:
        if existing_mapping_rows:
            mapping_doc = frappe.get_doc(
                "greytHR Employee Mapping", existing_mapping_rows[0]["name"]
            )
            mapping_action = (
                f"corrected (was greythr_employee_id="
                f"{existing_mapping_rows[0].get('greythr_employee_id')!r}, "
                f"now {greythr_id!r})"
            )
            mapping_doc.greythr_employee_id = greythr_id
            if greythr_no:
                mapping_doc.greythr_employee_no = greythr_no
            mapping_doc.last_synced_at = now
            mapping_doc.sync_status = "In Sync"
            mapping_doc.last_sync_error = None
            mapping_doc.save(ignore_permissions=True)
        else:
            mapping_doc = frappe.new_doc("greytHR Employee Mapping")
            mapping_doc.frappe_employee = frappe_employee
            mapping_doc.greythr_employee_id = greythr_id
            mapping_doc.greythr_employee_no = greythr_no
            mapping_doc.first_synced_at = now
            mapping_doc.last_synced_at = now
            mapping_doc.sync_status = "In Sync"
            mapping_doc.insert(ignore_permissions=True)
            mapping_action = "created (none existed)"
        frappe.db.commit()
    except Exception as exc:
        try:
            frappe.db.rollback()
        except Exception:
            pass
        return {
            "error": f"Frappe Employee fields updated, but mapping update "
                     f"failed: {type(exc).__name__}: {str(exc)[:300]}. "
                     f"State is partial — re-run after investigating.",
            "frappe_employee": frappe_employee,
            "greythr_id": greythr_id,
        }

    # ── 6. Audit log ──────────────────────────────────────────────────────────
    after = {f: employee_doc.get(f) for f in snapshot_fields}
    changed_fields = {f: {"before": before[f], "after": after[f]}
                      for f in snapshot_fields if before[f] != after[f]}
    log_error(
        f"force_resync_employee: {frappe_employee} → greytHR ID {greythr_id} "
        f"({greythr_no}). Mapping {mapping_action}. "
        f"Fields changed: {list(changed_fields.keys()) or 'none'}.",
        "greytHR Forced Resync",
    )

    return {
        "frappe_employee": frappe_employee,
        "greythr_id": greythr_id,
        "greythr_employee_no": greythr_no,
        "mapping_action": mapping_action,
        "fields_changed": changed_fields,
        "mapper_errors": mapper_errors,
        "result": "OK",
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
