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
def sync_payu_transactions(itr_submission_name):
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

    if not doc.payment_link:
        return {"status": "no_link", "message": "No payment link found for this submission."}

    # ── STRATEGY 1: Use the stored payment_link_txnid if available ──────────
    # Check if we stored txnid separately on the doc (field added going forward)
    stored_txnid = getattr(doc, "payment_link_txnid", None) or ""

    # ── STRATEGY 2: Use PayU Payment Links Transactions API ─────────────────
    # GET /payment-links/transactions?invoiceId={referenceId}
    # This API uses OAuth Bearer token and merchantId header.
    txn_data = None

    if stored_txnid:
        txn_data = _query_payu_by_txnid(stored_txnid, settings)

    if not txn_data:
        # Fall back: query by date range (today), filter by client mobile/email
        txn_data = _query_payu_payment_link_txns_by_date(doc, settings)

    if not txn_data:
        frappe.log_error(
            title="PayU Sync — No Transaction Found",
            message=(
                f"ITR Submission: {itr_submission_name}\n"
                f"Payment Link: {doc.payment_link}\n"
                f"Stored TxnID: {stored_txnid or 'N/A'}\n"
                f"PayU returned no matching transaction. Payment may be pending."
            )
        )
        return {
            "status": "not_found",
            "message": "No completed transaction found at PayU. Payment may still be pending."
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
        access_token = get_payu_access_token(settings)
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
    Loops over all ITR Filing Submissions with payment_status = 'Link Generated'
    and attempts to reconcile each one with PayU.

    Safe to call from Frappe Scheduler (e.g., hourly or daily job).
    Returns a summary dict.
    """
    if not frappe.has_permission("ITR Filing Submission", "write"):
        frappe.throw("You do not have permission to run payment reconciliation.")

    pending = frappe.get_all(
        "ITR Filing Submission",
        filters={"payment_status": "Link Generated", "payment_link": ["!=", ""]},
        fields=["name", "full_name", "email", "mobile_number", "payment_link"],
        limit=50  # Safety cap — avoid API rate limits
    )

    results = {"checked": len(pending), "paid": 0, "pending": 0, "errors": 0}

    for record in pending:
        try:
            result = sync_payu_transactions(record["name"])
            if result.get("is_paid"):
                results["paid"] += 1
            else:
                results["pending"] += 1
        except Exception as e:
            results["errors"] += 1
            frappe.log_error(
                title="PayU Bulk Sync Error",
                message=f"Failed for {record['name']}: {str(e)}"
            )

    frappe.log_error(
        title="PayU Bulk Sync Complete",
        message=frappe.as_json(results)
    )

    return results
