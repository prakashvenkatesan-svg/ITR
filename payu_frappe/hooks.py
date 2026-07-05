app_name = "payu_frappe"
app_title = "PayU Frappe"
app_publisher = "Aionion Advisory"
app_description = "PayU Payment Gateway + ITR Filing Integration"
app_email = "admin@aionionadvisory.com"
app_license = "MIT"

# -------------------------------------------------------------------------
# Module definition
# -------------------------------------------------------------------------
app_include_css = []
app_include_js = []

# -------------------------------------------------------------------------
# Website routes
# -------------------------------------------------------------------------
website_route_rules = [
    {"from_route": "/payu_checkout", "to_route": "payu_checkout"},
    {"from_route": "/payment-success", "to_route": "payment_success"},
    {"from_route": "/payment-failed", "to_route": "payment_failed"},
]

# -------------------------------------------------------------------------
# DocType JS (client scripts via developer mode)
# -------------------------------------------------------------------------
doctype_js = {
    "ITR Filing Submission": "payu_integration/doctype/itr_filing_submission/itr_filing_submission.js"
}

doctype_list_js = {
    "ITR Filing Submission": "payu_integration/doctype/itr_filing_submission/itr_filing_submission_list.js"
}

# -------------------------------------------------------------------------
# Document Events (Hooks)
# -------------------------------------------------------------------------
doc_events = {
    "ITR Filing Submission": {
        "before_insert": "payu_frappe.api.auto_assign_regional_manager",
        "before_save": "payu_frappe.api.capture_pre_save_stage",
        "on_update": "payu_frappe.api.reassign_to_rm_on_in_progress"
    }
}

# -------------------------------------------------------------------------
# Custom Permissions (Stateless Privacy)
# -------------------------------------------------------------------------
permission_query_conditions = {
    "ITR Filing Submission": "payu_frappe.api.get_permission_query_conditions"
}

has_permission = {
    "ITR Filing Submission": "payu_frappe.api.has_custom_permission"
}

# -------------------------------------------------------------------------
# Scheduled Jobs (Automatic PayU Payment Reconciliation)
# -------------------------------------------------------------------------
scheduler_events = {
    # Runs every 30 minutes — auto-creates Transaction Logs for paid submissions
    "cron": {
        "*/30 * * * *": [
            "payu_frappe.payment_reconcile.sync_all_pending_payments"
        ]
    }
}
