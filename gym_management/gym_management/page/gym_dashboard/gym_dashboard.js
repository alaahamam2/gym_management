frappe.pages["gym-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Gym Dashboard"),
		single_column: true,
	});
	const esc = frappe.utils.escape_html;
	const $body = $('<div class="gym-dashboard"></div>').appendTo(page.main);

	const card = (label, value, href) => `
		<a href="${href}" style="flex:1;min-width:200px;padding:16px 20px;border:1px solid var(--border-color);
			border-radius:var(--border-radius-md);background:var(--card-bg);text-decoration:none;">
			<div class="text-muted" style="font-size:12px;">${label}</div>
			<div style="font-size:28px;font-weight:600;color:var(--text-color);">${value}</div>
		</a>`;

	const time = (t) => esc((t || "").toString().slice(0, 5));

	const render = (d) => {
		const rows = d.sessions
			.map((s) => {
				const pct = cint(s.fill_rate);
				const colour = pct >= 100 ? "var(--red-500)" : pct >= 70 ? "var(--orange-500)" : "var(--green-500)";
				return `<tr>
					<td><a href="/app/class-session/${encodeURIComponent(s.name)}">${esc(s.gym_class)}</a></td>
					<td>${time(s.start_time)} - ${time(s.end_time)}</td>
					<td>${esc(s.trainer_name || "")}</td>
					<td>${cint(s.booked_count)} / ${cint(s.capacity)}</td>
					<td style="min-width:160px;">
						<div style="background:var(--control-bg);border-radius:4px;height:8px;">
							<div style="width:${Math.min(pct, 100)}%;height:8px;border-radius:4px;background:${colour};"></div>
						</div>
						<span class="text-muted small">${pct}%</span>
					</td>
				</tr>`;
			})
			.join("");

		$body.html(`
			<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:24px;">
				${card(__("Active Members"), d.active_members, "/app/gym-membership?status=Active&docstatus=1")}
				${card(__("Expiring in 7 Days"), d.expiring_soon, "/app/query-report/Membership Expiry Report")}
				${card(__("Sessions Today"), d.sessions.length, "/app/class-session?session_date=" + frappe.datetime.get_today())}
				${card(__("Revenue This Month"), `${format_currency(d.revenue).replace(/[^\d.,]/g, "").trim()} ${esc(d.currency || "")}`, "/app/sales-invoice")}
			</div>
			<h5>${__("Today's Sessions")}</h5>
			${
				rows
					? `<table class="table table-bordered">
						<thead><tr><th>${__("Class")}</th><th>${__("Time")}</th><th>${__("Trainer")}</th>
						<th>${__("Booked")}</th><th>${__("Fill Rate")}</th></tr></thead>
						<tbody>${rows}</tbody></table>`
					: `<p class="text-muted">${__("No sessions scheduled for today.")}</p>`
			}
		`);
	};

	const load = () =>
		frappe.call({ method: "gym_management.api.get_dashboard_data" }).then((r) => render(r.message));

	page.set_primary_action(__("Refresh"), load, "refresh");
	load();
};