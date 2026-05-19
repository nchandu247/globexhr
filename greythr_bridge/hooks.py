app_name = "greythr_bridge"
app_title = "greytHR Bridge"
app_publisher = "Globex Digital Solutions Pvt Ltd"
app_description = "Integration between Frappe HR and greytHR Cloud"
app_email = "hr@globexdigital.ai"
app_license = "Proprietary"
required_apps = ["frappe/hrms"]  # does not require ERPNext

# Fixtures auto-loaded on install
fixtures = [
    {
        "dt": "DocType",
        "filters": [["module", "=", "greytHR"]],
    }
]

# Scheduled jobs
scheduler_events = {
    "cron": {
        "*/15 * * * *": ["greythr_bridge.tasks.pull_employees.run"],      # Phase 2
        # "0 20 * * *": ["greythr_bridge.tasks.pull_salary_structures.run"],  # Phase 3
        # "0 21 * * *": ["greythr_bridge.tasks.reconcile_drift.run"],          # Phase 5
    }
}

# Document event handlers — wired in Phase 5+
# doc_events = {
#     "Job Offer": {
#         "on_submit": "greythr_bridge.hooks_handlers.job_offer.on_offer_submitted",
#     },
#     "Salary Structure Assignment": {
#         "on_submit": "greythr_bridge.hooks_handlers.salary_assignment.on_submit",
#     },
#     "Employee": {
#         "on_update": "greythr_bridge.hooks_handlers.employee.on_update",
#     },
# }
