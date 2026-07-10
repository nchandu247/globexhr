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
    # NOTE: Workspace is NOT shipped as a fixture in v16. Public app-owned
    # Workspaces live in greythr/workspace/<scrubbed-name>/<scrubbed-name>.json
    # (the per-module-folder convention used by Frappe HR / ERPNext). Shipping
    # via fixtures causes Frappe's "Removing orphan Workspaces" step to delete
    # the record at the end of every migrate.
]

# Scheduled jobs
scheduler_events = {
    "cron": {
        "0 21 * * *": ["greythr_bridge.tasks.stalled_signings.run"],
    }
}

# UX filter — hide Employees with malformed employee_number values from
# autocompletes and list views (NOT a security boundary; direct URL access
# still works). Covers the 2 invalid_pattern records that the GDS#### rename
# skips. See greythr_bridge/utils/permissions.py for the rationale.
permission_query_conditions = {
    "Employee": "greythr_bridge.utils.permissions.employee_query_conditions",
}


# Document event handlers
doc_events = {
    # Employee naming: use employee_number as the Frappe primary key when
    # present. Falls back to default naming series (HR-EMP-####) when empty.
    "Employee": {
        "before_insert": "greythr_bridge.hooks_handlers.employee.set_name_from_greythr_id",
    },
}
