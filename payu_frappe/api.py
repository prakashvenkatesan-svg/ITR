import frappe
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
    frappe.response["headers"] = {
        "Access-Control-Allow-Origin": "https://aionionadvisory.com",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    }
    
    try:
        data = {}

        if frappe.request.method == "POST":
            # Priority 1: form-encoded body with 'data' key (URLSearchParams from React)
            form_data_str = frappe.form_dict.get("data")
            if form_data_str:
                try:
                    parsed = frappe.parse_json(form_data_str)
                    if isinstance(parsed, dict):
                        data = parsed
                except Exception:
                    pass

            # Priority 2: raw JSON body
            if not data:
                try:
                    raw_bytes = frappe.request.get_data(as_text=True)
                    if raw_bytes and (raw_bytes.startswith("{") or raw_bytes.startswith("[")):
                        data = frappe.parse_json(raw_bytes)
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
        doc.email = (
            data.get("email") or data.get("email_id") or 
            data.get("emailId") or data.get("Email")
        )

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
            data.get("previouslyFiledWithAionion") or data.get("previouslyFiled") or "No"
        ).capitalize()
        doc.registered_on_it_portal = (
            data.get("registeredOnIncomeTax") or data.get("registeredOnPortal") or "No"
        ).capitalize()
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

        # --- Attachments are now handled after doc insertion using actual File uploads ---


        doc.service_amount = data.get("serviceAmount") or data.get("service_amount")

        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)

        # --- Process Physical File Attachments ---
        files_attached = []
        if hasattr(frappe.request, "files") and frappe.request.files:
            from frappe.utils.file_manager import save_file
            
            file_mapping = {
                "bank_details_attachment": "bank_details_attachment",
                "form_16_attachment": "form_16_attachment",
                "demat_statement_attachment": "demat_statement_attachment"
            }
            
            for fieldname, request_key in file_mapping.items():
                if request_key in frappe.request.files:
                    try:
                        file_obj = frappe.request.files.get(request_key)
                        file_content = file_obj.read()
                        
                        if file_content:
                            saved_file = save_file(
                                fname=file_obj.filename,
                                content=file_content,
                                dt="ITR Filing Submission",
                                dn=doc.name,
                                folder="Home/Attachments",
                                is_private=1,
                                df=fieldname
                            )
                            # Explicitly update the document field with the new file URL
                            doc.db_set(fieldname, saved_file.file_url)
                            files_attached.append(fieldname)
                    except Exception as fe:
                        frappe.log_error(f"Attachment failed for {fieldname}", str(fe))

        # Re-sync and finalize record
        doc.db_set("payment_amount", doc.payment_amount)
        frappe.db.commit()

        # Final debug log to confirm creation and attached files
        frappe.log_error(
            title="ITR Submission Success", 
            message=f"Created: {doc.name}\nFiles Saved: {', '.join(files_attached) if files_attached else 'None'}"
        )

        # --- Automated WhatsApp Confirmation ---
        try:
            from payu_frappe.utils import send_whatsapp_message
            welcome_msg = f"Hello {doc.full_name}, thank you for submitting your ITR details for {doc.tax_year}. Our team will review it shortly. Team Aionion Advisory."
            send_whatsapp_message(doc.mobile_number, welcome_msg, itr_submission=doc.name)
        except Exception as we:
            frappe.log_error(title="Auto WhatsApp Error", message=str(we))

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
def send_manual_whatsapp(docname, message=None, media_url=None, template_id=None, template_params=None, buttons=None):
    """
    Called from the manual chat dialog (supports templates and buttons).
    """
    from payu_frappe.utils import send_whatsapp_message
    doc = frappe.get_doc("ITR Filing Submission", docname)
    
    if template_params and isinstance(template_params, str):
        template_params = frappe.parse_json(template_params)

    if buttons and isinstance(buttons, str):
        buttons = frappe.parse_json(buttons)

    res = send_whatsapp_message(
        receiver_number=doc.mobile_number,
        message_text=message,
        media_url=media_url,
        itr_submission=doc.name,
        regional_manager=doc.regional_manager or frappe.session.user,
        template_id=template_id,
        template_params=template_params,
        buttons=buttons
    )
    return res


@frappe.whitelist()
def get_picky_assist_templates():
    """
    Fetch all local template configurations for the UI dropdown.
    """
    return frappe.get_all(
        "Picky Assist Template",
        fields=["name", "template_id", "template_name", "message_body", "has_buttons", "language"]
    )


@frappe.whitelist(allow_guest=True)
def get_whatsapp_history(itr_submission):
    """
    Fetch history for the integrated chat UI, bypassing client-side get_list restrictions.
    """
    return frappe.get_all(
        "Picky Assist Message",
        filters={"itr_submission": itr_submission},
        fields=["direction", "message", "creation", "media_url"],
        order_by="creation asc",
        limit=50
    )


@frappe.whitelist(allow_guest=True)
def handle_whatsapp_webhook():
    """
    Incoming WhatsApp messages from Picky Assist Webhook.
    JSON Payload: {"number": "91...", "message-in": "...", "unique-id": "..."}
    """
    data = frappe.form_dict
    
    # Try all common Picky Assist sender number fields
    raw_number = data.get("number") or data.get("sender") or data.get("from") or ""
    sender_number = str(raw_number).strip().replace("+", "")
    
    content = data.get("message_in_raw") or data.get("message-in") or data.get("text")

    if not sender_number or not content:
        return {"status": "Handled", "error": "Incomplete payload"}

    # Find the matching client by mobile number
    # We look for exact match or suffix match to handle country code variations
    client = frappe.db.get_value("ITR Filing Submission", {"mobile_number": ["like", f"%{sender_number[-10:]}"]}, ["name", "regional_manager"], as_dict=1)

    # Log the incoming message
    msg_doc = frappe.get_doc({
        "doctype": "Picky Assist Message",
        "direction": "Inbound",
        "mobile_number": sender_number,
        "message": content,
        "itr_submission": client.name if client else None,
        "regional_manager": client.regional_manager if client else None,
        "picky_assist_id": data.get("unique-id")
    })
    msg_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    # Trigger a notification for the RM if the client is matched
    if client and client.regional_manager:
        frappe.publish_realtime("whatsapp_notification", {
            "message": f"New WhatsApp from {client.name}",
            "rm": client.regional_manager
        }, user=client.regional_manager)

    return {"status": "Success", "id": msg_doc.name}


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

    if not doc.service_amount:
        frappe.throw("Service Amount is missing in this record.")

    if not doc.email:
        frappe.throw("Client Email is missing. Please provide an email address to send the link.")

    # payment_amount will be auto-synced by doc.save() -> doc.validate()
    payment_link = get_url(f"/payu_checkout?request={doc.name}")

    if not payment_link:
        frappe.throw("Failed to generate base URL for payment link.")

    doc.payment_link = payment_link
    doc.payment_status = "Link Generated"
    doc.save(ignore_permissions=True)
    frappe.db.commit()

    email_body = (
        f"<p>Dear {doc.full_name},</p>"
        f"<p>Please click the link below to complete your payment of <b>\u20b9{doc.service_amount}</b>:</p>"
        f'<p><a href="{payment_link}" style="background:#007bff;color:white;padding:10px 20px;'
        f'text-decoration:none;border-radius:5px;">Pay Now</a></p>'
        f"<p>Or copy this link: {payment_link}</p>"
        f"<br/><p>Thank you,<br>Aionion Advisory Team</p>"
    )
    try:
        frappe.enqueue(
            frappe.sendmail,
            recipients=[doc.email],
            subject=f"ITR Filing Payment Link - {doc.name}",
            message=email_body,
            queue="short",
        )
        
        # --- Send Payment Link via WhatsApp ---
        try:
            from payu_frappe.utils import send_whatsapp_message
            wa_msg = f"Hello {doc.full_name}, your ITR payment link of \u20b9{doc.service_amount} is ready. Click here to pay: {payment_link}"
            send_whatsapp_message(doc.mobile_number, wa_msg, itr_submission=doc.name)
        except Exception as we:
            frappe.log_error(title="Payment WA Error", message=str(we))
            
    except Exception:
        frappe.log_error("Email enqueue failed", "PayU Email Error")

    return {"payment_link": payment_link, "status": "Link Generated"}


@frappe.whitelist(allow_guest=True)
def get_checkout_details(request_id):
    """
    Called from the payu_checkout web page JS.
    Returns all PayU form params including the secure hash.
    """
    doc = frappe.get_doc("ITR Filing Submission", request_id)
    settings = get_payu_settings()

    # Format txnid tightly to avoid PayU's 25-character max-length limit
    # e.g. ITR-SUB-00019 (13 chars) + '-' + 2603281045 (10 chars) = 24 chars
    time_str = frappe.utils.now_datetime().strftime('%y%m%d%H%M')
    txnid = f"{doc.name}-{time_str}"
    
    # PayU strictly expects '2000' or '2000.00', but 2 decimal places is the safest format
    amt_val = float(doc.service_amount or 0)
    amount = f"{amt_val:.2f}"

    params = {
        "key": settings["key"],
        "txnid": txnid,
        "amount": amount,
        "productinfo": "ITR Filing",
        "firstname": doc.full_name or "Client",
        "email": doc.email or "test@example.com",
        "phone": doc.mobile_number or "9999999999",
        "surl": get_url("/api/method/payu_frappe.api.handle_callback"),
        "furl": get_url("/api/method/payu_frappe.api.handle_callback"),
        "service_provider": "payu_paisa",
        "udf1": "",
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

    if not request_ref and txnid.startswith("ITR-SUB-"):
        parts = txnid.split('-')
        if len(parts) >= 3:
            request_ref = f"{parts[0]}-{parts[1]}-{parts[2]}"

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
