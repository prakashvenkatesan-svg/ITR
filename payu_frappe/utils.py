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
    key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5||||||SALT
    """
    # CRITICAL: Always format amount to 2 decimal places
    amount_str = "{:.2f}".format(float(params.get("amount", 0)))
    
    # CRITICAL: All udf fields must be strings, never None
    udf1 = str(params.get("udf1", "")).strip()
    udf2 = str(params.get("udf2", "")).strip()
    udf3 = str(params.get("udf3", "")).strip()
    udf4 = str(params.get("udf4", "")).strip()
    udf5 = str(params.get("udf5", "")).strip()

    # Build the 16-pipe string exactly as PayU expects
    hash_fields = [
        str(params.get("key", "")).strip(),
        str(params.get("txnid", "")).strip(),
        amount_str,
        str(params.get("productinfo", "")).strip(),
        str(params.get("firstname", "")).strip(),
        str(params.get("email", "")).strip(),
        udf1, udf2, udf3, udf4, udf5
    ]
    
    # join(11 fields) gives 10 pipes, + "|||||" gives exactly 15 pipes total (16 segments)
    hash_str = "|".join(hash_fields) + "|||||" + salt.strip()


    return hashlib.sha512(hash_str.encode("utf-8")).hexdigest()


def verify_payu_hash(data: dict, salt: str) -> bool:
    received_hash = data.get("hash", "")
    additional_charges = data.get("additionalCharges")

    # Amount must match exactly what PayU sends back
    amount_str = "{:.2f}".format(float(data.get("amount", 0)))

    reverse_fields = [
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

    reverse_str = salt.strip() + "|" + "|".join(reverse_fields)

    if additional_charges:
        reverse_str = str(additional_charges) + "|" + reverse_str

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

