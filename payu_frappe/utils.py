import hashlib
import frappe


def get_payu_settings():
    """
    Reads PayU credentials from the PayU Settings single DocType.
    Falls back to site_config if the DocType is not available yet.
    """
    try:
        # Clear cache to ensure we get the latest saved credentials
        frappe.cache().delete_value("payu_settings")
        settings = frappe.get_single("PayU Settings")
        return {
            "merchant_id": settings.merchant_id.strip() if settings.merchant_id else "",
            "key": settings.merchant_key.strip() if settings.merchant_key else "",
            "salt": settings.merchant_salt.strip() if settings.merchant_salt else "",
            "is_sandbox": settings.is_sandbox,
        }
    except Exception:
        # Fallback: read from site_config.json (useful during initial setup)
        conf = frappe.conf
        return {
            "key": conf.get("payu_merchant_key", "").strip() if conf.get("payu_merchant_key") else "",
            "salt": conf.get("payu_merchant_salt", "").strip() if conf.get("payu_merchant_salt") else "",
            "is_sandbox": conf.get("payu_is_sandbox", 1),
        }


def generate_payu_hash(params: dict, salt: str) -> str:
    """
    PayU Outbound Hash Formula (Exactly 16 pipes):
    sha512(key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5|udf6|udf7|udf8|udf9|udf10|SALT)
    """
    # CRITICAL: Always format amount to 2 decimal places
    amount_str = "{:.2f}".format(float(params.get("amount", 0)))
    
    # Build segments strictly according to official sequence
    segments = [
        str(params.get("key", "")).strip(),
        str(params.get("txnid", "")).strip(),
        amount_str,
        str(params.get("productinfo", "")).strip(),
        str(params.get("firstname", "")).strip(),
        str(params.get("email", "")).strip(),
        str(params.get("udf1", "")).strip(),
        str(params.get("udf2", "")).strip(),
        str(params.get("udf3", "")).strip(),
        str(params.get("udf4", "")).strip(),
        str(params.get("udf5", "")).strip(),
        str(params.get("udf6", "")).strip(),
        str(params.get("udf7", "")).strip(),
        str(params.get("udf8", "")).strip(),
        str(params.get("udf9", "")).strip(),
        str(params.get("udf10", "")).strip(),
        salt.strip()
    ]
    
    hash_str = "|".join(segments)
    return hashlib.sha512(hash_str.encode("utf-8")).hexdigest()


def verify_payu_hash(data: dict, salt: str) -> bool:
    """
    PayU Inbound (Reverse) Hash Formula (Exactly 17 pipes):
    sha512(SALT|status|udf10|udf9|udf8|udf7|udf6|udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)
    """
    received_hash = data.get("hash", "")
    additional_charges = data.get("additionalCharges")

    # Amount must match exactly what PayU sends back
    amount_str = "{:.2f}".format(float(data.get("amount", 0)))

    # Official Reverse Sequence: SALT comes first, then status, then UDFs in reverse order
    reverse_segments = [
        salt.strip(),
        str(data.get("status", "")),
        str(data.get("udf10", "") or ""),
        str(data.get("udf9", "") or ""),
        str(data.get("udf8", "") or ""),
        str(data.get("udf7", "") or ""),
        str(data.get("udf6", "") or ""),
        str(data.get("udf5", "") or ""),
        str(data.get("udf4", "") or ""),
        str(data.get("udf3", "") or ""),
        str(data.get("udf2", "") or ""),
        str(data.get("udf1", "") or ""),
        str(data.get("email", "")),
        str(data.get("firstname", "")),
        str(data.get("productinfo", "")),
        amount_str,
        str(data.get("txnid", "")),
        str(data.get("key", "")),
    ]

    hash_str = "|".join(reverse_segments)

    # If additionalCharges field is present, prepend it with its own pipe
    if additional_charges:
        hash_str = str(additional_charges) + "|" + hash_str

    computed = hashlib.sha512(hash_str.encode("utf-8")).hexdigest()
    return computed.lower() == received_hash.lower()


def clean_mobile_number(mobile, country_code=None):
    """
    Standardizes a mobile number to digits-only format.
    If country_code is provided, it combines them correctly.
    Otherwise, it defaults to 91 for 10-digit numbers.
    """
    if not mobile:
        return ""
    
    # 1. Clean both parts (digits only)
    clean_mobile = "".join(filter(str.isdigit, str(mobile)))
    clean_cc = "".join(filter(str.isdigit, str(country_code))) if country_code else ""
    
    # 2. If we have a country code, ensure it's at the start
    if clean_cc:
        # If the mobile already starts with the country code, don't double it
        if clean_mobile.startswith(clean_cc):
            return clean_mobile
        return clean_cc + clean_mobile
    
    # 3. Fallback: If no country code and it's 10 digits, assume 91 (India)
    if len(clean_mobile) == 10:
        return "91" + clean_mobile
    
    return clean_mobile


def send_whatsapp_message(receiver_number, message_text, itr_submission=None, regional_manager=None, media_url=None, template_id=None, template_params=None, buttons=None, media_header=None, country_code=None):
    """
    Sends a WhatsApp message via Picky Assist Push API (V2/V4).
    Supports Text, Media, Templates, and Interactive Buttons.
    """
    import requests
    import json

    try:
        settings = frappe.get_single("Picky Assist Settings")
        if not settings.is_enabled:
            return {"status": "Disabled", "error": "WhatsApp integration is disabled in settings."}

        # Clear number using standardized utility
        clean_number = clean_mobile_number(receiver_number, country_code)
        if not clean_number:
            return {"status": "Error", "error": "Invalid mobile number"}

        # Core payload structure for V4
        payload = {
            "token": settings.get_password("api_token"),
            "application": settings.application_id,
        }

        # Individual recipient data
        recipient_data = { "number": clean_number }

        if template_id:
            # V4 Template Configuration belongs at the ROOT
            payload["template_id"] = template_id
            payload["language"] = "en"
            
            # Placeholders go into 'template_message' inside 'data'
            recipient_data["template_message"] = template_params or []
            
            # If media/buttons for a template is provided
            if media_url:
                recipient_data["media"] = media_url
            if media_header:
                recipient_data["template_header"] = media_header
        else:
            # Standard Text Message
            recipient_data["message"] = message_text or "ITR Filing Update"
            if media_url:
                recipient_data["media"] = media_url

        if buttons:
            # V4 Interactive Buttons
            recipient_data["payload"] = buttons

        # Wrap in 'data' array as required by V4 Push API
        payload["data"] = [recipient_data]

        url = "https://app.pickyassist.com/api/v2/push"
        response = requests.post(url, json=payload, timeout=15)
        res_data = response.json()

        # Log the message
        log_content = message_text
        if template_id:
            log_content = f"[Template: {template_id}] Values: {template_params}"

        # Resolve or Create Contact
        contact = None
        if itr_submission:
            client_data = frappe.db.get_value("ITR Filing Submission", itr_submission, ["full_name", "email"], as_dict=1)
            
            # Find existing contact by mobile or email (match last 10 digits for robustness)
            search_num = clean_number[-10:]
            contact_name = frappe.db.get_value("Contact", {"mobile_no": ["like", f"%{search_num}"]}, "name")
            if not contact_name and client_data and client_data.email:
                contact_name = frappe.db.get_value("Contact", {"email_id": client_data.email}, "name")
            
            if contact_name:
                contact = contact_name
            elif client_data:
                # Create a new Contact
                new_contact = frappe.get_doc({
                    "doctype": "Contact",
                    "first_name": client_data.full_name,
                    "email_id": client_data.email,
                    "mobile_no": clean_number
                })
                new_contact.insert(ignore_permissions=True)
                contact = new_contact.name

        # Determine message type
        msg_type = "Text"
        if template_id:
            msg_type = "Template"
        elif media_url:
            msg_type = "Media"

        # Handle status from Picky Assist (v2/v4 uses 100 or "Success")
        raw_status = res_data.get("status")
        raw_message = str(res_data.get("message", "")).lower()
        
        # Consider success if status is 100 or message is "success"
        is_success = (raw_status == 100 or raw_status == "100" or raw_message == "success")
        final_status = "Sent" if is_success else "Failed"

        if not is_success:
            frappe.log_error(
                title="Picky Assist API Failure",
                message=f"Payload: {json.dumps(payload, indent=2)}\n\nResponse: {json.dumps(res_data, indent=2)}"
            )

        log_doc = frappe.get_doc({
            "doctype": "Picky Assist Message",
            "direction": "Outbound",
            "mobile_number": clean_number,
            "message": log_content,
            "media_url": media_url,
            "itr_submission": itr_submission,
            "contact": contact,
            "message_type": msg_type,
            "status": final_status,
            "regional_manager": regional_manager or frappe.session.user,
            "picky_assist_id": str(res_data.get("data", [{}])[0].get("id", "")) if is_success else ""
        })
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        if is_success:
            return {"status": "Success", "data": res_data, "id": log_doc.name}
        else:
            error_msg = res_data.get("message") or res_data.get("status") or "Unknown Picky Assist Error"
            return {"status": "Error", "error": error_msg}

    except Exception as e:
        frappe.log_error(title="WhatsApp Send Error", message=frappe.get_traceback())
        return {"status": "Error", "error": str(e)}

