# Employee Data Integrity Plan — Frappe HR ↔ greytHR

**Status:** Approved 2026-05-23
**Driver:** Discovered while investigating workspace cards — Frappe `HR-EMP-####` IDs don't match greytHR `GDS####`, and HR-EMP-00684 opens with all fields blank.

---

## 1. Problems

| # | Problem | Evidence |
|---|---|---|
| 1 | **Ghost records** in Frappe HR | HR-EMP-00684 has blank `first_name`, `last_name`, `email`, `date_of_joining`. Naming counter at 684 but only 332 records exist (352 deleted historically). |
| 2 | **ID display mismatch** | Frappe primary key is `HR-EMP-####` (Frappe HR default series). greytHR primary key is `GDS####`. No visible cross-reference. HR can't correlate the two systems. |
| 3 | **48 employees missing** from Frappe | greytHR has ~380 employees (`GDS0380` latest); Frappe has 332. 48-employee gap. |

## 2. Hard constraints

- ❌ **No deletion** of any Employee or `greytHR Employee Mapping` record — production payroll system, child docs (salary slips, leaves, attendance) may exist, DPDP 7-year retention rule (PLAN.md §9.3a)
- ❌ **No renames** of Employee primary keys — `frappe.rename_doc` is atomic but mass PK changes risk payroll-linked child records
- ❌ **No `status = "Left"`** on ghosts — triggers Frappe HR exit-interview / F&F workflows
- ❌ **No bulk SQL UPDATE/DELETE** — bypasses ORM safeguards
- ✅ **greytHR is read-only** from this work — current sync is one-way (greytHR → Frappe). Phase 6 of PLAN.md will add limited push later as a separate epic.

Memory rule saved at `~/.claude/projects/d--ai-globexhr/memory/never_delete_employee_records.md`.

## 3. Sync behaviour (source-traced)

One-way: **greytHR → Frappe only**. greytHR row is never modified by anything in this codebase today.

For each Frappe Employee field on update:

| greytHR value | Frappe behaviour |
|---|---|
| Real value (e.g., `firstName: "John"`) | **Overwrites** Frappe with greytHR's value. Frappe edits to that field are lost on next sync. |
| Null / empty / missing | **Preserves** Frappe value (mapper omits null fields per [employee_mapper.py:33-37](../../greythr_bridge/mappers/employee_mapper.py#L33-L37)) |
| Field not in greytHR schema (`custom_*`, `personal_email`) | **Preserves** Frappe value |

Implication for **Phase 2 healing**: HR fixes ghost data in greytHR → next sync auto-populates Frappe via `update existing` path → ghost becomes real record. greytHR is the system of record and stays safe.

## 4. The 6 phases

| Phase | What | Risk | Output |
|---|---|---|---|
| **1 — Read-only audit** | New `@frappe.whitelist()` method `list_ghost_employees()` returns full report: ghosts + mapped-clean + missing-from-Frappe records | Zero (no writes) | CSV/table for HR review; defines scope |
| **2 — Heal at source** | HR opens each ghost's record in greytHR portal, fills missing data; next 15-min sync auto-populates Frappe | Zero in Frappe; HR effort in greytHR | Ghost records become real, audit trail preserved |
| **3 — Prevent new ghosts** | Add guard in `_sync_one`: `if not mapped.get("first_name"): return "skipped"` — logged to `greytHR Sync Log.records_skipped` | Low (code only, existing data untouched) | No new ghosts created going forward |
| **4 — UI display fix** | **4a:** add `employee_number` column to Employee list (List View Settings fixture); **4b:** customize Employee Link autocomplete to search `employee_number` (Client Script); **4c:** filter autocompletes to hide blank-name ghosts | Zero (pure JS / config) | HR sees `GDS####` everywhere; ghosts hidden from pickers but data preserved |
| **5 — Data Quality dashboard** | New workspace cards: ghost count, last sync time, missing-from-greytHR count, plus an HR "Operational note" card explaining where to edit what data | Zero (read-only widgets) | HR has ongoing visibility |
| **6 — Missing-48 investigation** | Read-only query greytHR API, diff against `greytHR Employee Mapping`; report which greytHR `employeeIds` aren't in Frappe and WHY | Zero (read-only API) | Action list for the 48 |

## 5. Order of operations

```
1. Phase 1 (audit)               ←─── first; defines scope
2. Phase 4a + 4b (UI display)    ←─── parallel; quick visible win
3. HR reviews audit + starts
   Phase 2 (greytHR fixes)        ←─── slowest; HR-driven, ongoing
4. Phase 3 (code prevention)     ←─── once Phase 2 reduces ghost count
5. Phase 4c (filter UI)          ←─── ships with Phase 3
6. Phase 5 (dashboard)            ←─── follow-up
7. Phase 6 (missing-48)          ←─── follow-up, independent
```

## 6. Operational changes (HR-facing)

- Edits to greytHR-managed fields (`firstName`, `lastName`, `email`, `dateOfJoin`, `employeeNo`, leaving date) **must be done in the greytHR portal**, not in Frappe. Sync overwrites Frappe within 15 minutes.
- Frappe-only fields (`custom_*`, `personal_email`, `address`, etc.) are safe to edit in Frappe — sync never touches them.
- The 332 vs 380 number gap is expected to shrink as Phase 2 + 6 progress. Baseline tracked in Phase 5 dashboard.

## 7. Off-table

| Won't do | Why |
|---|---|
| `frappe.delete_doc("Employee", ...)` | Hard constraint |
| `frappe.delete_doc("greytHR Employee Mapping", ...)` | Unlinks mapping; would create new duplicate on next sync |
| `frappe.rename_doc("Employee", ...)` | Mass PK change too risky for payroll-linked child docs |
| `status = "Left"` on ghosts | Triggers Frappe HR exit workflows |
| `frappe.db.sql("UPDATE/DELETE ...")` | Bypasses safeguards |
| Push corrections from Frappe → greytHR | Out of scope; Phase 6 of PLAN.md, separate epic |

## 8. Tests (all offline)

- Phase 1: audit endpoint returns list, asserts zero DB writes
- Phase 3: synthetic greytHR record with empty `firstName` → `records_skipped` increments, no `frappe.new_doc` call
- Phase 4: fixture JSON parses; Client Script JS syntax valid
- Phase 5: dashboard queries are SELECT-only
- Phase 6: greytHR API mocked; diff logic asserted against fixed sample

## 9. Reversibility

100%. Every change is `git revert`-able:
- Audit endpoint: delete the method
- Code prevention: remove the guard clause
- UI fixtures: delete the fixture files, run `bench migrate`
- Dashboard: delete the fixture cards

No data ever destroyed = no data ever needs restoration.

## 10. Confidence

| Area | Level | Reasoning |
|---|---|---|
| Diagnosis of ghost root cause | High | Code-traced to mapper + pull_employees, confirmed by HR-EMP-00684 screenshot |
| Phase 2 healing semantics | High | Source-traced sync behaviour matches "preserve null, overwrite real" pattern |
| Zero-risk to greytHR | Very high | Grep confirms no POST/PATCH/PUT to greytHR write endpoints anywhere in this work |
| UI mitigation effectiveness | High | List View Settings + Client Script + autocomplete filters are standard Frappe patterns |
| Missing-48 root cause | Medium | Won't know until Phase 6; likely sync errors or new hires since last successful pull |
