frappe.ui.form.on("Class Booking", {
	setup(frm) {
		frm.set_query("class_session", () => ({
			filters: { status: "Scheduled", session_date: [">=", frappe.datetime.get_today()] },
		}));
		frm.set_query("member", () => ({ filters: { status: ["!=", "Blacklisted"] } }));
	},

	refresh(frm) {
		frm.toggle_enable(["class_session", "member"], frm.is_new());
		frm.trigger("show_spots");
		frm.trigger("set_status_indicator");
		frm.trigger("add_buttons");
	},

	class_session(frm) {
		frm.trigger("show_spots");
	},

	show_spots(frm) {
		frm.dashboard.clear_headline();
		const session = frm.doc.class_session;
		if (!session) return;
		frappe.db.get_value("Class Session", session, ["capacity", "booked_count"]).then(({ message }) => {
			if (!message || session !== frm.doc.class_session) return; // another session was picked meanwhile
			const left = Math.max(cint(message.capacity) - cint(message.booked_count), 0);
			if (left > 0) {
				frm.dashboard.set_headline_alert(__("{0} of {1} spots left", [left, message.capacity]), "green");
			} else {
				frm.dashboard.set_headline_alert(__("Session is full. New bookings join the waitlist"), "orange");
			}
		});
	},

	set_status_indicator(frm) {
		if (frm.is_new()) return;
		const colours = { Booked: "green", Waitlisted: "orange", Attended: "blue", "No Show": "red", Cancelled: "gray" };
		frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status] || "gray");
	},

	add_buttons(frm) {
		if (frm.is_new() || frm.is_dirty()) return;
		const change = (status) => frm.set_value("status", status).then(() => frm.save());
		if (frm.doc.status === "Booked") {
			frm.add_custom_button(__("Mark Attended"), () => change("Attended"), __("Actions"));
			frm.add_custom_button(__("No Show"), () => change("No Show"), __("Actions"));
		}
		if (["Booked", "Waitlisted"].includes(frm.doc.status)) {
			frm.add_custom_button(
				__("Cancel Booking"),
				() => frappe.confirm(__("Cancel this booking?"), () => change("Cancelled")),
				__("Actions")
			);
		}
	},
});