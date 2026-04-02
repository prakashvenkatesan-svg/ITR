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

        // --- WhatsApp Popup Button ---
        if (frm.doc.mobile_number && !frm.is_new()) {
            frm.add_custom_button(__('WhatsApp'), function() {
                open_whatsapp_dialog(frm);
            });
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

// --- WhatsApp Popup Dialog Functionality ---
function open_whatsapp_dialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: `<i class="fa fa-whatsapp" style="color: #25D366; margin-right: 8px;"></i> WhatsApp: ${frm.doc.full_name}`,
        fields: [
            { fieldname: 'chat_widget', fieldtype: 'HTML' }
        ]
    });

    const chat_css = `
        <style>
            .wa-popup-container {
                background-color: #e5ddd5;
                height: 500px;
                display: flex;
                flex-direction: column;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                overflow: hidden;
                border-radius: 4px;
            }
            .wa-popup-messages {
                flex: 1;
                padding: 15px;
                overflow-y: auto;
                display: flex;
                flex-direction: column;
                gap: 8px;
            }
            .wa-msg {
                max-width: 80%;
                padding: 8px 12px;
                border-radius: 8px;
                font-size: 14px;
                position: relative;
                box-shadow: 0 1px 1px rgba(0,0,0,0.1);
            }
            .wa-msg.outbound { align-self: flex-end; background-color: #dcf8c6; }
            .wa-msg.inbound { align-self: flex-start; background-color: #fff; }
            .wa-msg-time { font-size: 10px; color: #999; text-align: right; margin-top: 2px; }
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
            .wa-input-container input { border: none; width: 100%; outline: none; font-size: 14px; }
            .wa-send-btn {
                background-color: #128C7E;
                color: white;
                width: 36px;
                height: 36px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                cursor: pointer;
            }
            .wa-footer-icon { color: #888; font-size: 18px; cursor: pointer; }
        </style>
    `;

    const chat_html = `
        <div class="wa-popup-container">
            <div class="wa-popup-messages" id="wa-dialog-body">
                <div style="text-align: center; color: #888; font-size: 12px; margin-top: 100px;">Loading...</div>
            </div>
            <div class="wa-chat-footer">
                <i class="fa fa-paperclip wa-footer-icon" id="wa-attach-trigger" title="Attach File"></i>
                <i class="fa fa-list-alt wa-footer-icon" id="wa-template-trigger" title="Send Template"></i>
                <div class="wa-input-container">
                    <i class="fa fa-smile-o wa-footer-icon"></i>
                    <input type="text" id="wa-dialog-input" placeholder="Type a message">
                </div>
                <div class="wa-send-btn" id="wa-dialog-send" title="Send (Enter)">
                    <i class="fa fa-paper-plane" style="font-size: 14px; margin-left: -2px;"></i>
                </div>
            </div>
        </div>
    `;

    const $wa_wrapper = dialog.fields_dict.chat_widget.$wrapper;
    $wa_wrapper.html(chat_css + chat_html);
    dialog.show();

    const $body = $wa_wrapper.find('#wa-dialog-body');
    const $input = $wa_wrapper.find('#wa-dialog-input');
    const $send = $wa_wrapper.find('#wa-dialog-send');
    const $attach = $wa_wrapper.find('#wa-attach-trigger');
    const $template = $wa_wrapper.find('#wa-template-trigger');

    // Load History
    fetch_wa_history(frm, $body);

    // Bind Events
    $send.on('click', () => send_wa_msg_popup(frm, $wa_wrapper));
    $input.on('keypress', (e) => { if (e.which === 13) send_wa_msg_popup(frm, $wa_wrapper); });
    
    // Attachment Logic
    $attach.on('click', () => {
        new frappe.ui.FileUploader({
            doctype: "ITR Filing Submission",
            docname: frm.doc.name,
            folder: "Home/Attachments",
            make_attachments_public: true,
            on_success: (file) => {
                const file_url = window.location.origin + file.file_url;
                send_wa_msg_popup(frm, $wa_wrapper, `Sent a file: ${file.file_name}`, file_url);
            }
        });
    });

    // Template Logic
    $template.on('click', () => {
        frappe.call({
            method: 'payu_frappe.api.get_picky_assist_templates',
            callback: (r) => {
                if (r.message && r.message.length > 0) {
                    show_template_popup(frm, $wa_wrapper, r.message);
                } else {
                    frappe.msgprint(__('No templates found. Add them in "Picky Assist Template" first.'));
                }
            }
        });
    });

    // Real-time
    frappe.realtime.on('whatsapp_notification', (data) => {
        // Refresh only if message is for THIS customer (matched by last 10 digits)
        const cur_mobile = (frm.doc.mobile_number || "").replace(/\D/g, "").slice(-10);
        const incoming_mobile = (data.mobile_number || "").replace(/\D/g, "").slice(-10);
        
        if (incoming_mobile === cur_mobile && $body && $body.length > 0) {
            fetch_wa_history(frm, $body, true);
        }
    });
}

function show_template_popup(frm, wa_wrapper, templates) {
    const d = new frappe.ui.Dialog({
        title: __('Send WhatsApp Template'),
        fields: [
            {
                label: __('Select Template'),
                fieldname: 'template',
                fieldtype: 'Select',
                options: templates.map(t => t.template_name),
                reqd: 1,
                on_change: () => {
                    const selected = templates.find(t => t.template_name === d.get_value('template'));
                    d.set_df_property('preview', 'options', `<b>Preview:</b><br>${selected.message_body || 'No preview available'}`);
                    
                    // Count placeholders {{1}}, {{2}}...
                    const matches = (selected.message_body || "").match(/{{(\d+)}}/g);
                    const count = matches ? (new Set(matches)).size : 0; // Unique placeholder count
                    
                    for(let i=1; i<=5; i++) {
                        d.set_df_property(`p${i}`, 'hidden', i > count);
                    }
                }
            },
            { fieldname: 'preview', fieldtype: 'HTML' },
            { fieldname: 'p1', fieldtype: 'Data', label: __('Value for {{1}}'), hidden: 1 },
            { fieldname: 'p2', fieldtype: 'Data', label: __('Value for {{2}}'), hidden: 1 },
            { fieldname: 'p3', fieldtype: 'Data', label: __('Value for {{3}}'), hidden: 1 },
            { fieldname: 'p4', fieldtype: 'Data', label: __('Value for {{4}}'), hidden: 1 },
            { fieldname: 'p5', fieldtype: 'Data', label: __('Value for {{5}}'), hidden: 1 }
        ],
        primary_action_label: __('Send Template'),
        primary_action: (values) => {
            const selected = templates.find(t => t.template_name === values.template);
            const params = [];
            if (values.p1) params.push(values.p1);
            if (values.p2) params.push(values.p2);
            if (values.p3) params.push(values.p3);
            if (values.p4) params.push(values.p4);
            if (values.p5) params.push(values.p5);

            send_wa_msg_popup(frm, wa_wrapper, null, null, selected.template_id, params);
            d.hide();
        }
    });
    d.show();
}

function fetch_wa_history(frm, body, scroll = false) {
    frappe.call({
        method: 'payu_frappe.api.get_whatsapp_history',
        args: {
            itr_submission: frm.doc.name
        },
        callback: (r) => {
            body.empty();
            if (r.message && r.message.length > 0) {
                r.message.forEach(msg => {
                const align = (msg.direction || "").toLowerCase() === 'inbound' ? 'inbound' : 'outbound';
                const time = frappe.datetime.get_time(msg.creation);
                let content = msg.message || "";
                if (msg.media_url) {
                    content += `<br><a href="${msg.media_url}" target="_blank" style="color: #075E54; font-weight: bold;">[View Attachment]</a>`;
                }
                body.append(`
                    <div class="wa-msg ${align}">
                        <div>${content}</div>
                        <div class="wa-msg-time">${time}</div>
                    </div>
                `);
                });
                if (scroll) body.scrollTop(body[0].scrollHeight);
                else setTimeout(() => body.scrollTop(body[0].scrollHeight), 200);
            } else {
                body.append('<div style="text-align: center; color: #999; margin-top: 50px;">No messages yet</div>');
            }
        }
    });
}

function send_wa_msg_popup(frm, wrapper, override_text = null, media_url = null, template_id = null, template_params = null) {
    const $input = wrapper.find('#wa-dialog-input');
    const text = override_text || $input.val().trim();
    if (!text && !media_url && !template_id) return;

    if (!override_text && !template_id) $input.val('').prop('disabled', true);

    frappe.call({
        method: 'payu_frappe.api.send_manual_whatsapp',
        args: {
            docname: frm.doc.name,
            message: text,
            media_url: media_url,
            template_id: template_id,
            template_params: template_params
        },
        callback: (r) => {
            $input.prop('disabled', false).focus();
            const status = r.message ? (r.message.status || "").toLowerCase() : "";
            
            if (status === 'success') {
                const $body = wrapper.find('#wa-dialog-body');
                fetch_wa_history(frm, $body, true);
            } else {
                const msg = (r.message && r.message.error) ? r.message.error : 'Unknown error';
                frappe.show_alert({ message: __('WhatsApp: ') + msg, indicator: 'red' });
                
                // Still try to refresh history just in case it was logged
                const $body = wrapper.find('#wa-dialog-body');
                fetch_wa_history(frm, $body, true);
            }
        }
    });
}
