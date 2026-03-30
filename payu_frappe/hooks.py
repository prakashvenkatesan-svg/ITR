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
    "ITR Filing Submission": "payu_frappe/payu_integration/doctype/itr_filing_submission/itr_filing_submission.js"
}
doctype_list_js = {
    "ITR Filing Submission": "payu_frappe/payu_integration/doctype/itr_filing_submission/itr_filing_submission_list.js"
}
