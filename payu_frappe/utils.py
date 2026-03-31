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
