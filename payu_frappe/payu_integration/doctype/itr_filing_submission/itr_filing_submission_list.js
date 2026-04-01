frappe.listview_settings['ITR Filing Submission'] = {
    // Explicitly add fields for the formatters to use
    add_fields: ["full_name", "mobile_number", "pan_number", "email", "regional_manager", "regional_manager_name", "stage_status"],

    formatters: {
        // Fallback: If Regional Manager field is present but Name field is empty, show the ID
        // (This happens before a record is saved for the first time with the new fetch field)
        regional_manager_name(val, df, doc) {
            if (val) return val;
            if (doc.regional_manager) {
                // Return a span that we can later update or just show the ID
                return `<span class="text-muted" data-rm-id="${doc.regional_manager}">${doc.regional_manager.split('@')[0]}</span>`;
            }
            return "";
        },

        pan_number(val) {
            return val ? val.toUpperCase() : "";
        }
    }
};
