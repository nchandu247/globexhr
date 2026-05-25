"""
Pull employees from greytHR into Frappe HR.

Scheduled every 15 minutes via hooks.py scheduler_events.
Depends on: greytHR Employee Mapping DocType (task 2.1),
            custom fields on Employee (task 2.2).
"""
import frappe
from datetime import date, datetime

from ..api.employee import list_employees
from ..mappers.employee_mapper import greythr_to_frappe
from ..utils.logging import log_error


def _values_differ(current, new) -> bool:
    """
    Compare current Frappe value vs mapper-produced new value, accounting
    for type mismatches that would otherwise produce false positives.

    Why: Frappe stores Date fields as Python `date` objects and Datetime
    fields as `datetime` objects, but the mapper produces ISO strings
    ("2024-01-02"). Naïve `!=` returns True even when semantically equal,
    causing the sync to call save() on every run when nothing changed.

    Coerce date/datetime objects to their ISO string forms before comparing.
    """
    if current is None and new is None:
        return False
    if current is None or new is None:
        return True
    if isinstance(current, datetime):
        current = current.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(current, date):
        current = current.strftime("%Y-%m-%d")
    if isinstance(new, datetime):
        new = new.strftime("%Y-%m-%d %H:%M:%S")
    elif isinstance(new, date):
        new = new.strftime("%Y-%m-%d")
    return current != new


# ── public entry points ────────────────────────────────────────────────────────

def run():
    """Scheduled entry point — called every 15 minutes by Frappe scheduler."""
    _pull(triggered_by="Scheduled")


@frappe.whitelist()
def run_now():
    """
    Bench-callable and whitelisted for manual triggering.

    bench --site hr.globexdigital.ai execute greythr_bridge.tasks.pull_employees.run_now
    """
    frappe.enqueue(
        "greythr_bridge.tasks.pull_employees._pull",
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
    warnings = []  # per-record mapper warnings (non-fatal) surfaced into error_summary

    try:
        # Frappe Datetime fields return datetime objects — convert to string for API params
        last_sync = settings.last_employee_sync
        if isinstance(last_sync, datetime):
            last_sync = last_sync.strftime("%Y-%m-%d %H:%M:%S")

        page = 1
        while True:
            result = list_employees(
                page=page,
                size=50,
                updated_after=last_sync,
            )
            employees = result.get("data", [])
            if not employees:
                break

            sync_log.resume_cursor = str(page)
            sync_log.save(ignore_permissions=True)

            for emp in employees:
                counters["processed"] += 1
                try:
                    outcome = _sync_one(emp, warnings=warnings)
                    counters[outcome] += 1
                except Exception as exc:
                    counters["failed"] += 1
                    emp_id = emp.get("employeeId", "unknown")
                    errors.append(f"{emp_id}: {str(exc)[:100]}")
                    log_error(
                        f"pull_employees: employeeId={emp_id} error={str(exc)[:200]}",
                        "greytHR Pull Employee Error",
                    )

            page += 1

        # Only advance the cursor on full success.
        # Use db.set_value to avoid version conflict — GreytHRClient saves settings
        # multiple times during the run (to cache token), making the local settings
        # object stale by the time we get here.
        frappe.db.set_value(
            "greytHR Settings",
            "greytHR Settings",
            "last_employee_sync",
            started_at.strftime("%Y-%m-%d %H:%M:%S"),
        )
        _finish_sync_log(sync_log, "Success", counters, errors, warnings)

    except Exception as exc:
        log_error(f"pull_employees: run failed: {str(exc)[:300]}", "greytHR Pull Employees Failed")
        _finish_sync_log(sync_log, "Failed", counters, errors + [str(exc)[:200]], warnings)
        _notify_failure(sync_log)


def _sync_one(greythr_emp: dict, warnings: list | None = None) -> str:
    """
    Sync one greytHR employee record into Frappe HR.

    Args:
        greythr_emp: raw greytHR record dict
        warnings: optional list — if provided, per-record mapper warnings
                  (e.g., "gender: unrecognised value 'X'", "leftorg=true but
                  no leavingDate") are appended with `employeeId:` prefix so
                  the caller can surface them in the Sync Log's
                  `error_summary` field. Defaults to None for backwards
                  compatibility with single-shot test callers.

    Returns: "created" | "updated" | "skipped"
    Raises on unrecoverable error (caller increments failed counter).
    """
    mapped = greythr_to_frappe(greythr_emp)
    mapping_errors = mapped.pop("_mapping_errors", [])

    if warnings is not None and mapping_errors:
        emp_id = mapped.get("custom_greythr_employee_id") or greythr_emp.get("employeeId") or "unknown"
        warnings.extend(f"{emp_id}: {msg}" for msg in mapping_errors)

    if not mapped.get("custom_greythr_employee_id"):
        raise ValueError(f"employeeId missing — {mapping_errors}")

    greythr_id = mapped["custom_greythr_employee_id"]

    # ── matching priority ──────────────────────────────────────────────────────
    frappe_employee = _find_frappe_employee(mapped, greythr_id)

    if frappe_employee == "DUPLICATE":
        return "skipped"

    if frappe_employee:
        # Update existing employee — only changed fields
        changed = False
        for field, value in mapped.items():
            if field.startswith("_"):
                continue
            current = frappe_employee.get(field)
            if _values_differ(current, value):
                frappe_employee.set(field, value)
                changed = True

        if changed:
            # ignore_mandatory: syncing from external system — not all Frappe-required
            # fields (gender, date_of_birth) are available in greytHR's list endpoint
            frappe_employee.custom_greythr_last_synced = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            frappe_employee.flags.ignore_mandatory = True
            frappe_employee.save(ignore_permissions=True)
        _upsert_mapping(frappe_employee.name, greythr_id, greythr_emp.get("employeeNo"))
        # Counter-honesty fix (2026-05-23): return "skipped" when nothing actually
        # changed. Previously this always returned "updated" — which masked the
        # ghost-records bug where sync runs reported "340 updated" while not a
        # single record was actually enriched. See diagnostics endpoint:
        # greythr_bridge.utils.sync_diagnostics.inspect_sync_for_employee
        return "updated" if changed else "skipped"

    else:
        # Create new Frappe Employee
        doc = frappe.new_doc("Employee")
        # Use greytHR's employee_number as the Frappe primary key so HR sees
        # matching IDs across both systems. Falls back to Frappe HR's default
        # naming series (HR-EMP-####) only when employee_number is empty.
        # Defense-in-depth: hooks_handlers.employee.set_name_from_greythr_id
        # (a before_insert hook) does the same — this explicit set protects
        # the sync path even if the hook is somehow disabled.
        emp_no = mapped.get("employee_number")
        if emp_no:
            doc.name = emp_no
            doc.flags.name_set = True
        for field, value in mapped.items():
            if field.startswith("_"):
                continue
            doc.set(field, value)

        doc.custom_greythr_last_synced = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # ignore_mandatory: gender, date_of_birth not available in greytHR list endpoint
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        _upsert_mapping(doc.name, greythr_id, greythr_emp.get("employeeNo"))
        return "created"


def _candidate_has_different_mapping(candidate_name: str, greythr_id: str) -> bool:
    """
    Return True if this Frappe Employee already has a greytHR Employee Mapping
    to a *different* greytHR ID than the one we're trying to match.

    Defends against the rehire-hijack bug (2026-05-25): when greytHR creates a
    new `employeeId` for a re-employed person, the email/employee_number
    fallback matching in _find_frappe_employee would otherwise reuse the
    person's existing Frappe Employee (linked to the OLD greytHR ID),
    overwriting historical employment data. Each greytHR employment should
    have its own Frappe Employee — silently merging them loses the audit trail
    of when the person left and rejoined.

    `ignore_permissions=True` so the Phase 4 `permission_query_conditions`
    filter on Employee can't accidentally hide a candidate's mapping check.
    """
    existing = frappe.get_all(
        "greytHR Employee Mapping",
        filters={"frappe_employee": candidate_name},
        fields=["greythr_employee_id"],
        limit=1,
        ignore_permissions=True,
    )
    if existing and str(existing[0]["greythr_employee_id"]) != str(greythr_id):
        log_error(
            f"pull_employees: greytHR ID={greythr_id} would have hijacked "
            f"Frappe Employee {candidate_name} (already mapped to greytHR ID="
            f"{existing[0]['greythr_employee_id']}). Routing to CREATE path "
            f"so historical record is preserved.",
            "greytHR Rehire Detection",
        )
        return True
    return False


def _find_frappe_employee(mapped: dict, greythr_id: str):
    """
    Find an existing Frappe Employee using the matching priority chain.

    Returns:
      - Frappe Employee document if a unique match is found
      - "DUPLICATE" if multiple Frappe employees match the same email
      - None if no match (new employee should be created) OR the matched
        record is already linked to a different greytHR ID (rehire scenario)

    All `frappe.get_all` calls use `ignore_permissions=True` so the Phase 4
    UX filter on Employee doesn't silently hide candidates from internal
    sync lookups.
    """
    # 1. Existing mapping record — canonical, always trusted
    mapping = frappe.get_all(
        "greytHR Employee Mapping",
        filters={"greythr_employee_id": greythr_id},
        fields=["frappe_employee"],
        limit=1,
        ignore_permissions=True,
    )
    if mapping:
        return frappe.get_doc("Employee", mapping[0]["frappe_employee"])

    # 2. company_email — fallback for backfill, but refuse to hijack rehires
    if email := mapped.get("company_email"):
        matches = frappe.get_all(
            "Employee",
            filters={"company_email": email},
            fields=["name"],
            limit=2,
            ignore_permissions=True,
        )
        if len(matches) > 1:
            log_error(
                f"pull_employees: duplicate company_email {email!r} — skipping both employees",
                "greytHR Duplicate Email",
            )
            return "DUPLICATE"
        if matches:
            candidate = matches[0]["name"]
            if _candidate_has_different_mapping(candidate, greythr_id):
                return None  # caller creates new record for this greytHR ID
            return frappe.get_doc("Employee", candidate)

    # 3. personal_email — same defense; uses the personal_email value from the
    # mapper (Bug #3 fix 2026-05-25: was previously reading company_email here,
    # making the step a duplicate of #2 against the wrong target field).
    if email := mapped.get("personal_email"):
        matches = frappe.get_all(
            "Employee",
            filters={"personal_email": email},
            fields=["name"],
            limit=2,
            ignore_permissions=True,
        )
        if len(matches) > 1:
            log_error(
                f"pull_employees: duplicate personal_email — skipping",
                "greytHR Duplicate Email",
            )
            return "DUPLICATE"
        if matches:
            candidate = matches[0]["name"]
            if _candidate_has_different_mapping(candidate, greythr_id):
                return None
            return frappe.get_doc("Employee", candidate)

    # 4. employee_number — same defense
    if emp_no := mapped.get("employee_number"):
        matches = frappe.get_all(
            "Employee",
            filters={"employee_number": emp_no},
            fields=["name"],
            limit=1,
            ignore_permissions=True,
        )
        if matches:
            candidate = matches[0]["name"]
            if _candidate_has_different_mapping(candidate, greythr_id):
                return None
            return frappe.get_doc("Employee", candidate)

    return None


def _upsert_mapping(frappe_employee: str, greythr_id: str, greythr_no: str = None) -> None:
    """Create or update the greytHR Employee Mapping record."""
    existing = frappe.get_all(
        "greytHR Employee Mapping",
        filters={"frappe_employee": frappe_employee},
        limit=1,
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if existing:
        doc = frappe.get_doc("greytHR Employee Mapping", existing[0]["name"])
        doc.last_synced_at = now
        doc.sync_status = "In Sync"
        doc.last_sync_error = None
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc("greytHR Employee Mapping")
        doc.frappe_employee = frappe_employee
        doc.greythr_employee_id = greythr_id
        doc.greythr_employee_no = greythr_no
        doc.first_synced_at = now
        doc.last_synced_at = now
        doc.sync_status = "In Sync"
        doc.insert(ignore_permissions=True)


# ── sync log helpers ───────────────────────────────────────────────────────────

def _start_sync_log(triggered_by: str, started_at: datetime):
    doc = frappe.new_doc("greytHR Sync Log")
    doc.sync_type = "Pull Employees"
    doc.status = "Started"
    doc.triggered_by = triggered_by
    doc.started_at = started_at.strftime("%Y-%m-%d %H:%M:%S")
    doc.insert(ignore_permissions=True)
    return doc


def _finish_sync_log(sync_log, status: str, counters: dict,
                      errors: list, warnings: list | None = None) -> None:
    sync_log.status = status
    sync_log.completed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sync_log.records_processed = counters["processed"]
    sync_log.records_created = counters["created"]
    sync_log.records_updated = counters["updated"]
    sync_log.records_failed = counters["failed"]
    sync_log.records_skipped = counters["skipped"]

    # error_summary: actual failures first (capped 20), then mapper warnings
    # tagged "WARN" (capped 30). Warnings are non-fatal — they surface
    # greytHR data quality issues HR should fix at the source.
    summary_lines = list(errors[:20])
    if warnings:
        summary_lines.extend(f"WARN {w}" for w in warnings[:30])
    sync_log.error_summary = "\n".join(summary_lines) if summary_lines else None

    sync_log.save(ignore_permissions=True)


def _notify_failure(sync_log) -> None:
    """Send Frappe notification to all System Managers when a sync fails."""
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
