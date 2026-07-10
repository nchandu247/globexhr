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

# UX filter — hide Employees with malformed employee_number values from
# autocompletes and list views (NOT a security boundary; direct URL access
# still works). See globex_hr_letters/utils/permissions.py for the rationale.
permission_query_conditions = {
    "Employee": "globex_hr_letters.utils.permissions.employee_query_conditions",
}


# Document event handlers
doc_events = {
    # Employee naming: use employee_number as the Frappe primary key when
    # present. Falls back to default naming series (HR-EMP-####) when empty.
    "Employee": {
        "before_insert": "globex_hr_letters.hooks_handlers.employee.set_name_from_employee_number",
    },
}
