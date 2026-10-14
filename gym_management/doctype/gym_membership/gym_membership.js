frappe.ui.form.on('Gym Membership', {
    membership_plan: function(frm) {
        if (frm.doc.membership_plan) {
            frappe.db.get_value('Membership Plan', frm.doc.membership_plan, ['duration_type', 'duration_value', 'price'], function(r) {
                if (r) {
                    if (r.price && !frm.doc.amount) {
                        frm.set_value('amount', r.price);
                    }
                    calculate_end_date(frm, r.duration_type, r.duration_value);
                }
            });
        }
    },
    start_date: function(frm) {
        if (frm.doc.membership_plan && frm.doc.start_date) {
            frappe.db.get_value('Membership Plan', frm.doc.membership_plan, ['duration_type', 'duration_value'], function(r) {
                if (r) {
                    calculate_end_date(frm, r.duration_type, r.duration_value);
                }
            });
        }
    }
});

function calculate_end_date(frm, duration_type, duration_value) {
    if (!frm.doc.start_date || !duration_type) return;

    let start_date = frappe.datetime.str_to_obj(frm.doc.start_date);
    let end_date;

    if (duration_type === 'Days') {
        end_date = frappe.datetime.add_days(start_date, duration_value);
    } else if (duration_type === 'Months') {
        end_date = frappe.datetime.add_months(start_date, duration_value);
    } else if (duration_type === 'Class Pack') {
        end_date = frappe.datetime.add_days(start_date, 365);
    }

    if (end_date) {
        frm.set_value('end_date', frappe.datetime.obj_to_str(end_date));
    }
}