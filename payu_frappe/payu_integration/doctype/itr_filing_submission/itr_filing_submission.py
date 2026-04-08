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
        """Set default values before insert, and auto-detect New vs Existing Client."""
        if not self.payment_status:
            self.payment_status = "Pending"
        if not self.assignment_method:
            self.assignment_method = "Auto Assign"
        self.sync_payment_amount()

        # --- Auto-detect New Client vs Existing Client based on PAN ---
        self.stage_status = self._detect_client_status()

    def _detect_client_status(self):
        """
        Check if the client's PAN already exists in ITR Filing Submission.
        Returns 'Existing Client' if a prior record is found, else 'New Client'.
        Falls back to 'Lead Generated' if PAN is not provided.
        The field name on the DocType is 'pan_number'.
        """
        pan = (self.pan_number or "").strip().upper()
        if not pan:
            # No PAN provided — cannot determine, use default
            return "Lead Generated"

        existing = frappe.db.exists(
            "ITR Filing Submission",
            {"pan_number": pan}
        )
        return "Existing Client" if existing else "New Client"

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
