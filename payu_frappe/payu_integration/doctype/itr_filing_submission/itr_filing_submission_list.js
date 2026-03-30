frappe.listview_settings['ITR Filing Submission'] = {
    get_indicator: function (doc) {
        const map = {
            'Pending':        ['orange', 'payment_status,=,Pending'],
            'Link Generated': ['blue',   'payment_status,=,Link Generated'],
            'Success':        ['green',  'payment_status,=,Success'],
            'Failed':         ['red',    'payment_status,=,Failed'],
        };
        return map[doc.payment_status] || ['grey', 'payment_status,=,'];
    },
    onload: function (listview) {
        listview.refresh();
    },
    add_fields: ['payment_status', 'stage_status', 'regional_manager'],
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
