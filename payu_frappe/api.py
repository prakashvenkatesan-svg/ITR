import frappe
from frappe.utils import get_url
from payu_frappe.utils import get_payu_settings, generate_payu_hash, verify_payu_hash, clean_mobile_number


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
            str(data.get("email") or data.get("email_id") or 
            data.get("emailId") or data.get("Email") or "").strip()
        )

        ty = data.get("taxYear") or "2025-26"
        if ty and "AY" not in ty:
            ty = f"AY {ty}"
        doc.tax_year = ty
        doc.annual_income = data.get("annualIncome")

        # --- Mobile ---
        doc.mobile_number = str(data.get("mobileNumber") or data.get("mobile") or "").strip()
        doc.country_code = str(data.get("country_code") or data.get("countryCode") or "").strip()
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
        # Use frappe.flags.in_import to suppress the Assignment Rule automation.
        # This is the correct Frappe mechanism — the assignment rule checks this flag
        # and skips execution. Without this, Guest submissions crash because the rule
        # tries to 'share' the doc which Frappe blocks for Guest users.
        frappe.flags.in_import = True
        try:
            doc.insert(ignore_permissions=True)
        finally:
            frappe.flags.in_import = False

        # Trigger assignment as Administrator AFTER insert succeeds (no crash risk)
        try:
            frappe.set_user("Administrator")
            from frappe.automation.doctype.assignment_rule.assignment_rule import apply as apply_assignment
            apply_assignment(doc, "after_insert")
        except Exception:
            pass  # Assignment failure must never block the submission
        finally:
            frappe.set_user("Guest")

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

        # --- Automated WhatsApp Confirmation (Template required to reach new users) ---
        try:
            from payu_frappe.utils import send_whatsapp_message
            # Use the approved template to bypass 24-hour restriction for new users
            # Template VX208528995 expects: [name, amount, link]
            send_whatsapp_message(
                receiver_number=doc.mobile_number, 
                message_text=f"Hello {doc.full_name}, thank you for submitting your ITR details.", 
                itr_submission=doc.name, 
                country_code=doc.country_code,
                regional_manager=doc.regional_manager or "Administrator",
                template_id="VX208528995",
                template_params=[doc.full_name, str(doc.service_amount or "TBD"), "https://aionionadvisory.com"]
            )
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
        buttons=buttons,
        country_code=doc.country_code
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
    """Fetch history for the chat UI, ensuring all messages for the mobile number are included."""
    # First, get the mobile number for this submission
    mobile = frappe.db.get_value("ITR Filing Submission", itr_submission, "mobile_number")
    if not mobile:
        return []

    # Clean the number to last 10 digits for robust matching
    clean_mobile = clean_mobile_number(mobile)[-10:]

    return frappe.get_all(
        "Picky Assist Message",
        filters={"mobile_number": ["like", f"%{clean_mobile}"]},
        fields=["direction", "message", "creation", "media_url", "mobile_number", "itr_submission", "status", "message_type"],
        order_by="creation asc"
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

    # Find the matching client by mobile number (standardized check)
    search_num = clean_mobile_number(sender_number)[-10:]
    client_name = frappe.db.get_value(
        "ITR Filing Submission", 
        {"mobile_number": ["like", f"%{search_num}"]}, 
        "name", 
        order_by="creation desc"
    )
    
    regional_manager = frappe.db.get_value("ITR Filing Submission", client_name, "regional_manager") if client_name else None

    # Resolve Contact
    contact = frappe.db.get_value("Contact", {"mobile_no": ["like", f"%{sender_number[-10:]}"]}, "name")

    # Determine message type
    msg_type = "Text"
    if data.get("media") or data.get("file"):
        msg_type = "Media"

    # Log the incoming message
    msg_doc = frappe.get_doc({
        "doctype": "Picky Assist Message",
        "direction": "Inbound",
        "mobile_number": sender_number,
        "message": content,
        "itr_submission": client_name,
        "contact": contact,
        "message_type": msg_type,
        "status": "Received",
        "regional_manager": regional_manager,
        "picky_assist_id": data.get("unique-id") or data.get("id")
    })
    msg_doc.insert(ignore_permissions=True)
    frappe.db.commit()

    # Trigger a real-time update
    frappe.publish_realtime("whatsapp_notification", {
        "message": content,
        "itr_submission": client_name,
        "mobile_number": sender_number,
        "rm": regional_manager
    }, user=regional_manager)

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
            reference_doctype="ITR Filing Submission",
            reference_name=doc.name,
            queue="short",
        )
        
        # --- Send Payment Link via WhatsApp (Template Required for Outbound) ---
        try:
            from payu_frappe.utils import send_whatsapp_message
            # Using specific Template ID VX208528995 to bypass 24-hour restriction
            wa_msg = f"Hello {doc.full_name}, your ITR payment link of \u20b9{doc.service_amount} is ready. Click here to pay: {payment_link}"
            send_whatsapp_message(
                receiver_number=doc.mobile_number, 
                message_text=wa_msg, # Fallback message
                itr_submission=doc.name,
                country_code=doc.country_code,
                template_id="VX208528995",
                template_params=[doc.full_name, str(doc.service_amount), payment_link, "Picky Assist", "Aionion"]
            )
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
    # Safer txnid: max 21-23 chars (PayU limit is 25)
    time_str = frappe.utils.now_datetime().strftime('%y%m%d%H%M%S') 
    short_name = doc.name.replace("-", "")[-8:] 
    txnid = f"{short_name}-{time_str}"
    
    # Amount with exactly 2 decimal places
    amt_val = float(doc.service_amount or 0)
    amount = f"{amt_val:.2f}"

    params = {
        "merchant_id": str(settings.get("merchant_id", "")).strip(),
        "key": str(settings["key"]).strip(),
        "txnid": txnid,
        "amount": amount,
        "productinfo": "ITR",
        "firstname": str(doc.full_name or "Client").strip()[:30],
        "email": str(doc.email or "test@example.com").strip(),
        "phone": str(doc.mobile_number or "9999999999").strip(),
        "surl": get_url("/api/method/payu_frappe.api.handle_callback"),
        "furl": get_url("/api/method/payu_frappe.api.handle_callback"),
        "service_provider": "payu_paisa",
        "udf1": doc.name,
        "udf2": "",
        "udf3": "",
        "udf4": "",
        "udf5": "",
        "udf6": "",
        "udf7": "",
        "udf8": "",
        "udf9": "",
        "udf10": "",
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
    Verifies hash, logs transaction, and optionally verifies with PayU API.
    """
    data = frappe.form_dict
    settings = get_payu_settings()

    # 1. Standard Hash Verification
    hash_valid = verify_payu_hash(data, settings["salt"])
    
    # 2. Server-side API Verification (Mandatory Security Check)
    api_verified = False
    txnid = data.get("txnid", "")
    request_ref = data.get("udf1", "")
    
    if txnid:
        api_status = verify_payment_with_payu_api(txnid, settings)
        if api_status and api_status.get("status") == "success":
            txn_details = api_status.get("transaction_details", {}).get(txnid, {})
            if txn_details.get("status") == "success":
                api_verified = True

    # Log the attempt
    try:
        tx_log = frappe.get_doc({
            "doctype": "PayU Transaction Log",
            "transaction_id": txnid,
            "client_request_ref": request_ref,
            "client_name": data.get("firstname", ""),
            "client_mobile": data.get("phone", ""),
            "client_email": data.get("email", ""),
            "amount": data.get("amount"),
            "status": "Success" if (hash_valid and api_verified and data.get("status") == "success") else "Failed",
            "payment_method": data.get("mode", ""),
            "upi_id": data.get("bank_ref_num", data.get("mihpayid", "")),
            "response_data": frappe.as_json(dict(data)),
            "payment_date": frappe.utils.now_datetime(),
        })
        tx_log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"PayU Log Error: {str(e)}", "PayU Integration")

    # Final Decision
    if hash_valid and api_verified and data.get("status") == "success":
        if request_ref and frappe.db.exists("ITR Filing Submission", request_ref):
            req_doc = frappe.get_doc("ITR Filing Submission", request_ref)
            req_doc.payment_status = "Paid"
            req_doc.save(ignore_permissions=True)
            frappe.db.commit()

        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-success"
    else:
        # If hash is valid but API failed, log as potential security risk
        if hash_valid and not api_verified and data.get("status") == "success":
            frappe.log_error(f"Potential Fraud Attempt: Hash valid but API status failed for {txnid}", "PayU Security")

        frappe.local.response["type"] = "redirect"
        frappe.local.response["location"] = "/payment-failed"


def verify_payment_with_payu_api(txnid, settings):
    """
    Calls PayU Verify Payment API (server-to-server) to confirm transaction status.
    Formula: sha512(key|command|var1|salt)
    """
    import hashlib
    import requests
    
    key = settings["key"]
    salt = settings["salt"]
    command = "verify_payment"
    var1 = txnid
    
    # Calculate API Hash
    hash_str = f"{key}|{command}|{var1}|{salt}"
    api_hash = hashlib.sha512(hash_str.encode("utf-8")).hexdigest()
    
    # Use appropriate endpoint
    url = "https://test.payu.in/merchant/postservice?form=2" if settings["is_sandbox"] else "https://info.payu.in/merchant/postservice?form=2"
    
    payload = {
        "key": key,
        "command": command,
        "var1": var1,
        "hash": api_hash
    }
    
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        frappe.log_error(f"PayU Verify API Error: {str(e)}", "PayU Integration")
        return None
