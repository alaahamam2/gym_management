frappe.listview_settings["Class Session"] = {
	add_fields: ["status", "booked_count", "capacity"],
	get_indicator(doc) {
		const colours = { Scheduled: "blue", Completed: "green", Cancelled: "gray" };
		return [__(doc.status), colours[doc.status] || "gray", "status,=," + doc.status];
	},
	formatters: {
		booked_count(value, df, doc) {
			return `${value || 0}/${doc.capacity || 0}`;
		},
	},
};