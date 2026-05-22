app_name = "greythr_bridge"
app_title = "greytHR Bridge"
app_publisher = "Globex Digital Solutions Pvt Ltd"
app_description = "Integration between Frappe HR and greytHR Cloud"
app_email = "hr@globexdigital.ai"
app_license = "Proprietary"
required_apps = ["frappe/hrms"]  # does not require ERPNext

# Fixtures auto-loaded on install / migrate
fixtures = [
    {
        "dt": "DocType",
        "filters": [["module", "=", "greytHR"]],
    },
    {
        "dt": "Custom Field",
        "filters": [
            ["dt", "in", ["Job Offer", "Employee", "Salary Structure Assignment",
                          "Employee Separation"]],
            ["fieldname", "like", "custom_%"],
        ],
    },
    # Phase B — Client Scripts for Employee form buttons (Promotion + Service Cert)
    {
        "dt": "Client Script",
        "filters": [["module", "=", "greytHR"]],
    },
]

# Scheduled jobs
scheduler_events = {
    "cron": {
        "*/15 * * * *": ["greythr_bridge.tasks.pull_employees.run"],      # Phase 2
        "0 20 * * *":   ["greythr_bridge.tasks.pull_salary_structures.run"],  # Phase 3
        "0 21 * * *":   ["greythr_bridge.tasks.stalled_signings.run"],         # Phase 5
        # "0 22 * * *": ["greythr_bridge.tasks.reconcile_drift.run"],          # Phase 5
    }
}

# Document event handlers
doc_events = {
    "Job Offer": {
        "on_submit": "greythr_bridge.hooks_handlers.job_offer.on_offer_submitted",
    },
    # Phase B — auto-trigger letters on source-doc submit
    "Salary Structure Assignment": {
        "on_submit": "greythr_bridge.hooks_handlers.salary_structure_assignment.on_ssa_submitted",
    },
    "Employee Separation": {
        "on_submit": "greythr_bridge.hooks_handlers.employee_separation.on_separation_submitted",
    },
    # Promotion + Service Certificate are MANUAL buttons (Client Scripts in
    # fixtures/client_script.json), not auto-triggered — no doc_event needed.
}
