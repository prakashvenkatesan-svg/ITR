import frappe


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    request_id = frappe.request.args.get("request")
    
    if not request_id:
        frappe.throw("Invalid payment link — no request ID found.")

    doc = frappe.get_doc("ITR Filing Submission", request_id)
    
    if doc.payment_status == "Success":
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-success"
        return

    # Check if a link already exists. If not, auto-generate it securely.
    link = doc.payment_link
    if not link:
        # Generate on the fly using our new OAuth API method
        try:
            from payu_frappe.api import generate_payment_link_and_send
            res = generate_payment_link_and_send(request_id)
            if res and isinstance(res, dict) and res.get("payment_link"):
                link = res.get("payment_link")
            else:
                frappe.throw("Payment link generation failed.")
        except Exception as e:
            frappe.throw(f"Failed to fetch payment link dynamically: {str(e)}")
            
    # Redirect immediately to the highly secure PayU Hosted Page
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = link
