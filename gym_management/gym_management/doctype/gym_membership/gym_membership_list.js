frappe.listview_settings["Gym Membership"] = {
	add_fields: ["status", "end_date", "docstatus"],
	get_indicator(doc) {
		if (doc.docstatus === 2) return [__("Cancelled"), "gray", "docstatus,=,2"];
		const colours = { Draft: "orange", Active: "green", Frozen: "blue", Expired: "red", Cancelled: "gray" };
		return [__(doc.status), colours[doc.status] || "gray", "status,=," + doc.status];
	},
};