frappe.ui.form.on('ITR Filing Submission', {
    service_amount: function(frm) {
        if (frm.doc.service_amount) {
            frm.set_value('payment_amount', parseInt(frm.doc.service_amount));
        }
    },
    refresh: function(frm) {
        // Show "Generate Payment Link" button only when service_amount is set and payment not yet done
        if (!frm.is_new() && frm.doc.service_amount && frm.doc.payment_status !== 'Success') {
            frm.add_custom_button(__('Generate & Send Payment Link'), function() {
                console.log("Button clicked for", frm.doc.name);
                if (!frm.doc.email) {
                    frappe.msgprint(__('Please provide an email address before generating the link.'));
                    return;
                }
                frappe.confirm(
                    `Send payment link of ₹${frm.doc.service_amount} to <b>${frm.doc.email}</b>?`,
                    async function() {
                        console.log("Calling API...");
                        const r = await frappe.call({
                            method: 'payu_frappe.api.generate_payment_link_and_send',
                            args: { request_id: frm.doc.name },
                            freeze: true,
                            freeze_message: __('Generating payment link...'),
                        });
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
