# CLAUDE.md — Coding Conventions for greythr_bridge

> Read this file at the start of every Claude Code session. Read `PLAN.md` for full context. Check `CHANGELOG.md` to see what's last been done.

This is a Frappe custom app (Globex Digital Solutions Pvt Ltd) that integrates Frappe HR (running on Frappe Cloud) with greytHR Cloud (HR/Payroll vendor). Frappe HR is the application HR uses; greytHR remains the system of record for employee master, payroll, and statutory data.

---

## Hard rules — never break these

1. **Never modify Frappe HR or Frappe Framework core.** All extensions live in `greythr_bridge`. If a customization seems to need core changes, stop and use a hook/fixture/custom field instead.
2. **All greytHR API calls go through `greythr_bridge.api.client.GreytHRClient`.** Never call `requests.get(...)` to greytHR from anywhere else.
3. **All Zoho Sign API calls go through `greythr_bridge.api.zoho_sign`.** Never call the Zoho Sign REST API directly from tasks, hooks, or webhooks.
4. **All credentials live in the `greytHR Settings` single DocType** with `Password` fields (encrypted at rest). Never hardcode `client_id`, `client_secret`, `zoho_api_key`, `zoho_sign_webhook_secret`, or any secret in source. Never read secrets from `frappe.conf` or environment variables.
5. **All sync operations are idempotent.** Running them twice produces the same result. Use Frappe document name as the idempotency key.
6. **All async work goes through `frappe.enqueue` with the correct queue type.**
   - `queue="short"` — webhook-triggered jobs (must start within seconds)
   - `queue="long"` — bulk sync jobs (pull_employees, pull_salary)
   - `queue="default"` — everything else
   HTTP webhook handlers must return within 5 seconds. Never block a webhook with synchronous work.
7. **All errors go through `frappe.log_error(message, title)`.** Never use `print()` or bare `pass` on exceptions. Log IDs and timestamps only — never log full employee records, candidate PII (name, email, mobile, Aadhaar, PAN), PDFs, tokens, or webhook payloads. This is both hygiene and a DPDP Act compliance requirement.
8. **Custom DocTypes start with `greytHR`** (e.g. `greytHR Settings`, `greytHR Sync Log`, `greytHR Employee Mapping`).
9. **Custom fields on Frappe HR DocTypes start with `custom_`** (e.g. `custom_greythr_employee_id`).
10. **Every function that calls greytHR or Zoho Sign has a unit test.** Use the `responses` library to mock HTTP. Tests must run offline in CI.
11. **Every commit batch updates `CHANGELOG.md`.**
12. **All greytHR HTTP calls are rate-limited to 10 req/sec** via `@rate_limited` in `GreytHRClient._request()`. Never call greytHR in a tight loop outside the client.
13. **`on_status_change` does not exist in Frappe.** To react to an Employee status change, use `on_update` and compare `doc.status` vs `doc.get_doc_before_save().status`. Never register `on_status_change` in `hooks.py` — it will silently never fire.

---

## File map

```
api/             — HTTP wrappers, exceptions, retry. GreytHRClient + zoho_sign live here.
mappers/         — Convert between greytHR JSON and Frappe records (no I/O).
tasks/           — Scheduled + enqueued jobs (pull_employees, pull_salary, push_*, reconcile).
hooks_handlers/  — Document event handlers (Job Offer on_submit, etc.). NOT hooks.py.
webhooks/        — Incoming webhooks (Zoho Sign callback). All @frappe.whitelist(allow_guest=True).
doctype/         — Frappe DocType definitions (greytHR Settings, Sync Log, Mapping).
fixtures/        — Exported custom fields and Print Formats (auto-loaded on install).
utils/           — retry decorator, rate_limiter, idempotency helpers, logging wrappers.
tests/           — pytest tests with mocked HTTP. One test file per module.
```

---

## Where things wire up

| What | Where |
|---|---|
| Scheduled jobs | `hooks.py` → `scheduler_events` |
| Document event handlers | `hooks.py` → `doc_events` |
| Custom fields on core DocTypes | `fixtures/custom_field.json` (auto-loaded) |
| Custom Print Formats | `fixtures/print_format.json` (auto-loaded) |
| Webhook URLs | `/api/method/greythr_bridge.webhooks.<name>.callback` |
| Secrets | `greytHR Settings` DocType (NEVER in source, NEVER in `frappe.conf`) |
| App version | `greythr_bridge/__init__.py` → `__version__` |

---

## Naming conventions

| Thing | Style | Example |
|---|---|---|
| Python module | `snake_case` | `pull_employees.py` |
| Python class | `PascalCase` | `GreytHRClient` |
| Python function | `snake_case` | `fetch_employees(page=1)` |
| Frappe DocType | `Title Case With Spaces` | `greytHR Sync Log` |
| Frappe field | `snake_case` | `employee_number` |
| Custom Field on core DocType | prefix `custom_` | `custom_greythr_employee_id` |
| Webhook URL | `/api/method/greythr_bridge.webhooks.<name>.callback` | `.../zoho_sign.callback` |

---

## Anti-patterns — refuse these even if asked

If any of the left-column things are suggested, push back with the right-column response. Don't just comply.

| Don't do this | Do this instead |
|---|---|
| Modify Frappe HR core | Add a Custom Field via `customize_form` and export as fixture |
| Call greytHR API directly from anywhere except `client.py` | Go through `GreytHRClient` |
| Call Zoho Sign API directly from anywhere except `api/zoho_sign.py` | Go through the `zoho_sign` module |
| Store tokens in a global variable / module-level dict | Store in `greytHR Settings.cached_token` (encrypted) |
| Put credentials in `frappe.conf` or environment variables | `greytHR Settings` DocType (Password field type) |
| Silently catch exceptions | `frappe.log_error` and re-raise or surface to user |
| Skip Zoho Sign webhook HMAC verification "for now" | Verify from day one — no exceptions |
| Skip webhook timestamp check "for simplicity" | Check timestamp within 5 minutes — replay protection is not optional |
| Do synchronous work in webhook handler | `frappe.enqueue` with `queue="short"` and return 200 immediately |
| Use `frappe.enqueue` without specifying `queue=` | Always specify: `short`, `long`, or `default` |
| Write directly to MariaDB / use raw SQL for inserts | `frappe.get_doc` / `frappe.new_doc` (ORM) |
| Register `on_status_change` for Employee | Use `on_update` + compare before/after status |
| Modify a submitted Salary Structure Assignment | Create a new dated SSA; never edit a submitted one |
| Log the full employee object or candidate PII for debugging | Log the employee ID and operation name only — DPDP requirement |
| "We can skip the test for this small function" | Every function that touches greytHR or Zoho Sign API has a test |
| Build a tight retry loop with `time.sleep` for API outages | Use the scheduler, Sync Log, and manual retry buttons |
| Add a JS file when a Server Script or Client Script would do | Prefer Frappe UI-managed scripts; file-based only when needed |

---

## When implementing a new feature

Default checklist for any new task — go through these in order:

1. **Re-read the relevant section of `PLAN.md`** (Section 5 has all phases with detailed tasks)
2. **Check if a DocType field needs to be added.** If yes, add via "Customize Form" UI first, then export as fixture
3. **Write the function signature and docstring first.** No body yet.
4. **Write the test that proves it works** (with mocked HTTP if it touches greytHR or Zoho Sign)
5. **Implement the function** to make the test pass
6. **Verify manually** with the bench-callable command pattern (see Phase 1 spec)
7. **Update `CHANGELOG.md`** with one line describing what changed
8. **Commit** with a message that references the phase and task number (e.g. "Phase 2.5: implement pull_employees task")

---

## Useful bench commands during development

```bash
# Run a quick Python function on the site (great for smoke tests)
bench --site hr-globexdigital execute greythr_bridge.api.client.test_connection

# Run all tests for this app
bench --site hr-globexdigital run-tests --app greythr_bridge

# Run a specific test module
bench --site hr-globexdigital run-tests --app greythr_bridge --module greythr_bridge.tests.test_client

# Migrate (apply patches) after pulling new code
bench --site hr-globexdigital migrate

# Reload a DocType after editing its .json file
bench --site hr-globexdigital reload-doctype "greytHR Settings"

# Export current fixtures (after creating custom fields via UI)
bench --site hr-globexdigital export-fixtures --app greythr_bridge

# Tail logs (useful while debugging)
tail -f sites/hr-globexdigital/logs/*.log
```

---

## Where to look things up

| Question | Where to find the answer |
|---|---|
| What's the next task to work on? | `CHANGELOG.md` (last entry) → `PLAN.md` Section 5 (next phase) |
| What fields does this DocType have? | `PLAN.md` Section 3.1 |
| What's the GreytHRClient supposed to do? | `PLAN.md` Section 5, Phase 1, "Detailed spec" |
| Which greytHR API endpoints do we use? | greytHR docs at https://api-docs.greythr.com |
| How do I add a new letter type? | `PLAN.md` Phase 4 |
| Why are we doing X this way? | `PLAN.md` Section 1 (Context) and Section 2 (Conventions) |
| Is there a Frappe-idiomatic way to do this? | https://docs.frappe.io/framework — search first; ask second |

---

## When in doubt

- **Read `PLAN.md`.** It's the source of truth.
- **If `PLAN.md` doesn't answer it, ask me.** Don't guess.
- **If it's a Frappe-framework question, search https://docs.frappe.io and https://discuss.frappe.io.** The community is active and most answers exist.
- **If suggesting a deviation from these conventions, flag it explicitly** — say "this breaks rule X, here's why I think it's worth it" rather than silently doing it.

---

## Session etiquette

At the start of each session, say:

> I've read PLAN.md and CLAUDE.md. The last CHANGELOG entry is "<entry>". We're currently in Phase <N>. The next task is <X.Y>: <task name>. Ready to proceed when you confirm.

At the end of each session, before stopping:

- Update `CHANGELOG.md`
- Make sure all tests pass
- Commit with a descriptive message referencing phase and task number
- Note in chat what's left unfinished so the next session can pick up cleanly
