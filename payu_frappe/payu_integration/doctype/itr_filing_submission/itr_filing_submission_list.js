frappe.listview_settings['ITR Filing Submission'] = {
    // -----------------------------------------------------------------------
    // Default page length — show all 2500 so pagination is rarely needed,
    // but still allow the user to switch via the bottom controls.
    // -----------------------------------------------------------------------
    // NOTE: Frappe reads this ONCE on first load.  To reset an existing saved
    // user preference, go to List View → ⋮ → Reset to default.
    page_length: 20,

    // -----------------------------------------------------------------------
    // Ensure the list always loads fresh (bypass Frappe's route cache)
    // -----------------------------------------------------------------------
    onload: function (listview) {
        // Clear all filters once on load to ensure everyone is visible.
        // This fixes the "record not reflected" issue if stale filters are present.
        if (listview.filter_area && !listview.list_view_filters_cleared) {
            listview.filter_area.clear_filters();
            listview.list_view_filters_cleared = true;
        }
        
        // Ensure standard sorting
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
            // Show initials + name if needed, or just capitalize the email name
            if (!value) return "";
            // If it's an email like john@google.com, make it 'John (google)'
            const name = value.split('@')[0];
            return `<span style="font-weight: 500;">${name.charAt(0).toUpperCase() + name.slice(1)}</span>`;
        }
    },
};
