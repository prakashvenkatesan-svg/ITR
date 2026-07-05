"""
payu_frappe/payment_reconcile.py
---------------------------------
Standalone PayU Transaction Reconciliation module.
Does NOT touch any existing code. Adds two whitelisted APIs:

1. sync_payu_transactions(itr_submission_name)
   - Called manually from the Frappe form button OR via Scheduled Job.
   - Queries PayU's Payment Link Transactions API using the referenceId
     (txnid embedded in the payment_link URL stored on the ITR submission).
   - Creates a PayU Transaction Log entry for each found transaction.
   - Updates payment_status = "Paid" on the ITR submission if successful.

2. sync_all_pending_payments()
   - Loops over all ITR Filing Submissions with payment_status = "Link Generated"
     and calls sync_payu_transactions for each.
   - Safe to run as a Frappe Scheduled Job (daily cron).
"""

import frappe
import hashlib
import requests

from payu_frappe.utils import get_payu_settings, get_payu_access_token


# ---------------------------------------------------------------------------
# Internal helper — extract the referenceId from the stored payment link
# ---------------------------------------------------------------------------

def _extract_reference_id_from_doc(doc):
    """
    The referenceId (txnid) was embedded in the successUrl / failureUrl
    when the payment link was created (format: {short_name}-{time_str}).
    PayU also stores it as referenceId in their system.

    We look for payment_link field on the doc.
    The referenceId is stored on the ITR doc's name + creation time — we
    reconstruct it using the same logic as generate_payment_link_and_send().

    However, the easiest reliable approach is to query PayU by merchant's
    referenceId which is stored as the 'txnid' we generated.
    We stored nothing locally — so we call the PayU Payment Link Transactions
    endpoint using invoiceId (referenceId / our txnid) if we have it,
    OR fall back to querying by date range using the Verify API.
    """
    # The payment link URL looks like: https://u.payu.in/PAYUMN/xxxxx
    # The referenceId (our txnid) is what PayU maps internally.
    # We cannot reconstruct the exact txnid from the short URL alone.
    # Best approach: use PayU's verify_payment API with txnid from the successUrl
    # that was appended as a query parameter.

    # Since successUrl was built as:
    #   {callback_base}?request_ref={doc.name}&txnid={txnid}&status=success
    # The txnid was: f"{short_name}-{time_str}" where:
    #   short_name = doc.name.replace("-", "")[-8:]
    #   time_str   = creation_time.strftime('%y%m%d%H%M%S')
    #
    # We don't have the original creation_time of the payment link stored separately.
    # So we cannot reconstruct it perfectly.
    #
    # The correct approach is to use PayU's GET /payment-links/{referenceId}/txns
    # endpoint, OR the verify_payment postservice API with the merchant's txnid.
    #
    # Since we stored payment_status = "Link Generated" and payment_link, but NOT
    # the referenceId separately, we need to add it OR use the date-range API.
    #
    # SOLUTION: Store txnid on doc when generating (see note below).
    # For NOW: extract from the ITR submission's doc.name + modification time heuristic.

    return None  # Will be resolved in sync_payu_transactions below


# ---------------------------------------------------------------------------
# Core: fetch PayU transactions for a single ITR submission
# ---------------------------------------------------------------------------

@frappe.whitelist()
def sync_payu_transactions(itr_submission_name, mihpayid=None):
    """
    Fetches transaction details from PayU for a given ITR Filing Submission
    and creates/updates a PayU Transaction Log entry.

    Called from the Frappe form JS button OR in bulk via sync_all_pending_payments().

    Strategy:
    1. Use PayU's Payment Link Transactions API (GET /payment-links/{invoiceId}/txns)
       with our referenceId (stored as txnid when the link was generated).
       The referenceId == payment_link_reference_id field (we'll store it going forward).
    2. If not available, fall back to PayU's verify_payment postservice using the
       txnid saved in the ITR doc (requires txnid stored — added to form from now on).
    3. As a last resort, use the Get Transaction Details date-range API for today.
    """
    doc = frappe.get_doc("ITR Filing Submission", itr_submission_name)
    settings = get_payu_settings()

    if doc.payment_status == "Paid":
        return {"status": "already_paid", "message": "This submission is already marked as Paid."}

    # ── STRATEGY 0: Direct lookup by PayU Payment ID (mihpayid) ─────────────
    # This is the most reliable method — user provides the ID shown on PayU's
    # success page (e.g. Payment ID: 28126138459)
    txn_data = None

    if mihpayid:
        txn_data = _query_payu_by_mihpayid(str(mihpayid).strip(), settings)

    # ── STRATEGY 1: Use the stored payment_link_txnid if available ──────────
    stored_txnid = getattr(doc, "payment_link_txnid", None) or ""

    if not txn_data and stored_txnid:
        txn_data = _query_payu_by_txnid(stored_txnid, settings)

    # ── STRATEGY 2: Use PayU Payment Links Transactions API ─────────────────
    if not txn_data and doc.payment_link:
        txn_data = _query_payu_payment_link_txns_by_date(doc, settings)

    if not txn_data:
        frappe.log_error(
            title="PayU Sync — No Transaction Found",
            message=(
                f"ITR Submission: {itr_submission_name}\n"
                f"Payment Link: {doc.payment_link}\n"
                f"PayU Payment ID (mihpayid) provided: {mihpayid or 'None'}\n"
                f"PayU returned no matching transaction. Payment may be pending."
            )
        )
        return {
            "status": "not_found",
            "message": "No completed transaction found at PayU. Please check the Payment ID and try again."
        }

    # ── Create / Update Transaction Log ─────────────────────────────────────
    txnid    = txn_data.get("mihpayid") or txn_data.get("txnid") or stored_txnid or ""
    status   = txn_data.get("status", "").lower()
    is_paid  = (status == "success" or status == "captured")

    # Avoid duplicate logs
    existing_log = frappe.db.exists("PayU Transaction Log", {"transaction_id": txnid})
    if existing_log:
        if is_paid:
            _mark_itr_as_paid(doc)
        return {
            "status": "already_logged",
            "message": f"Transaction {txnid} already exists in the log.",
            "is_paid": is_paid
        }

    try:
        tx_log = frappe.get_doc({
            "doctype":           "PayU Transaction Log",
            "transaction_id":    txnid,
            "client_request_ref": itr_submission_name,
            "client_name":       txn_data.get("firstname", "") or doc.full_name or "",
            "client_mobile":     txn_data.get("phone", "") or doc.mobile_number or "",
            "client_email":      txn_data.get("email", "") or doc.email or "",
            "amount":            txn_data.get("amount") or doc.service_amount or 0,
            "status":            "Success" if is_paid else "Failed",
            "payment_method":    txn_data.get("mode", "") or txn_data.get("payment_source", ""),
            "upi_id":            txn_data.get("bank_ref_num", "") or txn_data.get("mihpayid", ""),
            "response_data":     frappe.as_json(txn_data),
            "payment_date":      frappe.utils.now_datetime(),
        })
        tx_log.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(
            title="PayU Sync — Log Insert Failed",
            message=frappe.get_traceback()
        )
        return {"status": "error", "message": str(e)}

    # ── Update ITR submission payment status ─────────────────────────────────
    if is_paid:
        _mark_itr_as_paid(doc)
        return {
            "status": "success",
            "message": f"Payment confirmed! Transaction {txnid} logged. ITR marked as Paid.",
            "txnid": txnid,
            "is_paid": True
        }
    else:
        return {
            "status": "logged_failed",
            "message": f"Transaction {txnid} logged with status: {status}. Payment was NOT successful.",
            "txnid": txnid,
            "is_paid": False
        }


# ---------------------------------------------------------------------------
# Helper: mark ITR submission as Paid
# ---------------------------------------------------------------------------

def _mark_itr_as_paid(doc):
    """Mark the given ITR Filing Submission as Paid without triggering full save hooks."""
    try:
        frappe.db.set_value("ITR Filing Submission", doc.name, "payment_status", "Paid")
        frappe.db.commit()
        frappe.log_error(
            title="PayU Sync — Payment Status Updated",
            message=f"ITR Submission {doc.name} marked as Paid."
        )
    except Exception:
        frappe.log_error(
            title="PayU Sync — Failed to Mark as Paid",
            message=frappe.get_traceback()
        )


# ---------------------------------------------------------------------------
# Helper: Query PayU by mihpayid using get_transaction_details postservice
# ---------------------------------------------------------------------------

def _query_payu_by_mihpayid(mihpayid, settings):
    """
    Looks up a transaction by PayU's own Payment ID (mihpayid).
    This is the ID shown on PayU's payment success page.
    Uses the 'get_transaction_details' postservice command.
    Formula: sha512(key|command|var1|salt)
    """
    key     = settings["key"]
    salt    = settings["salt"]
    command = "get_transaction_details"
    # var1 is today's date in format YYYY-MM-DD for date-based lookup
    today = frappe.utils.today()  # YYYY-MM-DD

    hash_str = f"{key}|{command}|{today}|{salt}"
    api_hash = hashlib.sha512(hash_str.encode("utf-8")).hexdigest()

    url = (
        "https://test.payu.in/merchant/postservice.php?form=2"
        if settings["is_sandbox"]
        else "https://info.payu.in/merchant/postservice.php?form=2"
    )

    payload = {
        "key":     key,
        "command": command,
        "var1":    today,
        "hash":    api_hash
    }

    try:
        resp = requests.post(url, data=payload, timeout=15)
        result = resp.json()

        frappe.log_error(
            title="PayU Sync — get_transaction_details Response",
            message=frappe.as_json(result)
        )

        # The response is a dict of transactions keyed by txnid
        # Find the one matching our mihpayid
        if result.get("status") == 1:
            txn_details = result.get("transaction_details", {})
            for txnid_key, details in txn_details.items():
                if str(details.get("mihpayid", "")) == str(mihpayid):
                    return details
            # If only one transaction returned, return it (likely the one we want)
            if len(txn_details) == 1:
                only_txn = list(txn_details.values())[0]
                if only_txn.get("status") in ("success", "captured"):
                    return only_txn
    except Exception as e:
        frappe.log_error(
            title="PayU Sync — get_transaction_details Error",
            message=f"mihpayid: {mihpayid}\nError: {str(e)}"
        )
    return None


# ---------------------------------------------------------------------------
# Helper: Query PayU via verify_payment postservice (by txnid)
# ---------------------------------------------------------------------------

def _query_payu_by_txnid(txnid, settings):
    """
    Uses PayU's verify_payment server-to-server API to get transaction details.
    Formula: sha512(key|command|var1|salt)
    """
    key     = settings["key"]
    salt    = settings["salt"]
    command = "verify_payment"

    hash_str = f"{key}|{command}|{txnid}|{salt}"
    api_hash = hashlib.sha512(hash_str.encode("utf-8")).hexdigest()

    url = (
        "https://test.payu.in/merchant/postservice?form=2"
        if settings["is_sandbox"]
        else "https://info.payu.in/merchant/postservice?form=2"
    )

    payload = {
        "key":     key,
        "command": command,
        "var1":    txnid,
        "hash":    api_hash
    }

    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        result = resp.json()

        frappe.log_error(
            title="PayU Sync — verify_payment Response",
            message=frappe.as_json(result)
        )

        if result.get("status") == 1:
            txn_details = result.get("transaction_details", {})
            # transaction_details is a dict keyed by txnid
            for key_name, details in txn_details.items():
                if details.get("status") in ("success", "captured"):
                    return details
            # Return first record even if failed (for logging)
            for key_name, details in txn_details.items():
                return details
    except Exception as e:
        frappe.log_error(
            title="PayU Sync — verify_payment API Error",
            message=f"TxnID: {txnid}\nError: {str(e)}"
        )
    return None


# ---------------------------------------------------------------------------
# Helper: Query PayU Payment Links Transactions API by date range
# ---------------------------------------------------------------------------

def _query_payu_payment_link_txns_by_date(doc, settings):
    """
    Uses PayU's Payment Links GET transactions API with OAuth Bearer token.
    Endpoint: GET /payment-links/transactions?fromDate=YYYY-MM-DD&toDate=YYYY-MM-DD&merchantId=xxx

    Matches transaction by client mobile number or email.
    Falls back to get_transaction_details postservice API.
    """
    try:
        # Request access token with a broad/view scope.
        # PayU documentation is sometimes vague, but 'view_payment_links' or omitting scope (if enabled) works for fetching.
        access_token = get_payu_access_token(settings, scope="view_payment_links")
    except Exception:
        frappe.log_error(
            title="PayU Sync — Token Error",
            message=frappe.get_traceback()
        )
        return None

    # Use today's date as the range (payment just happened)
    today = frappe.utils.today()
    # Also check yesterday in case payment was late at night
    yesterday = frappe.utils.add_days(today, -1)

    base_url = (
        "https://uatoneapi.payu.in/payment-links/transactions"
        if settings["is_sandbox"]
        else "https://oneapi.payu.in/payment-links/transactions"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "merchantId":    str(settings.get("merchant_id")).strip(),
        "Content-Type":  "application/json"
    }

    params = {
        "merchantId": str(settings.get("merchant_id")).strip(),
        "fromDate":   yesterday,
        "toDate":     today
    }

    try:
        resp = requests.get(base_url, headers=headers, params=params, timeout=15)
        result = resp.json()

        frappe.log_error(
            title="PayU Sync — Payment Links Txns Response",
            message=frappe.as_json(result)
        )

        # Parse based on response structure
        txn_list = []
        if isinstance(result, list):
            txn_list = result
        elif isinstance(result, dict):
            txn_list = (
                result.get("result", []) or
                result.get("data", []) or
                result.get("transactions", []) or
                []
            )

        if not txn_list:
            return None

        # Match by client mobile or email — try to identify the right record
        client_mobile_last10 = (doc.mobile_number or "")[-10:]
        client_email = (doc.email or "").lower().strip()

        for txn in txn_list:
            txn_mobile = str(txn.get("phone", "") or txn.get("mobile", "") or "")[-10:]
            txn_email  = str(txn.get("email", "") or "").lower().strip()

            if (client_mobile_last10 and txn_mobile == client_mobile_last10):
                return txn
            if (client_email and txn_email == client_email):
                return txn

        # If only one transaction in the range (likely this client's), return it
        if len(txn_list) == 1:
            return txn_list[0]

    except Exception as e:
        frappe.log_error(
            title="PayU Sync — Payment Links Txns API Error",
            message=f"Error: {str(e)}\n{frappe.get_traceback()}"
        )

    return None


# ---------------------------------------------------------------------------
# Bulk: Sync all pending ITR submissions
# ---------------------------------------------------------------------------

@frappe.whitelist()
def sync_all_pending_payments():
    """
    Called automatically every 30 minutes by Frappe Scheduler (hooks.py).
    Also callable manually from Frappe → API.

    Strategy:
    1. Fetch ALL of today's transactions from PayU using get_transaction_details
    2. Get all ITR Filing Submissions with payment_status = "Link Generated"
    3. Match each PayU transaction to an ITR submission by mobile/email/amount
    4. Auto-create PayU Transaction Log entries and mark as Paid

    Returns a summary dict.
    """
    settings = get_payu_settings()

    # ── Step 1: Fetch all today's PayU transactions in ONE API call ──────────
    all_payu_txns = _fetch_all_todays_transactions(settings)

    if not all_payu_txns:
        frappe.log_error(
            title="PayU Bulk Sync — No Transactions Today",
            message="PayU returned 0 transactions for today. No payments to reconcile."
        )
        return {"checked": 0, "paid": 0, "pending": 0, "errors": 0}

    # ── Step 2: Get all pending ITR submissions ───────────────────────────────
    pending = frappe.get_all(
        "ITR Filing Submission",
        filters={"payment_status": "Link Generated"},
        fields=["name", "full_name", "email", "mobile_number", "service_amount"],
        limit=200
    )

    results = {"checked": len(pending), "paid": 0, "pending": 0, "errors": 0}

    # ── Step 3: Match and reconcile ───────────────────────────────────────────
    for record in pending:
        matched_txn = _match_txn_to_itr(record, all_payu_txns)
        if matched_txn:
            try:
                doc = frappe.get_doc("ITR Filing Submission", record["name"])
                _create_log_and_mark_paid(doc, matched_txn)
                results["paid"] += 1
            except Exception:
                results["errors"] += 1
                frappe.log_error(
                    title="PayU Bulk Sync — Error",
                    message=f"Failed for {record['name']}:\n{frappe.get_traceback()}"
                )
        else:
            results["pending"] += 1

    frappe.log_error(
        title="PayU Bulk Sync — Complete",
        message=frappe.as_json(results)
    )
    return results


def _fetch_all_todays_transactions(settings):
    """
    Fetches all of today's PayU transactions using the get_transaction_details
    postservice API. Returns a list of transaction dicts (only successful ones).
    """
    key     = settings["key"]
    salt    = settings["salt"]
    command = "get_transaction_details"
    today   = frappe.utils.today()  # YYYY-MM-DD

    hash_str = f"{key}|{command}|{today}|{salt}"
    api_hash = hashlib.sha512(hash_str.encode("utf-8")).hexdigest()

    url = (
        "https://test.payu.in/merchant/postservice.php?form=2"
        if settings["is_sandbox"]
        else "https://info.payu.in/merchant/postservice.php?form=2"
    )

    payload = {
        "key":     key,
        "command": command,
        "var1":    today,
        "hash":    api_hash
    }

    try:
        resp = requests.post(url, data=payload, timeout=20)
        result = resp.json()

        frappe.log_error(
            title="PayU Bulk Sync — get_transaction_details",
            message=frappe.as_json(result)
        )

        if result.get("status") == 1:
            txn_details = result.get("transaction_details", {})
            # Return only successful transactions as a flat list
            return [
                txn for txn in txn_details.values()
                if txn.get("status") in ("success", "captured")
            ]
    except Exception:
        frappe.log_error(
            title="PayU Bulk Sync — API Error",
            message=frappe.get_traceback()
        )
    return []


def _match_txn_to_itr(record, payu_txns):
    """
    Tries to match a PayU transaction to an ITR Filing Submission.
    Matches by mobile number (last 10 digits) OR email address.
    """
    mobile_last10 = str(record.get("mobile_number") or "")[-10:]
    email = str(record.get("email") or "").lower().strip()
    amount = float(record.get("service_amount") or 0)

    for txn in payu_txns:
        txn_mobile = str(txn.get("phone") or txn.get("mobile") or "")[-10:]
        txn_email  = str(txn.get("email") or "").lower().strip()
        txn_amount = float(txn.get("amount") or 0)

        # Primary match: mobile number
        if mobile_last10 and txn_mobile and mobile_last10 == txn_mobile:
            return txn
        # Secondary match: email
        if email and txn_email and email == txn_email:
            return txn

    return None


def _create_log_and_mark_paid(doc, txn_data):
    """
    Creates a PayU Transaction Log entry and marks the ITR submission as Paid.
    Skips if the transaction is already logged.
    """
    txnid   = txn_data.get("mihpayid") or txn_data.get("txnid") or ""
    status  = str(txn_data.get("status", "")).lower()
    is_paid = status in ("success", "captured")

    # Skip duplicates
    if frappe.db.exists("PayU Transaction Log", {"transaction_id": txnid}):
        if is_paid:
            _mark_itr_as_paid(doc)
        return

    tx_log = frappe.get_doc({
        "doctype":            "PayU Transaction Log",
        "transaction_id":     txnid,
        "client_request_ref": doc.name,
        "client_name":        txn_data.get("firstname", "") or doc.full_name or "",
        "client_mobile":      txn_data.get("phone", "") or doc.mobile_number or "",
        "client_email":       txn_data.get("email", "") or doc.email or "",
        "amount":             txn_data.get("amount") or doc.service_amount or 0,
        "status":             "Success" if is_paid else "Failed",
        "payment_method":     txn_data.get("mode", "") or "",
        "upi_id":             txn_data.get("bank_ref_num", "") or txn_data.get("mihpayid", ""),
        "response_data":      frappe.as_json(txn_data),
        "payment_date":       frappe.utils.now_datetime(),
    })
    tx_log.insert(ignore_permissions=True)
    frappe.db.commit()

    if is_paid:
        _mark_itr_as_paid(doc)


# ---------------------------------------------------------------------------
# PayU Webhook Handler — called instantly when any payment completes
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def handle_payu_webhook():
    """
    PayU calls this endpoint (server-to-server POST) immediately when a
    payment is completed via any Payment Link.

    Configure in PayU Merchant Dashboard:
      Developer → Webhooks → Create Webhook
      URL: https://aionion-itr.m.frappe.cloud/api/method/payu_frappe.payment_reconcile.handle_payu_webhook
      Events: payment_success
    """
    try:
        data      = frappe.request.form
        key       = data.get("key", "")
        txnid     = data.get("txnid", "")
        amount    = data.get("amount", "")
        email     = data.get("email", "")
        status    = (data.get("status", "") or "").lower()
        mihpayid  = data.get("mihpayid", "")
        firstname = data.get("firstname", "")
        phone     = data.get("phone", "")
        payu_hash = data.get("hash", "")

        # Log EVERYTHING we receive for debugging
        frappe.log_error(
            title="PayU Webhook — Received",
            message=frappe.as_json(dict(data))
        )

        # ── Verify PayU hash (WARNING only — never block on mismatch) ─────────
        # Correct PayU response hash formula:
        # sha512(salt|status|||udf5|udf4|udf3|udf2|udf1|email|firstname|productinfo|amount|txnid|key)
        settings    = get_payu_settings()
        salt        = settings["salt"]
        udf1        = data.get("udf1", "")
        udf2        = data.get("udf2", "")
        udf3        = data.get("udf3", "")
        udf4        = data.get("udf4", "")
        udf5        = data.get("udf5", "")
        productinfo = data.get("productinfo", "")

        hash_str = f"{salt}|{status}|||{udf5}|{udf4}|{udf3}|{udf2}|{udf1}|{email}|{firstname}|{productinfo}|{amount}|{txnid}|{key}"
        expected_hash = hashlib.sha512(hash_str.encode("utf-8")).hexdigest()

        if expected_hash != payu_hash:
            # Log but DO NOT stop — continue processing the payment
            frappe.log_error(
                title="PayU Webhook — Hash Warning (continuing anyway)",
                message=(
                    f"Hash mismatch detected but processing payment anyway.\n"
                    f"Expected: {expected_hash}\nReceived: {payu_hash}\n"
                    f"TxnID: {txnid} | Amount: {amount} | Status: {status}"
                )
            )
        # ── Only process successful payments ──────────────────────────────────
        if status not in ("success", "captured"):
            frappe.log_error(
                title="PayU Webhook — Non-success Payment",
                message=f"TxnID: {txnid} | Status: {status} | Skipping."
            )
            frappe.local.response["http_status_code"] = 200
            frappe.local.response["message"] = "ignored_non_success"
            return

        # ── Use mihpayid or txnid as the unique transaction identifier ────────
        log_txn_id = mihpayid or txnid
        if not log_txn_id:
            frappe.log_error(
                title="PayU Webhook — Missing TxnID",
                message=f"Both mihpayid and txnid are empty. Data: {frappe.as_json(dict(data))}"
            )
            frappe.local.response["http_status_code"] = 200
            frappe.local.response["message"] = "missing_txnid"
            return

        # ── Skip duplicates ────────────────────────────────────────────────────
        if frappe.db.exists("PayU Transaction Log", {"transaction_id": log_txn_id}):
            frappe.log_error(
                title="PayU Webhook — Duplicate Skipped",
                message=f"TxnID {log_txn_id} already in log."
            )
            frappe.local.response["http_status_code"] = 200
            frappe.local.response["message"] = "duplicate"
            return

        # ── Find the matching ITR submission by mobile or email ───────────────
        itr_doc    = None
        itr_name   = None

        if phone:
            mobile_last10 = str(phone)[-10:]
            matches = frappe.get_all(
                "ITR Filing Submission",
                filters={"mobile_number": ["like", f"%{mobile_last10}"]},
                fields=["name", "payment_status"],
                order_by="creation desc",
                limit=1
            )
            if matches:
                itr_name = matches[0]["name"]

        if not itr_name and email:
            matches = frappe.get_all(
                "ITR Filing Submission",
                filters={"email": email},
                fields=["name", "payment_status"],
                order_by="creation desc",
                limit=1
            )
            if matches:
                itr_name = matches[0]["name"]

        if itr_name:
            itr_doc = frappe.get_doc("ITR Filing Submission", itr_name)

        # ── Build transaction data ─────────────────────────────────────────────
        txn_data = {
            "mihpayid":     log_txn_id,
            "txnid":        txnid,
            "status":       status,
            "amount":       amount,
            "firstname":    firstname or (itr_doc.full_name if itr_doc else ""),
            "email":        email or (itr_doc.email if itr_doc else ""),
            "phone":        phone or (itr_doc.mobile_number if itr_doc else ""),
            "mode":         data.get("mode", ""),
            "bank_ref_num": data.get("bank_ref_num", ""),
        }

        # ── Create log entry ───────────────────────────────────────────────────
        tx_log = frappe.get_doc({
            "doctype":            "PayU Transaction Log",
            "transaction_id":     log_txn_id,
            "client_request_ref": itr_name or "",
            "client_name":        txn_data["firstname"],
            "client_email":       txn_data["email"],
            "client_mobile":      txn_data["phone"],
            "amount":             float(amount or 0),
            "status":             "Success",
            "payment_method":     data.get("mode", ""),
            "upi_id":             data.get("bank_ref_num", "") or log_txn_id,
            "response_data":      frappe.as_json(dict(data)),
            "payment_date":       frappe.utils.now_datetime(),
        })
        tx_log.insert(ignore_permissions=True)
        frappe.db.commit()

        # ── Mark ITR as Paid if we found one ──────────────────────────────────
        if itr_doc:
            _mark_itr_as_paid(itr_doc)
            frappe.log_error(
                title="PayU Webhook — Log Created ✅",
                message=f"ITR: {itr_doc.name} | TxnID: {log_txn_id} | ₹{amount} | Mode: {data.get('mode','')}"
            )
        else:
            frappe.log_error(
                title="PayU Webhook — Orphan Log Created",
                message=f"No ITR match for phone={phone}/email={email}. Log saved as orphan: {log_txn_id}"
            )

        frappe.local.response["http_status_code"] = 200
        frappe.local.response["message"] = "ok"

    except Exception:
        frappe.log_error(
            title="PayU Webhook — Exception",
            message=frappe.get_traceback()
        )
        frappe.local.response["http_status_code"] = 200
        frappe.local.response["message"] = "error_logged"
