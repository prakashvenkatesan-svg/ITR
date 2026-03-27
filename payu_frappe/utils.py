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
            "key": settings.merchant_key,
            "salt": settings.merchant_salt,
            "is_sandbox": settings.is_sandbox,
        }
    except Exception:
        # Fallback: read from site_config.json (useful during initial setup)
        conf = frappe.conf
        return {
            "key": conf.get("payu_merchant_key", ""),
            "salt": conf.get("payu_merchant_salt", ""),
            "is_sandbox": conf.get("payu_is_sandbox", 1),
        }


def generate_payu_hash(params: dict, salt: str) -> str:
    """
    PayU hash formula (SHA-512):
    key|txnid|amount|productinfo|firstname|email|udf1|udf2|udf3|udf4|udf5|||||SALT
    """
    hash_str = (
        f"{params['key']}|{params['txnid']}|{params['amount']}|"
        f"{params['productinfo']}|{params['firstname']}|{params['email']}|"
        f"{params.get('udf1','')}|{params.get('udf2','')}|{params.get('udf3','')}|"
        f"{params.get('udf4','')}|{params.get('udf5','')}||||||{salt}"
    )
    return hashlib.sha512(hash_str.encode("utf-8")).hexdigest()


def verify_payu_hash(data: dict, salt: str) -> bool:
    """
    Verify the reverse hash returned by PayU after payment.
    Reverse hash formula:
    SALT|status||||||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key
    """
    received_hash = data.get("hash", "")
    reverse_str = (
        f"{salt}|{data.get('status','')}|"
        f"{data.get('udf10','')}|{data.get('udf9','')}|{data.get('udf8','')}|"
        f"{data.get('udf7','')}|{data.get('udf6','')}|"
        f"{data.get('udf5','')}|{data.get('udf4','')}|{data.get('udf3','')}|"
        f"{data.get('udf2','')}|{data.get('udf1','')}|"
        f"{data.get('email','')}|{data.get('firstname','')}|"
        f"{data.get('productinfo','')}|{data.get('amount','')}|"
        f"{data.get('txnid','')}|{data.get('key','')}"
    )
    expected_hash = hashlib.sha512(reverse_str.encode("utf-8")).hexdigest()
    return received_hash.lower() == expected_hash.lower()
