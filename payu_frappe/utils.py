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
    hash_fields = [
        str(params.get("key", "")).strip(),
        str(params.get("txnid", "")).strip(),
        str(params.get("amount", "")).strip(),
        str(params.get("productinfo", "")).strip(),
        str(params.get("firstname", "")).strip(),
        str(params.get("email", "")).strip(),
        str(params.get("udf1", "")).strip(),
        "", "", "", "", "", "", "", "", ""  # udf2 -> udf10
    ]
    
    # join gives 15 pipes, + "|" + salt gives the 16th pipe
    hash_str = "|".join(hash_fields) + "|" + salt.strip()

    frappe.log_error("FINAL CORRECT HASH STRING", hash_str)

    return hashlib.sha512(hash_str.encode("utf-8")).hexdigest()


def verify_payu_hash(data: dict, salt: str) -> bool:
    """
    Verify the reverse hash returned by PayU after payment.
    Hash Formula: SALT|status|udf10|udf9|udf8|udf7|udf6|udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
    """
    received_hash = data.get("hash", "")
    additional_charges = data.get("additionalCharges")
    
    # Reverse string components in the correct PayU-specified order
    reverse_fields = [
        str(data.get("status", "")),
        str(data.get("udf10", "")),
        str(data.get("udf9", "")),
        str(data.get("udf8", "")),
        str(data.get("udf7", "")),
        str(data.get("udf6", "")),
        str(data.get("udf5", "")),
        str(data.get("udf4", "")),
        str(data.get("udf3", "")),
        str(data.get("udf2", "")),
        str(data.get("udf1", "")),
        str(data.get("email", "")),
        str(data.get("firstname", "")),
        str(data.get("productinfo", "")),
        str(data.get("amount", "")),
        str(data.get("txnid", "")),
        str(data.get("key", "")),
    ]
    
    reverse_str = f"{salt}|" + "|".join(reverse_fields)
    
    # If additionalCharges are present, they are prepended with an extra pipe
    if additional_charges:
        reverse_str = f"{additional_charges}|{reverse_str}"
        
    expected_hash = hashlib.sha512(reverse_str.encode("utf-8")).hexdigest()
    return received_hash.lower() == expected_hash.lower()


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

        log_doc = frappe.get_doc({
            "doctype": "Picky Assist Message",
            "direction": "Outbound",
            "mobile_number": clean_number,
            "message": log_content,
            "media_url": media_url,
            "itr_submission": itr_submission,
            "regional_manager": regional_manager or frappe.session.user,
            "picky_assist_id": str(res_data.get("data", [{}])[0].get("id", "")) if res_data.get("status") == "success" else ""
        })
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        # Handle case-insensitive status from Picky Assist
        api_status = str(res_data.get("status", "")).lower()
        
        if api_status == "success":
            return {"status": "Success", "data": res_data, "id": log_doc.name}
        else:
            # Check if there is an error message, otherwise show the status itself
            error_msg = res_data.get("message") or res_data.get("status") or "Unknown Picky Assist Error"
            return {"status": "Error", "error": error_msg}

    except Exception as e:
        frappe.log_error(title="WhatsApp Send Error", message=frappe.get_traceback())
        return {"status": "Error", "error": str(e)}

