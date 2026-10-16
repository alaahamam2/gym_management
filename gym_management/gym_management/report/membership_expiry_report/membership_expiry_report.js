frappe.query_reports["Membership Expiry Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("End Date From"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "to_date",
			label: __("End Date To"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), 30),
		},
		{
			fieldname: "membership_plan",
			label: __("Plan"),
			fieldtype: "Link",
			options: "Membership Plan",
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nActive\nFrozen\nExpired\nCancelled",
		},
	],

	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "days_left" && data && data.days_left !== null) {
			if (data.days_left < 0) {
				value = `<span style="color: var(--red-500)">${value}</span>`;
			} else if (data.days_left <= 7) {
				value = `<span style="color: var(--orange-500)">${value}</span>`;
			}
		}
		return value;
	},
};