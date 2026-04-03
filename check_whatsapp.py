import frappe

def check_logs():
    print("--- Check Picky Assist Message Logs ---")
    messages = frappe.get_all("Picky Assist Message", 
        fields=["name", "mobile_number", "status", "message_type", "creation"], 
        limit=5, 
        order_by="creation desc")
    for m in messages:
        print(f"Name: {m.name}, Mobile: {m.mobile_number}, Status: {m.status}, Type: {m.message_type}, Created: {m.creation}")

    print("\n--- Check Error Logs for Picky Assist ---")
    errors = frappe.get_all("Error Log", 
        filters={"title": ["like", "%Picky Assist%"]},
        fields=["name", "title", "message", "creation"],
        limit=5,
        order_by="creation desc")
    for e in errors:
        print(f"Name: {e.name}, Title: {e.title}, Created: {e.creation}")
        # print(f"Message: {e.message[:500]}...")

check_logs()
