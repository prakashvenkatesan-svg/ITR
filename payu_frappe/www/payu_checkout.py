import frappe

def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    request_id = frappe.request.args.get("request")
    
    if not request_id:
        context.error_msg = "Invalid payment link — no request ID found."
        return

    try:
        doc = frappe.get_doc("ITR Filing Submission", request_id)
    except frappe.DoesNotExistError:
        context.error_msg = "Request ID not found in system."
        return
    
    if doc.payment_status == "Success":
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-success"
        frappe.local.flags.redirect_location = "/payment-success"
        raise frappe.Redirect

    # Check if a link already exists. If not, auto-generate it securely.
    link = doc.payment_link
    
    # Critical Fix: Older records might have saved the local `/payu_checkout` URL 
    # to the database. If we redirect to this, we cause an infinite loop!
    if link and "/payu_checkout" in link:
        link = None
        
    if not link:
        # Generate on the fly using our new OAuth API method
        try:
            from payu_frappe.api import generate_payment_link_and_send
            res = generate_payment_link_and_send(request_id)
            if res and isinstance(res, dict) and res.get("payment_link"):
                link = res.get("payment_link")
            else:
                context.error_msg = "Payment link generation failed (Empty response)."
                return
        except Exception as e:
            # Check specifically for permission errors as they are common locally
            context.error_msg = f"Failed to fetch payment link dynamically: {str(e)}"
            return
            
    # Force a true HTTP 302 Redirect at network level (bypasses HTML completely)
    frappe.local.response["type"] = "redirect"
    frappe.local.response["location"] = link
    frappe.local.flags.redirect_location = link
    raise frappe.Redirect
