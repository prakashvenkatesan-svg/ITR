frappe.listview_settings['ITR Filing Submission'] = {
    // Explicitly add fields for the formatters to use
    add_fields: ["full_name", "mobile_number", "pan_number", "email", "regional_manager", "regional_manager_name", "stage_status"],

    formatters: {
        // Fallback: If Regional Manager field is present but Name field is empty, show the ID
        regional_manager_name(val, df, doc) {
            if (val) return val;
            if (doc.regional_manager) {
                return `<span class="text-muted" data-rm-id="${doc.regional_manager}">${doc.regional_manager.split('@')[0]}</span>`;
            }
            return "";
        },

        pan_number(val) {
            return val ? val.toUpperCase() : "";
        }
    },

    onload(listview) {
        // Only show the Bulk Reassign button to System Managers / Administrators
        if (!frappe.user.has_role("System Manager")) return;

        listview.page.add_action_item(__("Reassign RM"), function() {
            const selected = listview.get_checked_items();
            if (!selected || selected.length === 0) {
                frappe.msgprint({
                    title: __("No Records Selected"),
                    message: __("Please select one or more records to reassign."),
                    indicator: "orange"
                });
                return;
            }

            const docnames = selected.map(d => d.name);

            // Build RM options from the fixed pool
            const RM_POOL = [
                "padmapriya.s@aionioncapital.com",
                "srinivasan.hs@aionioncapital.com",
                "umeshkumar.s@aionioncapital.com",
                "bagiayalakshmi.p@aionioncapital.com",
                "abdulrahim.p@aionioncapital.com",
                "nethaji.a@aionioncapital.com",
                "meenatshisundharesh.vm@aionioncapital.com"
            ];

            const dialog = new frappe.ui.Dialog({
                title: `🔁 Bulk Reassign RM — ${docnames.length} record(s)`,
                fields: [
                    {
                        fieldname: "info_html",
                        fieldtype: "HTML",
                        options: `
                            <div style="background:#fff8e1;border-left:4px solid #f59e0b;padding:10px 14px;border-radius:4px;margin-bottom:12px;font-size:13px;">
                                <strong>⚠️ Manual Override</strong><br>
                                This will forcibly reassign <strong>${docnames.length}</strong> selected record(s) to the chosen RM.
                                The assignment method will be changed to <em>Manual Assign</em> on all selected records.
                            </div>
                        `
                    },
                    {
                        fieldname: "target_rm",
                        fieldtype: "Select",
                        label: __("Assign To (Regional Manager)"),
                        options: [""].concat(RM_POOL).join("\n"),
                        reqd: 1
                    }
                ],
                primary_action_label: __("Reassign"),
                primary_action(values) {
                    if (!values.target_rm) {
                        frappe.msgprint(__("Please select a Regional Manager."));
                        return;
                    }
                    dialog.hide();

                    frappe.confirm(
                        `Reassign <b>${docnames.length}</b> record(s) to <b>${values.target_rm}</b>?`,
                        function() {
                            frappe.call({
                                method: "payu_frappe.api.bulk_reassign_rm",
                                args: {
                                    docnames: docnames,
                                    target_rm: values.target_rm
                                },
                                freeze: true,
                                freeze_message: __("Reassigning records…"),
                                callback(r) {
                                    if (r.message && r.message.success) {
                                        frappe.show_alert({
                                            message: `✅ ${r.message.message}`,
                                            indicator: "green"
                                        }, 6);
                                        listview.refresh();
                                    } else {
                                        frappe.msgprint({
                                            title: __("Reassignment Failed"),
                                            message: r.message ? r.message.message : __("An unknown error occurred."),
                                            indicator: "red"
                                        });
                                    }
                                }
                            });
                        }
                    );
                }
            });

            dialog.show();
        });
    }
};
