app_name = "globex_hr_letters"
app_title = "Globex HR Letters"
app_publisher = "Globex Digital Solutions Pvt Ltd"
app_description = "HR letters generation application for Frappe HR"
app_email = "hr@globexdigital.ai"
app_license = "Proprietary"
required_apps = ["frappe/hrms"]  # does not require ERPNext

# Fixtures auto-loaded on install / migrate
fixtures = [
    # Shipped Letter Type catalog (prebuilt professional library)
    {
        "dt": "Letter Type",
    },
    # Client Scripts for "Generate Letter" buttons on Employee / Job Applicant
    {
        "dt": "Client Script",
        "filters": [["module", "=", "HR Letters"]],
    },
    # NOTE: Workspace is NOT shipped as a fixture in v16. Public app-owned
    # Workspaces live in hr_letters/workspace/<scrubbed-name>/<scrubbed-name>.json
    # (the per-module-folder convention used by Frappe HR / ERPNext). Shipping
    # via fixtures causes Frappe's "Removing orphan Workspaces" step to delete
    # the record at the end of every migrate.
]

# Scheduled jobs
scheduler_events = {
    "cron": {
        # Daily nudge for HR Letters stuck in "Sent for Signature"
        "0 21 * * *": ["globex_hr_letters.tasks.stalled_signings.run"],
    }
}

# Document event handlers
doc_events = {
    # greytHR Employee ID (employee_number): malformed values are a hard
    # save error (GDS + 3-6 digits); records keep the internal HR-EMP-####
    # name — decisions B3/B4, 2026-07-13. before_insert only defaults the
    # mandatory holiday_list.
    "Employee": {
        "before_insert": "globex_hr_letters.hooks_handlers.employee.apply_employee_defaults",
        "validate": "globex_hr_letters.hooks_handlers.employee.validate_employee_number",
    },
}
