frappe.listview_settings['ITR Filing Submission'] = {
    // Force the necessary fields to be available for the formatters
    add_fields: ["full_name", "mobile_number", "pan_number", "email", "regional_manager", "regional_manager_name", "stage_status"],

    formatters: {
        // Fallback formatter to ensure Regional Manager name is NEVER empty in the list
        regional_manager_name(val, df, doc) {
            if (val) return val;
            
            // If the fetch field is empty, but we have a manager ID, show a placeholder or try to fetch
            if (doc.regional_manager) {
                return `<span class="text-muted" data-rm-id="${doc.regional_manager}">Syncing...</span>`;
            }
            return "";
        },

        // Ensure PAN is always uppercase and visible
        pan_number(val) {
            return val ? val.toUpperCase() : "";
        }
    },

    onload(listview) {
        // Simple trick to refresh names if they show "Syncing..."
        setTimeout(() => {
            listview.wrapper.find('[data-rm-id]').each(function() {
                const $span = $(this);
                const rm_id = $span.attr('data-rm-id');
                frappe.db.get_value('User', rm_id, 'full_name', (r) => {
                    if (r && r.full_name) {
                        $span.text(r.full_name).removeClass('text-muted');
                    }
                });
            });
        }, 1000);
    }
};
