frappe.listview_settings['ITR Filing Submission'] = {
    // Standard page length
    page_length: 20,

    // -----------------------------------------------------------------------
    // Additional columns in list view
    // -----------------------------------------------------------------------
    add_fields: ['payment_status', 'stage_status', 'regional_manager_name'],

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
        regional_manager_name: function(value) {
            // Show the fetched Full Name in a clean format
            if (!value) return "";
            return `<span style="font-weight: 500; color: #333;">${value}</span>`;
        }
    }
};
