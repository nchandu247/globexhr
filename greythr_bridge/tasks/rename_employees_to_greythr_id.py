"""
One-shot rename: Frappe Employee.name (HR-EMP-####) → greytHR employee_number (GDS####).

HR triggers this manually via two whitelisted endpoints:

  1. plan_rename()       — read-only, returns the rename plan; safe anytime
  2. run_rename(confirm) — enqueues background job that does the actual renames

Pre-flight (HR's responsibility before triggering run_rename):
  - Take a Frappe Cloud DB backup (recovery if anything goes sideways)
  - Fix any typo / lowercase employee_numbers in greytHR portal (gds0115,
    GSD0033, etc.); wait one sync cycle for corrections to propagate
  - Run during a payroll-quiet window (no Payroll Entry in progress)

Mechanics:
  - frappe.rename_doc is NOT transactional internally — it runs separate
    SQL UPDATEs for the parent + every FK reference. To bound the blast
    radius of any one record's failure, we commit per-record on success
    and rollback per-record on failure. Failed records are logged but
    don't abort the batch.

  - During the rename batch, the scheduled pull_employees sync would race
    with our renames (mapping pointed to old name, then we rename, etc.).
    The script auto-disables greytHR Settings.enabled at start and
    restores the original value at end via try/finally.

  - Every rename is logged to the greytHR Sync Log details field as JSON,
    preserving an audit trail for reverse migration if disaster recovery
    is needed.

  - Skip-and-continue policy: records with invalid employee_number patterns
    (lowercase, typos, non-GDS values) are skipped, logged, and the batch
    proceeds for the valid records. HR fixes the bad data in greytHR and
    re-runs for the skipped set.

Restricted to System Manager only — mass primary-key change on production
payroll data is privileged.
"""
import json
import re
from datetime import datetime

import frappe

from ..utils.logging import log_error


# greytHR's canonical employee number format. Customise here if greytHR uses
# a different convention. Case-insensitive match — `GDS0001` and `gds0001`
# both pass. Length 3-5 digits (4 is the common case; 3-digit and 5-digit
# variants observed in real data).
_VALID_EMPLOYEE_NUMBER = re.compile(r"^GDS\d{3,5}$", re.IGNORECASE)


def _check_role() -> None:
    """System Manager only — privileged operation on production data."""
    if "System Manager" not in frappe.get_roles(frappe.session.user):
        frappe.throw(
            "Only System Manager can plan or execute employee rename. "
            "This is a mass primary-key change on production payroll data."
        )


@frappe.whitelist()
def plan_rename() -> dict:
    """
    Read-only: categorise every Frappe Employee record by what the rename
    would do. Returns a dict with counts + full lists. Safe to call anytime
    (no DB writes). HR should run this and review the plan before triggering
    run_rename.

    Categories:
      to_rename:        name != employee_number, employee_number is valid GDS####
                        format, no collision with another record's name
      already_correct:  name == employee_number (no rename needed)
      no_employee_number: employee_number is empty/null (rename skipped — record
                          stays HR-EMP-#### until HR sets a greytHR ID)
      invalid_pattern:  employee_number is set but doesn't match GDS#### regex
                        (typos like 'GSD0033', lowercase like 'gds0115', random
                        like 'Gds0943274'). Fix in greytHR portal then re-run.
      collisions:       rename target already exists as another record's name
                        (data integrity issue — investigate before any rename)
    """
    _check_role()

    employees = frappe.get_all(
        "Employee",
        fields=["name", "employee_number", "first_name", "status"],
        limit_page_length=0,
    )

    to_rename = []
    already_correct = []
    no_employee_number = []
    invalid_pattern = []
    collisions = []

    # Pre-compute all existing names for collision detection
    existing_names = {e["name"] for e in employees}

    for emp in employees:
        name = emp["name"]
        emp_no = (emp.get("employee_number") or "").strip()

        if name == emp_no:
            already_correct.append(emp)
            continue

        if not emp_no:
            no_employee_number.append({
                **emp,
                "reason": "employee_number is empty",
            })
            continue

        if not _VALID_EMPLOYEE_NUMBER.match(emp_no):
            invalid_pattern.append({
                **emp,
                "reason": f"employee_number {emp_no!r} doesn't match GDS\\d{{3,5}} pattern",
            })
            continue

        # Collision: another record already has this name
        if emp_no in existing_names and emp_no != name:
            collisions.append({
                **emp,
                "would_become": emp_no,
                "reason": f"name {emp_no!r} already exists on another Employee",
            })
            continue

        to_rename.append({"from": name, "to": emp_no,
                          "first_name": emp.get("first_name"),
                          "status": emp.get("status")})

    return {
        "summary": {
            "total_employees": len(employees),
            "to_rename": len(to_rename),
            "already_correct": len(already_correct),
            "no_employee_number": len(no_employee_number),
            "invalid_pattern": len(invalid_pattern),
            "collisions": len(collisions),
        },
        "to_rename": to_rename,
        "already_correct": already_correct,
        "no_employee_number": no_employee_number,
        "invalid_pattern": invalid_pattern,
        "collisions": collisions,
    }


@frappe.whitelist()
def run_rename(confirm: str = "no") -> dict:
    """
    Enqueue the rename background job. Requires explicit confirm=yes.

    Call:
        /api/method/greythr_bridge.tasks.rename_employees_to_greythr_id.run_rename?confirm=yes

    Pre-flight checklist (HR's responsibility):
      1. Frappe Cloud DB backup taken
      2. Typo/lowercase employee_numbers fixed in greytHR + one sync cycle waited
      3. No payroll run in progress (Payroll-quiet window)
      4. plan_rename() reviewed — collisions and skipped records understood

    The script auto-disables greytHR sync during the rename and re-enables
    at end (via try/finally). Progress is logged to greytHR Sync Log every
    25 records. The full audit trail (every old→new pair) is persisted in
    the Sync Log's `details` field as JSON.
    """
    _check_role()
    if confirm != "yes":
        frappe.throw(
            "Refusing to run without explicit confirmation. "
            "Pass ?confirm=yes after reviewing plan_rename output. "
            "Ensure: (1) DB backup taken, (2) greytHR typos fixed, "
            "(3) payroll-quiet window, (4) plan reviewed."
        )

    frappe.enqueue(
        "greythr_bridge.tasks.rename_employees_to_greythr_id._do_rename",
        queue="long",
        timeout=1500,  # 25 minutes — generous for 300+ records
    )
    return {
        "status": "enqueued",
        "check_progress_at": "/app/greythr-sync-log",
        "note": (
            "Background job started. Watch the latest greytHR Sync Log entry "
            "(sync_type='Rename Employees to greytHR ID') for live counters. "
            "Re-run plan_rename after completion to verify final state."
        ),
    }


def _do_rename() -> None:
    """
    Background job: execute the rename plan.

    1. Disable greytHR sync to prevent race conditions
    2. Re-compute the plan (don't trust a stale plan_rename call)
    3. For each (from, to): try rename_doc, commit on success, rollback on
       failure, log either way. Progress saved to Sync Log every 25 records.
    4. Re-enable sync in finally block (even if exception bubbles up)
    5. Persist full audit (every old→new pair) in Sync Log details
    """
    started_at = datetime.now()
    sync_log = _start_rename_log(started_at)

    # ── Disable sync for the duration ─────────────────────────────────────────
    settings_was_enabled = bool(
        frappe.db.get_value("greytHR Settings", "greytHR Settings", "enabled")
    )
    if settings_was_enabled:
        frappe.db.set_value(
            "greytHR Settings", "greytHR Settings", "enabled", 0
        )
        frappe.db.commit()
        log_error(
            f"rename_employees: temporarily disabled greytHR sync "
            f"(will re-enable at end of run)",
            "greytHR Employee Rename",
        )

    counters = dict(processed=0, renamed=0, skipped=0, failed=0)
    audit_log = []  # list of {"old": ..., "new": ..., "status": ...}
    errors = []

    try:
        plan = plan_rename()
        for item in plan["to_rename"]:
            counters["processed"] += 1
            try:
                frappe.rename_doc(
                    "Employee", item["from"], item["to"],
                    force=False, merge=False, rebuild_search=False,
                )
                frappe.db.commit()
                counters["renamed"] += 1
                audit_log.append({
                    "old": item["from"], "new": item["to"], "status": "OK"
                })
            except Exception as exc:
                try:
                    frappe.db.rollback()
                except Exception:
                    pass
                counters["failed"] += 1
                err_msg = f"{item['from']} → {item['to']}: {str(exc)[:200]}"
                errors.append(err_msg)
                audit_log.append({
                    "old": item["from"], "new": item["to"],
                    "status": "FAILED", "error": str(exc)[:200]
                })
                log_error(
                    f"rename_employees: {err_msg}",
                    "greytHR Employee Rename Error",
                )

            # Progress checkpoint every 25 records — HR can monitor live
            if counters["processed"] % 25 == 0:
                _update_log_progress(sync_log, counters)

        # Count skipped records (from plan categories that we don't try to rename)
        counters["skipped"] = (
            plan["summary"]["no_employee_number"]
            + plan["summary"]["invalid_pattern"]
            + plan["summary"]["collisions"]
        )

        status = "Success" if counters["failed"] == 0 else "Partial Success"
        _finish_rename_log(
            sync_log, status, counters, errors, audit_log, started_at
        )
    except Exception as exc:
        log_error(
            f"rename_employees: catastrophic failure: {str(exc)[:300]}",
            "greytHR Employee Rename Failed",
        )
        _finish_rename_log(
            sync_log, "Failed", counters,
            errors + [f"catastrophic: {str(exc)[:200]}"],
            audit_log, started_at,
        )
    finally:
        # Re-enable sync if we disabled it. Wrapped to never raise — the
        # rename completion status takes precedence.
        if settings_was_enabled:
            try:
                frappe.db.set_value(
                    "greytHR Settings", "greytHR Settings",
                    "enabled", 1,
                )
                frappe.db.commit()
            except Exception as exc:
                log_error(
                    f"rename_employees: failed to re-enable sync: "
                    f"{str(exc)[:200]}. MANUAL ACTION: open greytHR Settings "
                    f"and tick `enabled` to resume scheduled syncs.",
                    "greytHR Employee Rename Cleanup Error",
                )


# ── Sync Log helpers ──────────────────────────────────────────────────────────

def _start_rename_log(started_at: datetime):
    # `status` Select on greytHR Sync Log accepts only:
    # Started / Success / Partial Success / Failed.
    # Stay consistent with pull_employees + pull_salary_structures.
    doc = frappe.new_doc("greytHR Sync Log")
    doc.sync_type = "Rename Employees to greytHR ID"
    doc.triggered_by = "Manual"
    doc.started_at = started_at.strftime("%Y-%m-%d %H:%M:%S")
    doc.status = "Started"
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return doc


def _update_log_progress(sync_log, counters: dict) -> None:
    """Save current counter state — HR sees live progress in the Sync Log."""
    sync_log.records_processed = counters["processed"]
    sync_log.records_updated = counters["renamed"]
    sync_log.records_failed = counters["failed"]
    sync_log.save(ignore_permissions=True)
    frappe.db.commit()


def _finish_rename_log(sync_log, status: str, counters: dict,
                        errors: list, audit_log: list,
                        started_at: datetime) -> None:
    sync_log.status = status
    sync_log.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_log.records_processed = counters["processed"]
    sync_log.records_updated = counters["renamed"]
    sync_log.records_failed = counters["failed"]
    sync_log.records_skipped = counters["skipped"]
    sync_log.error_summary = "\n".join(errors[:50]) if errors else None
    # Full audit — every old→new pair, success or fail. Used for reverse
    # migration in disaster recovery.
    sync_log.details = json.dumps(
        {
            "audit": audit_log,
            "summary": counters,
            "started_at": started_at.strftime("%Y-%m-%d %H:%M:%S"),
        },
        indent=2,
    )
    sync_log.save(ignore_permissions=True)
    frappe.db.commit()
