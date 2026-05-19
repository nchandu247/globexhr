"""
Pull salary components from greytHR into Frappe HR.

Scheduled daily at 2 AM IST via hooks.py scheduler_events.
Phase 3 scope: sync Salary Component records only.
Employee Salary Structure Assignments (per-employee CTC mirror) are deferred
until the greytHR employee salary endpoint is verified on the Essential plan.
"""
import frappe
from datetime import datetime

from ..api.payroll import get_salary_repository
from ..mappers.salary_mapper import flatten_repository, component_to_frappe
from ..utils.logging import log_error


# ── public entry points ────────────────────────────────────────────────────────

def run():
    """Scheduled entry point — daily at 2 AM IST."""
    _pull(triggered_by="Scheduled")


@frappe.whitelist()
def run_now():
    """
    Bench-callable and whitelisted for manual triggering.

    bench --site hr.globexdigital.ai execute greythr_bridge.tasks.pull_salary_structures.run_now
    """
    frappe.enqueue(
        "greythr_bridge.tasks.pull_salary_structures._pull",
        queue="long",
        triggered_by="Manual",
    )


# ── core logic ─────────────────────────────────────────────────────────────────

def _pull(triggered_by: str = "Scheduled") -> None:
    settings = frappe.get_single("greytHR Settings")
    if not settings.enabled:
        return

    started_at = datetime.now()
    sync_log = _start_sync_log(triggered_by, started_at)
    counters = dict(processed=0, created=0, updated=0, failed=0, skipped=0)
    errors = []

    try:
        result = get_salary_repository()
        repository_data = result.get("data", [])

        if not repository_data:
            _finish_sync_log(sync_log, "Success", counters, errors)
            return

        components = flatten_repository(repository_data)

        for component in components:
            counters["processed"] += 1
            try:
                outcome = _sync_component(component)
                counters[outcome] += 1
            except Exception as exc:
                counters["failed"] += 1
                errors.append(
                    f"{component.get('name', '?')}: {str(exc)[:100]}"
                )
                log_error(
                    f"pull_salary: component={component.get('name')} error={str(exc)[:200]}",
                    "greytHR Pull Salary Error",
                )

        frappe.db.set_value(
            "greytHR Settings",
            "greytHR Settings",
            "last_salary_sync",
            started_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        status = "Partial Success" if counters["failed"] else "Success"
        _finish_sync_log(sync_log, status, counters, errors)

    except Exception as exc:
        log_error(
            f"pull_salary_structures: run failed: {str(exc)[:300]}",
            "greytHR Pull Salary Failed",
        )
        _finish_sync_log(sync_log, "Failed", counters, errors + [str(exc)[:200]])
        _notify_failure(sync_log)


def _sync_component(component: dict) -> str:
    """
    Ensure a greytHR salary component exists as a Frappe Salary Component.

    Returns: "created" | "updated" | "skipped"
    """
    name = component.get("name", "").strip()
    if not name:
        return "skipped"

    mapped = component_to_frappe(component)

    existing = frappe.get_all(
        "Salary Component",
        filters={"salary_component": name},
        fields=["name"],
        limit=1,
    )

    if existing:
        doc = frappe.get_doc("Salary Component", existing[0]["name"])
        changed = False
        for field, value in mapped.items():
            if doc.get(field) != value:
                doc.set(field, value)
                changed = True
        if changed:
            doc.flags.ignore_mandatory = True
            doc.save(ignore_permissions=True)
            return "updated"
        return "skipped"

    else:
        doc = frappe.new_doc("Salary Component")
        for field, value in mapped.items():
            doc.set(field, value)
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        return "created"


# ── sync log helpers ───────────────────────────────────────────────────────────

def _start_sync_log(triggered_by: str, started_at: datetime):
    doc = frappe.new_doc("greytHR Sync Log")
    doc.sync_type = "Pull Salary"
    doc.status = "Started"
    doc.triggered_by = triggered_by
    doc.started_at = started_at.strftime("%Y-%m-%d %H:%M:%S")
    doc.insert(ignore_permissions=True)
    return doc


def _finish_sync_log(sync_log, status: str, counters: dict, errors: list) -> None:
    sync_log.status = status
    sync_log.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_log.records_processed = counters["processed"]
    sync_log.records_created = counters["created"]
    sync_log.records_updated = counters["updated"]
    sync_log.records_failed = counters["failed"]
    sync_log.records_skipped = counters["skipped"]
    sync_log.error_summary = "\n".join(errors[:20]) if errors else None
    sync_log.save(ignore_permissions=True)


def _notify_failure(sync_log) -> None:
    """Notify System Managers when salary sync fails."""
    managers = frappe.get_all(
        "Has Role",
        filters={"role": "System Manager", "parenttype": "User"},
        fields=["parent"],
    )
    for row in managers:
        frappe.share.add(
            doctype="greytHR Sync Log",
            name=sync_log.name,
            user=row["parent"],
            notify=1,
            flags={"ignore_share_permission": True},
        )
