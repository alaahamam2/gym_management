frappe.ui.form.on('Class Booking', {
    class_session: function(frm) {
        if (frm.doc.class_session) {
            frappe.db.get_value('Class Session', frm.doc.class_session, ['session_date', 'start_time', 'capacity', 'booked_count'], function(r) {
                if (r) {
                    console.log("Session loaded:", r);
                }
            });
        }
    }
});
frappe.ui.form.on('Class Booking', {
    class_session: function(frm) {
        if (frm.doc.class_session) {
            frappe.db.get_value('Class Session', frm.doc.class_session, ['session_date', 'start_time', 'capacity', 'booked_count'], function(r) {
                if (r) {
                    let available = (r.capacity || 0) - (r.booked_count || 0);
                    if (available <= 0) {
                        frappe.show_alert({
                            message: __('This session is full. Booking will be added to Waitlist.'),
                            indicator: 'orange'
                        });
                    } else {
                        frappe.show_alert({
                            message: __('Available spots: ') + available,
                            indicator: 'green'
                        });
                    }
                }
            });
        }
    }
});