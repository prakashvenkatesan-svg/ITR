import frappe


def get_context(context):
    context.no_cache = 1
    context.show_sidebar = False
    request_id = frappe.request.args.get("request")
    if not request_id:
        frappe.throw("Invalid payment link — no request ID found.")
    context.request_id = request_id
