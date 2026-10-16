frappe.ui.form.on("Gym Membership", {
	setup(frm) {
		frm.set_query("membership_plan", () => ({ filters: { is_active: 1 } }));
		frm.set_query("member", () => ({ filters: { status: ["!=", "Blacklisted"] } }));
	},

	refresh(frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("toggle_fields");
		frm.trigger("add_buttons");
	},

	membership_plan(frm) {
		frm.trigger("toggle_fields");
	},

	set_status_indicator(frm) {
		if (frm.is_new()) return;
		const colours = { Draft: "orange", Active: "green", Frozen: "blue", Expired: "red", Cancelled: "gray" };
		const status = frm.doc.docstatus === 2 ? "Cancelled" : frm.doc.status;
		frm.page.set_indicator(__(status), colours[status] || "gray");
	},

	toggle_fields(frm) {
		const submitted = frm.doc.docstatus === 1;
		frm.toggle_display("section_freeze", submitted || (frm.doc.freeze_history || []).length > 0);
		frm.toggle_display("subscription", false); // recurring billing is custom, see DECISIONS.md
		frm.toggle_display("end_date", !frm.is_new());
		frm.toggle_enable(["member", "membership_plan", "start_date"], frm.doc.docstatus === 0);

		// class balance only matters for plans with a class allowance
		const plan = frm.doc.membership_plan;
		if (!plan) return frm.toggle_display("classes_remaining", false);
		if (frm._plan === plan) {
			return frm.toggle_display("classes_remaining", cint(frm._classes_included) > 0);
		}
		frappe.db.get_value("Membership Plan", plan, "classes_included").then(({ message }) => {
			frm._plan = plan;
			frm._classes_included = message.classes_included;
			frm.toggle_display("classes_remaining", cint(message.classes_included) > 0);
		});
	},

	add_buttons(frm) {
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.status === "Active") {
			frm.add_custom_button(__("Freeze"), () => frm.trigger("open_freeze_dialog"), __("Actions"));
		}
		if (["Active", "Expired"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Renew"), () => frm.trigger("renew"), __("Actions"));
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice),
				__("View")
			);
		}
	},

	renew(frm) {
		const today = frappe.datetime.get_today();
		// renewing early starts the day after the current one ends
		const still_running = frm.doc.end_date && frappe.datetime.get_diff(frm.doc.end_date, today) >= 0;
		frappe.new_doc("Gym Membership", {
			member: frm.doc.member,
			membership_plan: frm.doc.membership_plan,
			start_date: still_running ? frappe.datetime.add_days(frm.doc.end_date, 1) : today,
			auto_renew: frm.doc.auto_renew,
		});
	},

	open_freeze_dialog(frm) {
		frappe.db.get_value("Membership Plan", frm.doc.membership_plan, "max_freeze_days").then(({ message }) => {
			const max = cint(message.max_freeze_days);
			const used = (frm.doc.freeze_history || []).reduce((total, row) => total + cint(row.days), 0);
			const left = max - used;
			if (left <= 0) {
				frappe.msgprint(__("This plan allows {0} freeze days and all of them are used.", [max]));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __("Freeze Membership"),
				fields: [
					{
						fieldname: "info",
						fieldtype: "HTML",
						options: `<p class="text-muted">${__("Freeze days left: {0}", [left])}</p>`,
					},
					{ fieldname: "freeze_from", label: __("From"), fieldtype: "Date", default: frappe.datetime.get_today(), reqd: 1 },
					{ fieldname: "freeze_to", label: __("To"), fieldtype: "Date", reqd: 1 },
					{ fieldname: "reason", label: __("Reason"), fieldtype: "Small Text" },
				],
				primary_action_label: __("Freeze"),
				primary_action(values) {
					const days = frappe.datetime.get_diff(values.freeze_to, values.freeze_from) + 1;
					if (days < 2) {
						frappe.msgprint(__("Freeze To must be after Freeze From."));
						return;
					}
					if (days > left) {
						frappe.msgprint(__("You can freeze at most {0} more days.", [left]));
						return;
					}
					frm.add_child("freeze_history", {
						freeze_from: values.freeze_from,
						freeze_to: values.freeze_to,
						reason: values.reason,
					});
					frm.refresh_field("freeze_history");
					dialog.hide();
					frm.save("Update");
				},
			});
			dialog.show();
		});
	},
});