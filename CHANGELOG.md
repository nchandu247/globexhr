# Changelog

All notable changes to `greythr_bridge` are documented here.
Format: `## [Unreleased]` until first production deploy, then version + date.

---

## [Unreleased]

### Phase 0 — Scaffolding

- ✅ **Task 0.5:** API user `globexdigital` created in greytHR Admin with the following
  roles: Salary API, Employee API, User API, Employee API read access,
  Employee Document API access.

- ✅ **Task 0.6:** greytHR OAuth and data endpoints verified via PowerShell.
  Confirmed working auth pattern:
  - OAuth endpoint: `https://globex.greythr.com/uas/v1/oauth2/client-token`
    (tenant host — different from the data API host `api.greythr.com`)
  - OAuth credential delivery: HTTP Basic auth header (not body params)
  - Data calls: `ACCESS-TOKEN: <token>` header (no Bearer prefix)
  - Tenant routing: `x-greythr-domain: globex.greythr.com` required on every data call
  - Token TTL: ~45 days
  - Silent failure trap: 200 + `text/html` = auth rejected; must validate Content-Type
  - Confirmed endpoints (JSON + `{"data": [...]}` wrapper):
    - `GET /employee/v2/employees`
    - `GET /employee/v2/employees/work`
    - `GET /employee/v2/employees/separation`
    - `GET /payroll/v2/salary/repository`
  - Observed field keys captured in `NOTES_greythr_api.md`

- ⬜ **Task 0.0 (partial):** Write endpoint availability (POST employee, POST docs,
  POST salary revision) not yet verified with the correct auth pattern.
  Required before Phase 6 begins.

- ✅ **Task 0.1:** Frappe Cloud site created at `globex.m.frappe.cloud` (AWS Mumbai region).
- ✅ **Task 0.2:** Frappe HR (`hrms`) installed at site creation.
- ✅ **Task 0.7:** Custom domain `hr.globexdigital.ai` configured in Frappe Cloud; SSL provisioned.
- ⬜ **Task 0.3:** Setup wizard — company, country, currency, fiscal year. Run next.
- ⬜ **Task 0.4:** Timezone `Asia/Kolkata`, date format `dd-mm-yyyy`. Run after 0.3.
- ✅ **Task 0.9:** GitHub repo created at `https://github.com/nchandu247/globexhr`.
  Scaffold committed: pyproject.toml, hooks.py, modules.txt, all package stubs,
  .gitignore, .github/workflows/ci.yml, README.md.
- ✅ **Task 0.10 (partial):** Frappe Cloud V16 bench "GlobexHR" deployed successfully.
  Workaround applied: official `frappe/erpnext` (version-16) must be present in the bench
  alongside `frappe/hrms` due to a Frappe Cloud account-level resolver bug that
  auto-adds a broken ERPNext fork (`vorasmit/erpnext`) otherwise.
  ERPNext will NOT be installed on the site — bench only.
  Raise support ticket with Frappe Cloud to clean up the broken fork registrations.
- ✅ **Task 0.10 (complete):** Bench GlobexHR deployed successfully with all 6 apps:
  frappe v16.18.2, Builder v1.24.6, Insights v3.9.9, ERPNext (frappe/erpnext) 799d6d1,
  HR & Payroll v16.7.0, greytHR Bridge cc0155a. Site created on AWS Mumbai, ₹820/mo plan.
- ⬜ **Task 0.3:** Frappe HR setup wizard (company, country, currency, fiscal year). Next.
- ⬜ **Task 0.4:** Timezone Asia/Kolkata, date format dd-mm-yyyy. After 0.3.
- ⬜ **Task 0.7:** Point hr.globexdigital.ai to new site. Pending.
- ⬜ **Task 0.8:** HR team invites. Pending.
