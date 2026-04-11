frappe.ui.form.on('ITR Filing Submission', {
    service_amount: function(frm) {
        if (frm.doc.service_amount) {
            frm.set_value('payment_amount', parseInt(frm.doc.service_amount));
        }
    },
    refresh: function(frm) {
        // --- Standalone PayU Button (placed LEFT of WhatsApp) ---
        if (!frm.is_new() && frm.doc.service_amount) {
            frm.add_custom_button(__('PayU'), function() {
                open_payu_dialog(frm);
            });
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

        // --- RM Workload Button ---
        // Visible to padmapriya (intake user) and System Managers when stage is "New Client"
        const isIntakeUser = frappe.session.user === 'padmapriya.s@aionioncapital.com';
        const isSysManager = frappe.user.has_role('System Manager');
        if (!frm.is_new() && (isIntakeUser || isSysManager) && frm.doc.stage_status === 'New Client') {
            frm.add_custom_button(__('📊 RM Workload'), function() {
                frappe.call({
                    method: 'payu_frappe.api.get_rm_workload',
                    freeze: true,
                    freeze_message: __('Loading workload data…'),
                    callback(r) {
                        if (!r.message) return;
                        const rows = r.message.map(rm => {
                            const badge = rm.next_assign
                                ? `<span style="background:#22c55e;color:#fff;padding:2px 8px;border-radius:99px;font-size:11px;font-weight:600;">Next ✓</span>`
                                : '';
                            const countColor = rm.active_records > 10 ? '#ef4444' : rm.active_records > 5 ? '#f59e0b' : '#22c55e';
                            return `
                                <tr style="border-bottom:1px solid #f0f0f0;">
                                    <td style="padding:10px 12px;font-weight:${rm.next_assign ? '700' : '400'}">${rm.name}</td>
                                    <td style="padding:10px 12px;color:#666;font-size:12px;">${rm.email}</td>
                                    <td style="padding:10px 12px;text-align:center;">
                                        <span style="background:${countColor};color:#fff;padding:3px 10px;border-radius:99px;font-weight:600;">${rm.active_records}</span>
                                    </td>
                                    <td style="padding:10px 12px;text-align:center;">${badge}</td>
                                </tr>`;
                        }).join('');

                        const html = `
                            <div style="font-family:sans-serif;">
                                <p style="color:#666;font-size:13px;margin-bottom:12px;">
                                    When you save this record as <strong>In Progress</strong>, the system will auto-assign it
                                    to the RM marked <span style="background:#22c55e;color:#fff;padding:1px 7px;border-radius:99px;font-size:11px;">Next ✓</span> below.
                                </p>
                                <table width="100%" style="border-collapse:collapse;font-size:13px;">
                                    <thead>
                                        <tr style="background:#f8f9fa;color:#444;">
                                            <th style="padding:8px 12px;text-align:left;">RM Name</th>
                                            <th style="padding:8px 12px;text-align:left;">Email</th>
                                            <th style="padding:8px 12px;text-align:center;">Active Records</th>
                                            <th style="padding:8px 12px;text-align:center;">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>${rows}</tbody>
                                </table>
                                <p style="color:#888;font-size:11px;margin-top:10px;">
                                    * Active records = all records not yet marked as Completed.
                                </p>
                            </div>`;

                        frappe.msgprint({
                            title: __('RM Workload Distribution'),
                            message: html,
                            indicator: 'blue',
                            wide: true
                        });
                    }
                });
            }, __('Assignment'));
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

// --- PayU Action Dialog ---
function open_payu_dialog(frm) {
    const has_email = !!(frm.doc.email);
    const has_link = !!(frm.doc.payment_link);
    const is_paid = frm.doc.payment_status === 'Success';

    const dialog = new frappe.ui.Dialog({
        title: '💳 PayU — Payment Options',
        fields: [{ fieldname: 'actions_html', fieldtype: 'HTML' }]
    });

    const action_css = `
        <style>
            .payu-actions-container {
                display: flex;
                flex-direction: column;
                gap: 12px;
                padding: 8px 4px 4px;
            }
            .payu-action-card {
                display: flex;
                align-items: center;
                gap: 14px;
                padding: 14px 16px;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.18s ease;
                background: #fafafa;
            }
            .payu-action-card:hover {
                background: #f0f4ff;
                border-color: #5a67d8;
                box-shadow: 0 2px 8px rgba(90,103,216,0.12);
            }
            .payu-action-card.disabled {
                opacity: 0.45;
                cursor: not-allowed;
                pointer-events: none;
            }
            .payu-action-icon {
                font-size: 22px;
                width: 36px;
                text-align: center;
            }
            .payu-action-label {
                flex: 1;
            }
            .payu-action-label strong {
                display: block;
                font-size: 14px;
                color: #1a202c;
            }
            .payu-action-label span {
                font-size: 12px;
                color: #718096;
            }
            .payu-action-badge {
                font-size: 11px;
                padding: 2px 8px;
                border-radius: 10px;
                background: #5a67d8;
                color: white;
                font-weight: 600;
            }
        </style>
    `;

    const send_card_class = (is_paid || !has_email) ? 'payu-action-card disabled' : 'payu-action-card';
    const send_hint = is_paid ? 'Payment already completed' : (!has_email ? 'Add email to this record first' : 'Generates link & sends to client');

    const copy_card_class = 'payu-action-card';
    const copy_hint = has_link ? 'Click to copy the existing link' : 'Will generate a new link first';

    const sync_card_class = is_paid ? 'payu-action-card disabled' : 'payu-action-card';
    const sync_hint = is_paid ? 'Payment already completed' : 'Check PayU and update payment status here';

    const action_html = `
        ${action_css}
        <div class="payu-actions-container">
            <div class="${send_card_class}" id="payu-action-send">
                <div class="payu-action-icon">📧</div>
                <div class="payu-action-label">
                    <strong>Send payment link via Email &amp; WhatsApp</strong>
                    <span>${send_hint}</span>
                </div>
                <span class="payu-action-badge">Send</span>
            </div>
            <div class="${copy_card_class}" id="payu-action-copy">
                <div class="payu-action-icon">📋</div>
                <div class="payu-action-label">
                    <strong>Copy payment link to clipboard</strong>
                    <span>${copy_hint}</span>
                </div>
                <span class="payu-action-badge" style="background:#38a169;">Copy</span>
            </div>
            <div class="${sync_card_class}" id="payu-action-sync">
                <div class="payu-action-icon">🔄</div>
                <div class="payu-action-label">
                    <strong>Sync Payment Status from PayU</strong>
                    <span>${sync_hint}</span>
                </div>
                <span class="payu-action-badge" style="background:#d97706;">Sync</span>
            </div>
        </div>
    `;


    dialog.fields_dict.actions_html.$wrapper.html(action_html);
    dialog.show();
    // Remove default primary button — pure action-card UI
    dialog.$wrapper.find('.btn-primary').hide();

    // --- Action: Send via Email & WhatsApp ---
    dialog.$wrapper.find('#payu-action-send').on('click', function() {
        dialog.hide();
        frappe.confirm(
            `Send payment link of <b>₹${frm.doc.service_amount}</b> to <b>${frm.doc.email}</b> via Email & WhatsApp?`,
            async function() {
                const r = await frappe.call({
                    method: 'payu_frappe.api.generate_payment_link_and_send',
                    args: { request_id: frm.doc.name },
                    freeze: true,
                    freeze_message: __('Generating & sending payment link…'),
                });
                if (r.message && r.message.payment_link) {
                    frappe.msgprint({
                        title: __('Payment Link Sent ✅'),
                        message: `Link sent to <b>${frm.doc.email}</b> and WhatsApp.<br><br>
                            <a href="${r.message.payment_link}" target="_blank">${r.message.payment_link}</a>`,
                        indicator: 'green'
                    });
                    frm.reload_doc();
                } else {
                    frappe.msgprint({ title: 'Error', message: 'Could not generate payment link.', indicator: 'red' });
                }
            }
        );
    });

    // --- Action: Copy to Clipboard ---
    dialog.$wrapper.find('#payu-action-copy').on('click', async function() {
        dialog.hide();
        let link = frm.doc.payment_link;

        // If no link yet, generate it first, then copy
        if (!link) {
            frappe.show_alert({ message: __('Generating payment link…'), indicator: 'blue' });
            const r = await frappe.call({
                method: 'payu_frappe.api.generate_payment_link_and_send',
                args: { request_id: frm.doc.name },
                freeze: true,
                freeze_message: __('Generating payment link…'),
            });
            if (r.message && r.message.payment_link) {
                link = r.message.payment_link;
                frm.reload_doc();
            } else {
                frappe.msgprint({ title: 'Error', message: 'Could not generate payment link.', indicator: 'red' });
                return;
            }
        }

        navigator.clipboard.writeText(link).then(function() {
            frappe.show_alert({ message: __('✅ Payment link copied to clipboard!'), indicator: 'green' });
        }).catch(function() {
            frappe.msgprint({ title: 'Copy failed', message: `Please copy manually:<br><br><a href="${link}" target="_blank">${link}</a>`, indicator: 'orange' });
        });
    });

    // --- Action: Sync Payment Status from PayU ---
    dialog.$wrapper.find('#payu-action-sync').on('click', async function() {
        dialog.hide();

        // Show a small dialog to enter the PayU Payment ID
        const sync_dialog = new frappe.ui.Dialog({
            title: '🔄 Sync Payment from PayU',
            fields: [
                {
                    fieldname: 'payment_id_html',
                    fieldtype: 'HTML',
                    options: `
                        <div style="padding: 4px 0 12px;">
                            <p style="font-size:13px;color:#4a5568;margin:0 0 4px;">
                                After payment, PayU shows a <b>Payment ID</b> on their success page.
                            </p>
                            <p style="font-size:12px;color:#718096;margin:0;">
                                Example: <code style="background:#f0f4ff;padding:2px 6px;border-radius:4px;">28126138459</code>
                            </p>
                        </div>`
                },
                {
                    fieldname: 'mihpayid',
                    fieldtype: 'Data',
                    label: 'PayU Payment ID',
                    placeholder: 'Paste the Payment ID from PayU success page',
                    description: 'Leave blank to search automatically by date'
                }
            ],
            primary_action_label: '🔄 Sync Now',
            primary_action: async function(values) {
                sync_dialog.hide();
                const r = await frappe.call({
                    method: 'payu_frappe.payment_reconcile.sync_payu_transactions',
                    args: {
                        itr_submission_name: frm.doc.name,
                        mihpayid: values.mihpayid || null
                    },
                    freeze: true,
                    freeze_message: __('Checking PayU for transaction…'),
                });
                const result = r.message || {};
                if (result.status === 'success') {
                    frappe.msgprint({
                        title: __('✅ Payment Confirmed!'),
                        message: result.message,
                        indicator: 'green'
                    });
                    frm.reload_doc();
                } else if (result.status === 'already_paid') {
                    frappe.show_alert({ message: __('Already marked as Paid.'), indicator: 'blue' });
                } else if (result.status === 'already_logged') {
                    frappe.msgprint({ title: __('Already Logged'), message: result.message, indicator: 'blue' });
                    frm.reload_doc();
                } else if (result.status === 'not_found') {
                    frappe.msgprint({
                        title: __('No Transaction Found'),
                        message: (result.message || '') + '<br><br>Please ensure you entered the correct Payment ID from PayU\'s success page.',
                        indicator: 'orange'
                    });
                } else {
                    frappe.msgprint({
                        title: __('Sync Result'),
                        message: result.message || JSON.stringify(result),
                        indicator: 'red'
                    });
                }
            }
        });
        sync_dialog.show();
    });

} // end open_payu_dialog


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
        const cur_mobile = (frm.doc.mobile_number || "").toString().replace(/\D/g, "").slice(-10);
        const incoming_mobile = (data.mobile_number || "").toString().replace(/\D/g, "").slice(-10);
        
        if (cur_mobile && incoming_mobile === cur_mobile && $body && $body.length > 0) {
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
