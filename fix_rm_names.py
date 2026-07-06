import frappe

def execute():
    frappe.init(site="aionion-itr.m.frappe.cloud")
    frappe.connect()
    
    docs = frappe.get_all("ITR Filing Submission", fields=["name", "regional_manager", "regional_manager_name"])
    fixed = 0
    for doc in docs:
        if not doc.regional_manager:
            continue
        correct_name = frappe.db.get_value("User", doc.regional_manager, "full_name") or doc.regional_manager
        if correct_name != doc.regional_manager_name:
            frappe.db.set_value("ITR Filing Submission", doc.name, "regional_manager_name", correct_name)
            fixed += 1
            print(f"Fixed {doc.name}: {doc.regional_manager_name} -> {correct_name}")
            
    frappe.db.commit()
    print(f"Fixed {fixed} records.")
execute()
