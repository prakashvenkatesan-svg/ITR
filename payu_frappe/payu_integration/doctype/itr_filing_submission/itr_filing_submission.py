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
        Determine if this is a New or Existing Client based on PAN.

        Checks TWO sources:
        1. Customer DocType (ERPNext) — where Customer Name = PAN (e.g., 'ABLHS9005F')
        2. ITR Filing Submission DocType — prior year/repeated submissions

        Returns:
            'Existing Client' — if PAN found in Customer or prior ITR submission
            'New Client'      — if PAN is not found anywhere
            'Lead Generated'  — fallback if PAN field is empty
        """
        pan = (self.pan_number or "").strip().upper()
        if not pan:
            return "Lead Generated"

        # Check 1: ERPNext Customer DocType — Customer Name = PAN number (e.g. 'ABLHS9005F')
        existing_customer = frappe.db.exists(
            "Customer",
            {"customer_name": pan}
        )
        if existing_customer:
            return "Existing Client"

        # Check 2: Prior ITR Filing Submission with same PAN
        existing_itr = frappe.db.exists(
            "ITR Filing Submission",
            {"pan_number": pan}
        )
        if existing_itr:
            return "Existing Client"

        return "New Client"

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
