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

        // --- WhatsApp Integrated Chat UI ---
        if (frm.doc.mobile_number && !frm.is_new()) {
            render_whatsapp_chat(frm);
        }

        // Show/Hide IT Portal Password
        let pwd_field = frm.fields_dict.it_portal_password;
        if (pwd_field && pwd_field.df.fieldtype === 'Data') {
            setTimeout(() => {
                let $input = pwd_field.$input;
                if ($input && $input.length > 0) {
                    $input.attr('type', 'password');
                    if ($input.parent().find('.pwd-toggle-btn').length === 0) {
                        $input.wrap('<div style="position: relative;"></div>');
                        let $eye = $('<i class="fa fa-eye pwd-toggle-btn" style="position: absolute; right: 10px; top: 8px; cursor: pointer; color: #8D99A6; z-index: 4;"></i>');
                        $eye.insertAfter($input);
                        $eye.on('click', function() {
                            if ($input.attr('type') === 'password') {
                                $input.attr('type', 'text');
                                $eye.removeClass('fa-eye').addClass('fa-eye-slash');
                            } else {
                                $input.attr('type', 'password');
                                $eye.removeClass('fa-eye-slash').addClass('fa-eye');
                            }
                        });
                    }
                }
            }, 500);
        }
    }
});

// --- WhatsApp Integrated Chat Functionality ---
function render_whatsapp_chat(frm) {
    if (!frm.fields_dict.whatsapp_chat_widget) return;

    const wrapper = $(frm.fields_dict.whatsapp_chat_widget.wrapper);
    wrapper.empty();

    // 1. Inject CSS for WhatsApp UI
    const chat_css = `
        <style>
            .wa-chat-container {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: #e5ddd5;
                height: 450px;
                display: flex;
                flex-direction: column;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                overflow: hidden;
            }
            .wa-chat-header {
                background-color: #075E54;
                color: white;
                padding: 10px 15px;
                display: flex;
                align-items: center;
                justify-content: space-between;
                font-weight: 500;
            }
            .wa-chat-header .wa-user-info { display: flex; align-items: center; gap: 10px; }
            .wa-chat-header .wa-icons { display: flex; gap: 15px; cursor: pointer; }
            .wa-chat-messages {
                flex: 1;
                padding: 15px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .wa-msg {
                max-width: 75%;
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 14px;
                position: relative;
                box-shadow: 0 1px 1px rgba(0,0,0,0.1);
            }
            .wa-msg.outbound {
                align-self: flex-end;
                background-color: #dcf8c6;
            }
            .wa-msg.inbound {
                align-self: flex-start;
                background-color: #fff;
            }
            .wa-msg-time {
                font-size: 10px;
                color: #999;
                text-align: right;
                margin-top: 2px;
            }
            .wa-chat-footer {
                background-color: #f0f0f0;
                padding: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .wa-input-container {
                flex: 1;
                background: white;
                border-radius: 20px;
                padding: 5px 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .wa-input-container input {
                border: none;
                width: 100%;
                outline: none;
                font-size: 14px;
            }
            .wa-send-btn {
                background-color: #128C7E;
                color: white;
                width: 40px;
                height: 40px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
            }
            .wa-footer-icon { color: #888; font-size: 18px; cursor: pointer; }
        </style>
    `;

    // 2. Initial HTML Structure
    const chat_html = `
        <div class="wa-chat-container">
            <div class="wa-chat-header">
                <div class="wa-user-info">
                    <i class="fa fa-user-circle" style="font-size: 24px;"></i>
                    <span>${frm.doc.full_name} (${frm.doc.mobile_number})</span>
                </div>
                <div class="wa-icons">
                    <i class="fa fa-search" title="Search Chat"></i>
                    <i class="fa fa-ellipsis-v" title="Settings"></i>
                </div>
            </div>
            <div class="wa-chat-messages" id="wa-chat-body">
                <div style="text-align: center; color: #888; font-size: 12px; margin-top: 100px;">
                    Loading messages...
                </div>
            </div>
            <div class="wa-chat-footer">
                <i class="fa fa-plus wa-footer-icon" title="Attach"></i>
                <div class="wa-input-container">
                    <i class="fa fa-smile-o wa-footer-icon"></i>
                    <input type="text" id="wa-input" placeholder="Type a message">
                </div>
                <div class="wa-send-btn" id="wa-send-trigger" title="Send (Enter)">
                    <i class="fa fa-paper-plane" style="margin-left: -2px;"></i>
                </div>
            </div>
        </div>
    `;

    wrapper.html(chat_css + chat_html);

    // 3. Load Message History
    load_chat_history(frm);

    // 4. Bind Events
    wrapper.find('#wa-send-trigger').on('click', () => send_wa_msg(frm));
    wrapper.find('#wa-input').on('keypress', (e) => {
        if (e.which === 13) send_wa_msg(frm);
    });

    // 5. Real-time Listener (Incoming)
    frappe.realtime.on('whatsapp_notification', (data) => {
        if (data.message && data.rm === frappe.session.user) {
            fetch_and_append_new_msg(frm);
        }
    });
}

function load_chat_history(frm) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'WhatsApp Message',
            filters: { itr_submission: frm.doc.name },
            fields: ['direction', 'message', 'creation'],
            order_by: 'creation asc',
            limit: 50
        },
        callback: (r) => {
            const body = $('#wa-chat-body');
            body.empty();
            if (r.message && r.message.length > 0) {
                r.message.forEach(msg => append_msg_to_ui(msg));
                scroll_wa_bottom();
            } else {
                body.append('<div style="text-align: center; color: #888; font-size: 12px; margin-top: 20px;">No messages yet.</div>');
            }
        }
    });
}

function append_msg_to_ui(msg) {
    const body = $('#wa-chat-body');
    const time = frappe.datetime.get_time(msg.creation);
    const align_class = msg.direction === 'Inbound' ? 'inbound' : 'outbound';
    
    const msg_html = `
        <div class="wa-msg ${align_class}">
            <div class="wa-msg-content">${msg.message}</div>
            <div class="wa-msg-time">${time}</div>
        </div>
    `;
    body.append(msg_html);
}

function send_wa_msg(frm) {
    const $input = $('#wa-input');
    const text = $input.val().trim();
    if (!text) return;

    $input.val('').prop('disabled', true);

    frappe.call({
        method: 'payu_frappe.api.send_manual_whatsapp',
        args: {
            docname: frm.doc.name,
            message: text
        },
        callback: (r) => {
            $input.prop('disabled', false).focus();
            if (r.message && r.message.status === 'Success') {
                // Manually append for fast feedback
                append_msg_to_ui({
                    direction: 'Outbound',
                    message: text,
                    creation: frappe.datetime.now_datetime()
                });
                scroll_wa_bottom();
            } else {
                frappe.show_alert({ message: __('Failed: ') + (r.message ? r.message.error : 'Unknown error'), indicator: 'red' });
            }
        }
    });
}

function scroll_wa_bottom() {
    const body = document.getElementById('wa-chat-body');
    if (body) body.scrollTop = body.scrollHeight;
}

function fetch_and_append_new_msg(frm) {
    // Small delay to ensure DB commit
    setTimeout(() => {
        frappe.call({
            method: 'frappe.client.get_list',
            args: {
                doctype: 'WhatsApp Message',
                filters: { itr_submission: frm.doc.name },
                fields: ['direction', 'message', 'creation'],
                order_by: 'creation desc',
                limit: 1
            },
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    append_msg_to_ui(r.message[0]);
                    scroll_wa_bottom();
                }
            }
        });
    }, 500);
}
