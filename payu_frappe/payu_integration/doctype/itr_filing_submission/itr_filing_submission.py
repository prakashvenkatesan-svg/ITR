import frappe
from frappe.model.document import Document


class ITRFilingSubmission(Document):
    def before_insert(self):
        """Set default values before insert."""
        if not self.payment_status:
            self.payment_status = "Pending"
        if not self.stage_status:
            self.stage_status = "Lead Generated"
        if not self.assignment_method:
            self.assignment_method = "Auto Assign"
