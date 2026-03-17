frappe.ui.form.on('ITR Filing Submission', {
    refresh: function(frm) {
        // Show "Generate Payment Link" button only when service_amount is set and payment not yet done
        if (!frm.is_new() && frm.doc.service_amount && frm.doc.payment_status !== 'Success') {
            frm.add_custom_button(__('Generate & Send Payment Link'), function() {
                frappe.confirm(
                    `Send payment link of ₹${frm.doc.service_amount} to <b>${frm.doc.email}</b>?`,
                    function() {
                        frappe.call({
                            method: 'payu_frappe.api.generate_payment_link_and_send',
                            args: { request_id: frm.doc.name },
                            freeze: true,
                            freeze_message: __('Generating payment link...'),
                            callback: function(r) {
                                if (r.message && r.message.payment_link) {
                                    frappe.msgprint({
                                        title: __('Payment Link Generated'),
                                        message: `Link sent to client email.<br><br>
                                            <a href="${r.message.payment_link}" target="_blank">
                                                ${r.message.payment_link}
                                            </a>`,
                                        indicator: 'green'
                                    });
                                    frm.reload_doc();
                                }
                            }
                        });
                    }
                );
            }, __('PayU'));
        }

        // Add quick-copy button for payment link
        if (frm.doc.payment_link) {
            frm.add_custom_button(__('Copy Payment Link'), function() {
                navigator.clipboard.writeText(frm.doc.payment_link).then(function() {
                    frappe.show_alert({ message: __('Payment link copied!'), indicator: 'green' });
                });
            }, __('PayU'));
        }

        // Colour the payment status indicator
        const statusColors = {
            'Pending': 'orange',
            'Link Generated': 'blue',
            'Success': 'green',
            'Failed': 'red'
        };
        if (frm.doc.payment_status && statusColors[frm.doc.payment_status]) {
            frm.set_indicator_formatter('payment_status', function(doc) {
                return statusColors[doc.payment_status] || 'grey';
            });
        }
    }
});
