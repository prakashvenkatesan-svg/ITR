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
        // Clear all filters on load to ensure all 11+ clients are visible.
        // This fixes the "record not reflected" issue if stale filters are present.
        if (listview.filter_area) {
            listview.filter_area.clear_filters();
        }
        
        // Force page length and sort order
        listview.page_length = 20;
        listview.sort_by = 'name';
        listview.sort_order = 'desc';
        
        listview.refresh();
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
    },
};
