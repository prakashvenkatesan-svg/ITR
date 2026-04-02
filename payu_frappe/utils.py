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
    PayU hash formula (exactly 16 pipes):
    key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5|udf6|udf7|udf8|udf9|udf10|SALT
    """
    # CRITICAL: Always format amount to 2 decimal places
    amount_str = "{:.2f}".format(float(params.get("amount", 0)))
    
    # CRITICAL: All udf fields must be strings, never None
    udf1 = str(params.get("udf1", "")).strip()
    udf2 = str(params.get("udf2", "")).strip()
    udf3 = str(params.get("udf3", "")).strip()
    udf4 = str(params.get("udf4", "")).strip()
    udf5 = str(params.get("udf5", "")).strip()

    # Build the string exactly as PayU Bolt/Standard expects
    hash_fields = [
        str(params.get("key", "")).strip(),
        str(params.get("txnid", "")).strip(),
        amount_str,
        str(params.get("productinfo", "")).strip(),
        str(params.get("firstname", "")).strip(),
        str(params.get("email", "")).strip(),
        udf1, udf2, udf3, udf4, udf5
    ]
    
    # join(11 fields) gives 10 pipes.
    # To reach 16 pipes (accounting for udf6-udf10 slots), we add 6 more pipes trailing.
    hash_str = "|".join(hash_fields) + "||||||" + salt.strip()

    return hashlib.sha512(hash_str.encode("utf-8")).hexdigest()


def verify_payu_hash(data: dict, salt: str) -> bool:
    """
    Verify the reverse hash returned by PayU after payment.
    Reference Formula: salt|status|udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
    """
    received_hash = data.get("hash", "")

    # Amount must match exactly what PayU sends back
    amount_str = "{:.2f}".format(float(data.get("amount", 0)))

    # Order must strictly match the reference implementation
    reverse_fields = [
        str(data.get("status", "")),
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

    reverse_str = salt.strip() + "|" + "|".join(reverse_fields)

    computed = hashlib.sha512(reverse_str.encode("utf-8")).hexdigest()
    return computed.lower() == received_hash.lower()


def send_whatsapp_message(receiver_number, message_text, itr_submission=None, regional_manager=None, media_url=None, template_id=None, template_params=None, buttons=None, media_header=None):
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

        # Clear number: remove +, spaces, etc.
        clean_number = "".join(filter(str.isdigit, str(receiver_number)))
        if not clean_number.startswith("91") and len(clean_number) == 10:
            clean_number = "91" + clean_number

        # Core message data
        message_data = { "number": clean_number }

        if template_id:
            # V4 Template Logic
            # template_params should be a list of strings for {{1}}, {{2}}...
            message_data["template_message"] = template_params or []
            message_data["language"] = "en"
        else:
            # Standard Text
            message_data["message"] = message_text

        if template_id:
            message_data["template_id"] = template_id
            if template_params:
                message_data["template_message"] = template_params

        if media_url:
            message_data["media"] = media_url
            if media_header:
                message_data["template_header"] = media_header
        
        if buttons:
            # V4 Interactive Buttons (payload)
            message_data["payload"] = buttons

        payload = {
            "token": settings.get_password("api_token"),
            "application": settings.application_id,
            "data": [message_data]
        }

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
            
            # Find existing contact by mobile or email
            contact_name = frappe.db.get_value("Contact", {"mobile_no": ["like", f"%{clean_number[-10:]}"]}, "name")
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

        # Handle case-insensitive status from Picky Assist
        api_status = str(res_data.get("status", "")).lower()
        final_status = "Sent" if api_status == "success" else "Failed"

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
            "picky_assist_id": str(res_data.get("data", [{}])[0].get("id", "")) if api_status == "success" else ""
        })
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        if api_status == "success":
            return {"status": "Success", "data": res_data, "id": log_doc.name}
        else:
            error_msg = res_data.get("message") or res_data.get("status") or "Unknown Picky Assist Error"
            return {"status": "Error", "error": error_msg}

    except Exception as e:
        frappe.log_error(title="WhatsApp Send Error", message=frappe.get_traceback())
        return {"status": "Error", "error": str(e)}

