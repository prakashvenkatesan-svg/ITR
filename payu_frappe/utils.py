import hashlib
import frappe


def get_payu_settings():
    """
    Reads PayU credentials from the PayU Settings single DocType.
    Falls back to site_config if the DocType is not available yet.
    """
    try:
        settings = frappe.get_single("PayU Settings")
        return {
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
    PayU hash formula (SHA-512):
    key|txnid|amount|productinfo|firstname|email|||||||||||SALT
    """
    hash_str = (
        f"{params.get('key','')}|{params.get('txnid','')}|{params.get('amount','')}|"
        f"{params.get('productinfo','')}|{params.get('firstname','')}|{params.get('email','')}|||||||||||{salt}"
    )
    try:
        frappe.log_error("Raw PayU Hash String", f"String: '{hash_str}'\nParams: {params}")
    except Exception:
        pass
    return hashlib.sha512(hash_str.encode("utf-8")).hexdigest()


def verify_payu_hash(data: dict, salt: str) -> bool:
    """
    Verify the reverse hash returned by PayU after payment.
    """
    received_hash = data.get("hash", "")
    additional_charges = data.get("additionalCharges")

    if additional_charges:
        reverse_str = (
            f"{additional_charges}|{salt}|{data.get('status','')}|||||||||||"
            f"{data.get('email','')}|{data.get('firstname','')}|"
            f"{data.get('productinfo','')}|{data.get('amount','')}|"
            f"{data.get('txnid','')}|{data.get('key','')}"
        )
    else:
        reverse_str = (
            f"{salt}|{data.get('status','')}|||||||||||"
            f"{data.get('email','')}|{data.get('firstname','')}|"
            f"{data.get('productinfo','')}|{data.get('amount','')}|"
            f"{data.get('txnid','')}|{data.get('key','')}"
        )
    expected_hash = hashlib.sha512(reverse_str.encode("utf-8")).hexdigest()
    return received_hash.lower() == expected_hash.lower()


def send_whatsapp_message(receiver_number, message_text, itr_submission=None, regional_manager=None):
    """
    Sends a WhatsApp message via Picky Assist V2 Push API.
    Log the message in the WhatsApp Message DocType.
    """
    import requests
    import json

    try:
        settings = frappe.get_single("WhatsApp Settings")
        if not settings.is_enabled:
            return {"status": "Disabled", "error": "WhatsApp integration is disabled in settings."}

        # Clear number: remove +, spaces, etc.
        clean_number = "".join(filter(str.isdigit, str(receiver_number)))
        if not clean_number.startswith("91") and len(clean_number) == 10:
            clean_number = "91" + clean_number

        payload = {
            "token": settings.get_password("api_token"),
            "application": settings.application_id,
            "data": [
                {
                    "number": clean_number,
                    "message": message_text
                }
            ]
        }

        url = "https://app.pickyassist.com/api/v2/push"
        response = requests.post(url, json=payload, timeout=15)
        res_data = response.json()

        # Log the message in Database
        log_doc = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "direction": "Outbound",
            "mobile_number": clean_number,
            "message": message_text,
            "itr_submission": itr_submission,
            "regional_manager": regional_manager or frappe.session.user,
            "picky_assist_id": str(res_data.get("data", [{}])[0].get("id", "")) if res_data.get("status") == "success" else ""
        })
        log_doc.insert(ignore_permissions=True)
        frappe.db.commit()

        if res_data.get("status") == "success":
            return {"status": "Success", "data": res_data}
        else:
            return {"status": "Error", "error": res_data.get("message", "Unknown Picky Assist Error")}

    except Exception as e:
        frappe.log_error(title="WhatsApp Send Error", message=frappe.get_traceback())
        return {"status": "Error", "error": str(e)}

