frappe.listview_settings['ITR Filing Submission'] = {
    // -----------------------------------------------------------------------
    // Ensure the list always loads fresh (bypass Frappe's route cache)
    // -----------------------------------------------------------------------
    onload: function (listview) {
        // Clear all filters once on load to ensure everyone is visible.
        if (listview.filter_area && !listview.list_view_filters_cleared) {
            listview.filter_area.clear_filters();
            listview.list_view_filters_cleared = true;
        }
        
        // Ensure standard sorting by ID Descending
        listview.sort_by = 'name';
        listview.sort_order = 'desc';
    },

    // -----------------------------------------------------------------------
    // Additional columns in list view
    // -----------------------------------------------------------------------
    add_fields: ['payment_status', 'stage_status', 'regional_manager'],

    // -----------------------------------------------------------------------
    // Formatters for list columns
    // -----------------------------------------------------------------------
    formatters: {
        payment_status: function (value) {
            const colors = {
                'Pending': 'var(--orange-500)',
                'Link Generated': 'var(--blue-500)',
                'Success': 'var(--green-500)',
                'Failed': 'var(--red-500)',
            };
            const color = colors[value] || 'var(--gray-500)';
            return `<span style="color: ${color}; font-weight: 600;">${value || ''}</span>`;
        },
        regional_manager: function(value) {
            // Show just the Name part of the email/ID in BOLD
            if (!value) return "";
            const name = value.split('@')[0].replace(/\./g, ' ');
            return `<span style="font-weight: 600; color: #333;">${name.charAt(0).toUpperCase() + name.slice(1)}</span>`;
        }
    },
};
