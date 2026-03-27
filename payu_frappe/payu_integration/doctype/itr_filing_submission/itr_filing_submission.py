import frappe
from frappe.model.document import Document
from frappe.utils import get_url
from frappe.utils.data import cint, flt


class ITRFilingSubmission(Document):
    def validate(self):
        """Standard Frappe validation hook."""
        self.sync_payment_amount()
        self.auto_generate_payment_link()

    def before_insert(self):
        """Set default values before insert."""
        if not self.payment_status:
            self.payment_status = "Pending"
        if not self.stage_status:
            self.stage_status = "Lead Generated"
        if not self.assignment_method:
            self.assignment_method = "Auto Assign"
        self.sync_payment_amount()

    def sync_payment_amount(self):
        """Sync payment_amount with service_amount automatically."""
        if self.service_amount:
            # Use Frappe datatype helpers — handles str/float/int safely
            self.payment_amount = cint(flt(self.service_amount))
        else:
            self.payment_amount = 0

    def auto_generate_payment_link(self):
        """Automatically generate payment link if service amount is set and link is missing."""
        if self.service_amount and not self.payment_link and self.email:
            # Generate link
            # Note: During initial insert, self.name is generated before validate
            if self.name and not self.name.startswith("new-itr-filing-submission"):
                self.payment_link = get_url(f"/payu_checkout?request={self.name}")
                self.payment_status = "Link Generated"
                
                # We could send email here, but validate is for validation.
                # However, the user flow implies immediate action.
                # We'll stick to field updates for now to match exactly what was requested.

    def before_save(self):
        # We use validate() instead
        pass
