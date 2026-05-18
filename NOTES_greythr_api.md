# greytHR API — Observed Schema Notes

> **Keys only — no values.** Do not paste actual field values (employee names, emails,
> IDs, dates) into this file. This file is safe to commit to the private repo.
> Last verified: 2026-05-18

---

## Auth Contract

| Concern | Value |
|---|---|
| OAuth token endpoint | `https://globex.greythr.com/uas/v1/oauth2/client-token` |
| OAuth host | Tenant host — **different from the data API host** |
| OAuth credential delivery | HTTP Basic auth header (Base64 of `client_id:client_secret`) — **not** POST body params |
| OAuth body | `grant_type=client_credentials` |
| Token TTL | ~45 days (~3,888,000 seconds returned as `expires_in`) — cache aggressively |
| Data API base URL | `https://api.greythr.com` |
| Data auth header | `ACCESS-TOKEN: <raw token>` — **no** "Bearer" prefix |
| Tenant routing header | `x-greythr-domain: globex.greythr.com` — required on every data call |
| Accept header | `application/json` — explicit; omitting it can trigger 403 |
| Silent failure trap | greytHR returns **200 + `text/html`** when auth is rejected silently. Always validate `Content-Type` before parsing the response body. Treat HTML as auth failure and retry once with a fresh token. |
| Response envelope | All list endpoints wrap payload in `{"data": [...]}` |

---

## Confirmed Field Keys Per Endpoint

### GET /employee/v2/employees
```
employeeId, name, firstName, middleName, lastName, email, employeeNo,
dateOfJoin, leavingDate
```
**Notes:**
- `leavingDate` is present on this endpoint — non-null value means the employee has
  separated. Status ("Left") can be inferred here without a separate separation call.
- `email` appears to be personal email based on observed data. Verify whether a
  separate work/official email field exists before implementing Phase 2 matching logic.
- Use `employeeId` (internal greytHR ID) as the primary join key — not `employeeNo`.

### GET /employee/v2/employees/work
```
employeeId, confirmDate, extendedProbationDays, extension, lastPrevEmployment,
lastPromotionDate, noticePeriod, onboardingStatus, originalHireDate, probationExtendedBy
```
**Notes:**
- `onboardingStatus` values not yet observed — check what strings greytHR uses
  before Phase 7 design.
- `confirmDate` and `originalHireDate` feed the Confirmation Letter template (Phase 4).

### GET /employee/v2/employees/separation
```
employeeId, exitInterviewDate, finalSettlementDate, fitToBeRehired, leavingDate,
leavingReason, leftOrg, retirementDate, submissionDate, submittedResignation,
tentativeLeavingDate, tentativeRelieveDate
```
**Notes:**
- `fitToBeRehired` is a boolean — HR decision needed on whether to surface this in
  Frappe HR (see Phase 2 pre-tasks in PLAN.md).
- `leavingReason`, `exitInterviewDate`, `finalSettlementDate` feed Experience Letter
  and Relieving Letter templates (Phase 4/6).

### GET /payroll/v2/salary/repository
```
children, description, id, name, parent, taxable, type
```
**Notes:**
- Structure: **tree** — 3 top-level nodes, each with nested `children` arrays.
- Phase 3 mapper must do a recursive tree-walk to flatten before creating Frappe records.
- Field mapping to Frappe Salary Component:
  - `name` → `salary_component`
  - `description` → `description`
  - `taxable` → `is_tax_applicable`
  - `type` → `component_type` (map greytHR strings to Frappe's Earning/Deduction values)
  - `parent` / `children` → tree structure (flatten; preserve grouping via Frappe formula/condition fields)

---

## Pending Verification (Required Before Phase 6)

These **write** endpoints have **not** been verified with the correct auth pattern.
Test with `ACCESS-TOKEN` header + `x-greythr-domain` header (not `Authorization: Bearer`):

| Endpoint | Purpose | Status |
|---|---|---|
| `POST /employee/v2/employees` | Create new employee (push new joiner) | ⬜ Unverified |
| `POST /employee/v2/employee-docs/{id}/{category}` | Upload signed PDF | ⬜ Unverified |
| `POST /payroll/v2/salary/revision/employees/{id}` | Push salary revision | ⬜ Unverified |

Also confirm these are available on the **Essential plan** (not Enterprise-only).

---

## Open Questions

| Question | Status |
|---|---|
| Does `/employee/v2/employees` support `updated_after` filter? | ⬜ Unverified |
| Is `email` personal or work email? Is there a separate work email field? | ⬜ Unverified |
| What string values does `onboardingStatus` take? | ⬜ Unverified |
| Are write endpoints available on Essential plan? | ⬜ Unverified |
| Does the separation endpoint return records for all time or only recent? | ⬜ Unverified |
