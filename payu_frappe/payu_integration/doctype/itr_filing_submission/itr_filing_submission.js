frappe.ui.form.on('ITR Filing Submission', {
    service_amount: function(frm) {
        if (frm.doc.service_amount) {
            frm.set_value('payment_amount', parseInt(frm.doc.service_amount));
        }
    },
    refresh: function(frm) {
        if (!frm.is_new() && frm.doc.service_amount) {
            frm.add_custom_button(__('PayU'), function() { open_payu_dialog(frm); });
        }
        const sc = {'Pending':'orange','Link Generated':'blue','Success':'green','Failed':'red'};
        if (frm.doc.payment_status && sc[frm.doc.payment_status]) {
            frm.set_indicator_formatter('payment_status', function(doc) { return sc[doc.payment_status] || 'grey'; });
        }
        if (frm.doc.mobile_number && !frm.is_new()) {
            frm.add_custom_button(__('WhatsApp'), function() { open_whatsapp_dialog(frm); });
        }
    }
});
function open_payu_dialog(frm) {
    var d = new frappe.ui.Dialog({ title: 'PayU - Payment Options', fields: [{ fieldname: 'actions_html', fieldtype: 'HTML' }] });
    var sc = (frm.doc.payment_status==='Success' || !frm.doc.email) ? 'payu-action-card disabled' : 'payu-action-card';
    var sh = frm.doc.payment_status==='Success' ? 'Payment already completed' : (!frm.doc.email ? 'Add email first' : 'Generates link and sends to client');
    var ch = frm.doc.payment_link ? 'Copy existing link' : 'Will generate a new link first';
    d.fields_dict.actions_html.$wrapper.html('<style>.payu-actions-container{display:flex;flex-direction:column;gap:12px;padding:8px}.payu-action-card{display:flex;align-items:center;gap:14px;padding:14px 16px;border:1px solid #e2e8f0;border-radius:8px;cursor:pointer;background:#fafafa}.payu-action-card:hover{background:#f0f4ff;border-color:#5a67d8}.payu-action-card.disabled{opacity:0.45;cursor:not-allowed;pointer-events:none}.payu-action-icon{font-size:22px;width:36px;text-align:center}.payu-action-label{flex:1}.payu-action-label strong{display:block;font-size:14px;color:#1a202c}.payu-action-label span{font-size:12px;color:#718096}.payu-action-badge{font-size:11px;padding:2px 8px;border-radius:10px;color:white;font-weight:600}</style><div class="payu-actions-container"><div class="' + sc + '" id="payu-action-send"><div class="payu-action-icon">&#x1F4E7;</div><div class="payu-action-label"><strong>Send payment link via Email &amp; WhatsApp</strong><span>' + sh + '</span></div><span class="payu-action-badge" style="background:#5a67d8">Send</span></div><div class="payu-action-card" id="payu-action-copy"><div class="payu-action-icon">&#x1F4CB;</div><div class="payu-action-label"><strong>Copy payment link to clipboard</strong><span>' + ch + '</span></div><span class="payu-action-badge" style="background:#38a169">Copy</span></div></div>');
    d.show(); d.$wrapper.find('.btn-primary').hide();
    d.$wrapper.find('#payu-action-send').on('click', function() {
        d.hide();
        frappe.confirm('Send payment link of Rs.' + frm.doc.service_amount + ' to ' + frm.doc.email + ' via Email & WhatsApp?', async function() {
            var r = await frappe.call({ method: 'payu_frappe.api.generate_payment_link_and_send', args: { request_id: frm.doc.name }, freeze: true, freeze_message: __('Generating...') });
            if (r.message && r.message.payment_link) { frappe.msgprint({ title: 'Payment Link Sent', message: 'Link: ' + r.message.payment_link, indicator: 'green' }); frm.reload_doc(); }
            else frappe.msgprint({ title: 'Error', message: 'Could not generate payment link.', indicator: 'red' });
        });
    });
    d.$wrapper.find('#payu-action-copy').on('click', async function() {
        d.hide();
        var link = frm.doc.payment_link;
        if (!link) {
            var r = await frappe.call({ method: 'payu_frappe.api.generate_payment_link_and_send', args: { request_id: frm.doc.name }, freeze: true });
            if (r.message && r.message.payment_link) { link = r.message.payment_link; frm.reload_doc(); }
            else { frappe.msgprint({ title: 'Error', message: 'Failed to generate link.', indicator: 'red' }); return; }
        }
        navigator.clipboard.writeText(link).then(function() { frappe.show_alert({ message: 'Payment link copied!', indicator: 'green' }); });
    });
}
function open_whatsapp_dialog(frm) {
    var dialog = new frappe.ui.Dialog({ title: 'WhatsApp: ' + frm.doc.full_name, fields: [{ fieldname: 'chat_widget', fieldtype: 'HTML' }] });
    var $w = dialog.fields_dict.chat_widget.$wrapper;
    $w.html('<style>.wa-popup-container{background-color:#e5ddd5;height:500px;display:flex;flex-direction:column;overflow:hidden;border-radius:4px}.wa-popup-messages{flex:1;padding:15px;overflow-y:auto;display:flex;flex-direction:column;gap:8px}.wa-msg{max-width:80%;padding:8px 12px;border-radius:8px;font-size:14px}.wa-msg.outbound{align-self:flex-end;background-color:#dcf8c6}.wa-msg.inbound{align-self:flex-start;background-color:#fff}.wa-msg-time{font-size:10px;color:#999;text-align:right;margin-top:2px}.wa-chat-footer{background-color:#f0f0f0;padding:10px;display:flex;align-items:center;gap:10px}.wa-input-container{flex:1;background:white;border-radius:20px;padding:5px 15px;display:flex;align-items:center;gap:10px}.wa-input-container input{border:none;width:100%;outline:none;font-size:14px}.wa-send-btn{background-color:#128C7E;color:white;width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer}.wa-footer-icon{color:#888;font-size:18px;cursor:pointer}</style><div class="wa-popup-container"><div class="wa-popup-messages" id="wa-dialog-body"><div style="text-align:center;color:#888;margin-top:100px">Loading...</div></div><div class="wa-chat-footer"><i class="fa fa-paperclip wa-footer-icon" id="wa-attach-trigger"></i><i class="fa fa-list-alt wa-footer-icon" id="wa-template-trigger"></i><div class="wa-input-container"><i class="fa fa-smile-o wa-footer-icon"></i><input type="text" id="wa-dialog-input" placeholder="Type a message"></div><div class="wa-send-btn" id="wa-dialog-send"><i class="fa fa-paper-plane" style="font-size:14px;margin-left:-2px"></i></div></div></div>');
    dialog.show();
    var $b=$w.find('#wa-dialog-body'),$i=$w.find('#wa-dialog-input'),$s=$w.find('#wa-dialog-send'),$a=$w.find('#wa-attach-trigger'),$t=$w.find('#wa-template-trigger');
    fetch_wa_history(frm,$b);
    $s.on('click',function(){send_wa_msg_popup(frm,$w);});
    $i.on('keypress',function(e){if(e.which===13)send_wa_msg_popup(frm,$w);});
    $a.on('click',function(){new frappe.ui.FileUploader({doctype:"ITR Filing Submission",docname:frm.doc.name,folder:"Home/Attachments",make_attachments_public:true,on_success:function(file){send_wa_msg_popup(frm,$w,'Sent a file: '+file.file_name,window.location.origin+file.file_url);}});});
    $t.on('click',function(){frappe.call({method:'payu_frappe.api.get_picky_assist_templates',callback:function(r){if(r.message&&r.message.length>0)show_template_popup(frm,$w,r.message);else frappe.msgprint(__('No templates found.'));}});});
    frappe.realtime.on('whatsapp_notification',function(data){var c=(frm.doc.mobile_number||"").toString().replace(/\D/g,"").slice(-10),n=(data.mobile_number||"").toString().replace(/\D/g,"").slice(-10);if(c&&n===c&&$b&&$b.length>0)fetch_wa_history(frm,$b,true);});
}
function show_template_popup(frm,wa_wrapper,templates){var d=new frappe.ui.Dialog({title:__('Send WhatsApp Template'),fields:[{label:__('Select Template'),fieldname:'template',fieldtype:'Select',options:templates.map(function(t){return t.template_name;}),reqd:1,on_change:function(){var sel=templates.find(function(t){return t.template_name===d.get_value('template');});d.set_df_property('preview','options','<b>Preview:</b><br>'+(sel.message_body||'No preview'));var m=(sel.message_body||"").match(/{{\d+}}/g);var c=m?(new Set(m)).size:0;for(var i=1;i<=5;i++)d.set_df_property('p'+i,'hidden',i>c);}},{fieldname:'preview',fieldtype:'HTML'},{fieldname:'p1',fieldtype:'Data',label:__('Value for {{1}}'),hidden:1},{fieldname:'p2',fieldtype:'Data',label:__('Value for {{2}}'),hidden:1},{fieldname:'p3',fieldtype:'Data',label:__('Value for {{3}}'),hidden:1},{fieldname:'p4',fieldtype:'Data',label:__('Value for {{4}}'),hidden:1},{fieldname:'p5',fieldtype:'Data',label:__('Value for {{5}}'),hidden:1}],primary_action_label:__('Send Template'),primary_action:function(values){var sel=templates.find(function(t){return t.template_name===values.template;});var p=[];if(values.p1)p.push(values.p1);if(values.p2)p.push(values.p2);if(values.p3)p.push(values.p3);if(values.p4)p.push(values.p4);if(values.p5)p.push(values.p5);send_wa_msg_popup(frm,wa_wrapper,null,null,sel.template_id,p);d.hide();}});d.show();}
function fetch_wa_history(frm,body,scroll){frappe.call({method:'payu_frappe.api.get_whatsapp_history',args:{itr_submission:frm.doc.name},callback:function(r){body.empty();if(r.message&&r.message.length>0){r.message.forEach(function(msg){var a=(msg.direction||"").toLowerCase()==='inbound'?'inbound':'outbound';var t=frappe.datetime.get_time(msg.creation);var c=msg.message||"";if(msg.media_url)c+='<br><a href="'+msg.media_url+'" target="_blank" style="color:#075E54;font-weight:bold">[View Attachment]</a>';body.append('<div class="wa-msg '+a+'"><div>'+c+'</div><div class="wa-msg-time">'+t+'</div></div>');});if(scroll)body.scrollTop(body[0].scrollHeight);else setTimeout(function(){body.scrollTop(body[0].scrollHeight);},200);}else body.append('<div style="text-align:center;color:#999;margin-top:50px">No messages yet</div>');}});}
function send_wa_msg_popup(frm,wrapper,override_text,media_url,template_id,template_params){var $i=wrapper.find('#wa-dialog-input');var text=override_text||$i.val().trim();if(!text&&!media_url&&!template_id)return;if(!override_text&&!template_id)$i.val('').prop('disabled',true);frappe.call({method:'payu_frappe.api.send_manual_whatsapp',args:{docname:frm.doc.name,message:text,media_url:media_url||null,template_id:template_id||null,template_params:template_params||null},callback:function(r){$i.prop('disabled',false).focus();var s=r.message?(r.message.status||"").toLowerCase():"";var $b=wrapper.find('#wa-dialog-body');if(s==='success')fetch_wa_history(frm,$b,true);else{frappe.show_alert({message:__('WhatsApp: ')+((r.message&&r.message.error)?r.message.error:'Unknown error'),indicator:'red'});fetch_wa_history(frm,$b,true);}}});}
