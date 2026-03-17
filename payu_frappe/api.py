import frappe
import json as _json
from frappe.utils import get_url
from payu_frappe.utils import get_payu_settings, generate_payu_hash, verify_payu_hash


# ---------------------------------------------------------------------------
# ITR Filing Submission (called from React website form)
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def submit_itr_details():
    """
    Receives ITR filing form data from the React website and creates a new
    ITR Filing Submission document in Frappe.
    """
    try:
        data = {}

        if frappe.request.method == "POST":
            # Priority 1: form-encoded body with 'data' key (URLSearchParams from React)
            form_data_str = frappe.form_dict.get("data")
            if form_data_str:
                try:
                    if isinstance(form_data_str, str):
                        data = _json.loads(form_data_str)
                except Exception:
                    pass

            # Priority 2: raw JSON body
            if not data:
                try:
                    raw_bytes = frappe.request.get_data(as_text=True)
                    if raw_bytes and (raw_bytes.startswith("{") or raw_bytes.startswith("[")):
                        data = _json.loads(raw_bytes)
                except Exception:
                    pass

        # Priority 3: fallback to full form_dict
        if not data:
            data = frappe.form_dict

        frappe.log_error(title="Debug ITR Data", message=frappe.as_json(data))

        doc = frappe.new_doc("ITR Filing Submission")

        # Workflow defaults
        doc.assignment_method = "Auto Assign"
        doc.stage_status = "Lead Generated"

        # --- Section 1: Basic Info ---
        doc.interested_in_services = data.get("interestedInService") or data.get("interestedInServices")
        doc.full_name = (
            data.get("fullName") or data.get("full_name") or data.get("name")
        )
        doc.email = data.get("email")

        ty = data.get("taxYear") or "2025-26"
        if ty and "AY" not in ty:
            ty = f"AY {ty}"
        doc.tax_year = ty
        doc.annual_income = data.get("annualIncome")

        # --- Mobile ---
        doc.mobile_number = data.get("mobileNumber") or data.get("mobile")
        doc.country_code = data.get("country_code") or data.get("countryCode")
        doc.alt_whatsapp_number = (
            data.get("altMobileNumber") or data.get("alt_mobile") or data.get("altWhatsappNumber")
        )

        # --- Section 2: ID Details ---
        doc.pan_number = data.get("pan_number") or data.get("panNumber") or data.get("pan")
        doc.aadhaar_number = data.get("aadhaar") or data.get("aadhaarNumber")

        acc_type = data.get("account_type") or data.get("accountType")
        if acc_type:
            acc_type_lower = acc_type.lower()
            if acc_type_lower == "huf":
                doc.account_type = "HUF"
            elif acc_type_lower == "individual":
                doc.account_type = "Individual"
            else:
                doc.account_type = acc_type.title()

        # --- Section 3: Portal Access ---
        doc.previously_filed_with_aionion = (
            data.get("previouslyFiledWithAionion") or data.get("previouslyFiled")
        )
        doc.registered_on_it_portal = (
            data.get("registeredOnIncomeTax") or data.get("registeredOnPortal")
        )
        doc.willing_to_share_password = (
            data.get("sharePassword") or data.get("willingToSharePassword")
        )
        doc.it_portal_password = data.get("itPassword") or data.get("portalPassword")

        # --- Section 4: Personal Details ---
        doc.name_as_per_pan = data.get("pan_name") or data.get("nameAsPerPan")
        doc.father_name = data.get("father_name") or data.get("fatherName")
        doc.gender = data.get("gender")
        doc.dob = data.get("dob")
        doc.name_as_per_aadhaar = data.get("aadhaar_name") or data.get("nameAsPerAadhaar")
        doc.communication_address = data.get("comm_address") or data.get("communicationAddress")
        doc.permanent_address = data.get("perm_address") or data.get("permanentAddress")

        # --- Section 5: Residency & Salary ---
        doc.is_indian_resident = (
            data.get("is_resident") or data.get("isIndianResident") or "No"
        ).capitalize()
        doc.has_salary_income = (
            data.get("has_salary") or data.get("hasSalaryIncome") or "No"
        ).capitalize()
        doc.has_form_16 = (
            data.get("form16_available") or data.get("has_form16") or data.get("hasForm16") or "No"
        ).capitalize()

        # --- Section 6: Property Income ---
        doc.has_rental_income = (
            data.get("hasRentedHome") or data.get("hasRentalIncome") or "No"
        ).capitalize()
        doc.total_annual_rent = data.get("annualRent")
        doc.has_active_housing_loan = (data.get("housingLoan") or "No").capitalize()

        usage = data.get("loanUsage")
        if usage:
            doc.house_utilization = usage.capitalize()

        # --- Section 7: Business & Investments ---
        doc.has_business_income = (
            data.get("businessIncome") or data.get("hasBusinessIncome") or "No"
        ).capitalize()
        doc.business_nature = data.get("businessNature")
        doc.gstin_available = (
            data.get("gstAvailable") or data.get("gstinAvailable") or "No"
        ).capitalize()

        cg_types = data.get("capitalGains") or data.get("capitalGainsTypes", [])
        if isinstance(cg_types, list) and len(cg_types) > 0:
            doc.has_capital_gains = "Yes"
            doc.capital_gains_types = ", ".join(cg_types)
        else:
            doc.has_capital_gains = "No"

        os_types = data.get("otherIncome") or data.get("otherSourcesTypes", [])
        if isinstance(os_types, list) and len(os_types) > 0:
            doc.has_other_sources = "Yes"
            doc.other_source_types = ", ".join(os_types)
        else:
            doc.has_other_sources = "No"

        # --- Section 8: Assets & Compliance ---
        doc.has_foreign_assets_income = (
            data.get("foreignAssets") or data.get("hasForeignAssets") or "No"
        ).capitalize()
        doc.other_demat_account = (
            data.get("otherDemat") or data.get("hasOtherDemat") or "No"
        ).capitalize()

        cash_val = data.get("cashDeposit") or data.get("cashDepositedRange")
        if cash_val == "<10":
            doc.cash_deposited_range = "Less than 10 Lakhs"
        elif cash_val == ">10":
            doc.cash_deposited_range = "More than 10 Lakhs"
        elif cash_val == "na":
            doc.cash_deposited_range = "Not Applicable"
        else:
            doc.cash_deposited_range = cash_val

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "success": True,
            "message": "ITR details submitted successfully",
            "doc_name": doc.name,
            "formId": doc.name,
        }

    except Exception as e:
        frappe.log_error(title="ITR Submission Error", message=frappe.get_traceback())
        return {"success": False, "message": str(e)}


@frappe.whitelist(allow_guest=True)
def submit_client_requirements():
    """Alias kept for backward compatibility with older React code."""
    return submit_itr_details()


# ---------------------------------------------------------------------------
# PayU Payment Flow
# ---------------------------------------------------------------------------

@frappe.whitelist()
def generate_payment_link_and_send(request_id):
    """
    Called from ITR Filing Submission form button.
    Generates a PayU checkout link and e-mails it to the client.
    """
    doc = frappe.get_doc("ITR Filing Submission", request_id)

    if not doc.service_amount or doc.service_amount == "":
        frappe.throw("Please select a valid Service Amount first.")

    if not doc.email:
        frappe.throw("Email Address is required to send the payment link.")

    doc.payment_amount = int(doc.service_amount)
    payment_link = get_url(f"/payu_checkout?request={doc.name}")

    doc.payment_link = payment_link
    doc.payment_status = "Link Generated"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    try:
        frappe.sendmail(
            recipients=[doc.email],
            subject=f"ITR Filing Payment Link - {doc.name}",
            message=f"""
                <p>Dear {doc.full_name},</p>
                <p>Please click the link below to complete your payment of <b>₹{doc.service_amount}</b>:</p>
                <p><a href="{payment_link}" style="background:#007bff;color:white;padding:10px 20px;
                   text-decoration:none;border-radius:5px;">Pay Now</a></p>
                <p>Or copy this link: {payment_link}</p>
                <br/>
                <p>Thank you,<br/>Aionion Advisory Team</p>
            """,
        )
    except Exception:
        frappe.log_error("Email sending failed", "PayU Email Error")

    return {"payment_link": payment_link, "status": "Link Generated"}


@frappe.whitelist(allow_guest=True)
def get_checkout_details(request_id):
    """
    Called from the payu_checkout web page JS.
    Returns all PayU form params including the secure hash.
    """
    doc = frappe.get_doc("ITR Filing Submission", request_id)
    settings = get_payu_settings()

    txnid = f"ITR-{doc.name}-{frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')}"
    amount = str(doc.service_amount or 0)

    params = {
        "key": settings["key"],
        "txnid": txnid,
        "amount": amount,
        "productinfo": f"ITR Filing Services - {doc.name}",
        "firstname": doc.full_name,
        "email": doc.email,
        "phone": doc.mobile_number or "",
        "surl": get_url("/api/method/payu_frappe.api.handle_callback"),
        "furl": get_url("/api/method/payu_frappe.api.handle_callback"),
        "service_provider": "payu_paisa",
        "udf1": doc.name,
        "udf2": "",
        "udf3": "",
        "udf4": "",
        "udf5": "",
    }

    params["hash"] = generate_payu_hash(params, settings["salt"])

    return {
        "params": params,
        "url": (
            "https://test.payu.in/_payment"
            if settings["is_sandbox"]
            else "https://secure.payu.in/_payment"
        ),
    }


@frappe.whitelist(allow_guest=True)
def handle_callback():
    """
    PayU posts payment result here (both success & failure).
    Verifies hash, logs transaction, updates ITR Filing Submission.
    """
    data = frappe.form_dict
    settings = get_payu_settings()

    if not verify_payu_hash(data, settings["salt"]):
        frappe.log_error("Invalid PayU Hash received", "PayU Callback Security")
        frappe.respond_as_web_page(
            "Payment Error", "Security check failed. Please contact support."
        )
        return

    txnid = data.get("txnid", "")
    request_ref = data.get("udf1", "")
    payment_status = "Success" if data.get("status") == "success" else "Failed"

    try:
        tx_log = frappe.get_doc(
            {
                "doctype": "PayU Transaction Log",
                "transaction_id": txnid,
                "client_request_ref": request_ref,
                "client_name": data.get("firstname", ""),
                "client_mobile": data.get("phone", ""),
                "client_email": data.get("email", ""),
                "amount": data.get("amount"),
                "status": payment_status,
                "payment_method": data.get("mode", ""),
                "upi_id": data.get("bank_ref_num", data.get("mihpayid", "")),
                "response_data": frappe.as_json(dict(data)),
                "payment_date": frappe.utils.now_datetime(),
            }
        )
        tx_log.insert(ignore_permissions=True)

        if request_ref and frappe.db.exists("ITR Filing Submission", request_ref):
            req_doc = frappe.get_doc("ITR Filing Submission", request_ref)
            req_doc.payment_status = payment_status
            req_doc.save(ignore_permissions=True)

        frappe.db.commit()
    except Exception as e:
        frappe.log_error(str(e), "PayU Callback Error")

    if data.get("status") == "success":
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-success"
    else:
        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-failed"
