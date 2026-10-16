frappe.views.calendar["Class Session"] = {
	field_map: {
		start: "session_date",
		end: "session_date",
		id: "name",
		title: "gym_class",
	},
	order_by: "session_date",
	filters: [
		{ fieldtype: "Link", fieldname: "gym_class", options: "Gym Class", label: __("Class") },
		{ fieldtype: "Link", fieldname: "trainer", options: "Gym Trainer", label: __("Trainer") },
	],
	get_css_class(data) {
		if (data.status === "Cancelled") return "danger";
		if (data.status === "Completed") return "success";
		return "info";
	},
};