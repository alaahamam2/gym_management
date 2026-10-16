frappe.pages["front-desk-checkin"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Front Desk Check-in"),
		single_column: true,
	});
	const esc = frappe.utils.escape_html;
	const $root = $(`
		<div style="max-width:640px;margin:0 auto;">
			<input type="text" class="form-control input-lg gym-q" autocomplete="off"
				placeholder="${__("Search by name, phone, or scan the member QR")}">
			<div class="gym-results" style="margin-top:8px;"></div>
			<div class="gym-banner" style="margin-top:16px;"></div>
		</div>`).appendTo(page.main);
	const $q = $root.find(".gym-q");
	const $results = $root.find(".gym-results");
	const $banner = $root.find(".gym-banner");
	let results = [];

	const reset = () => {
		results = [];
		$results.empty();
		$banner.empty();
		$q.val("").focus();
	};

	const show_banner = (s) => {
		const ok = !!s.allowed;
		const c = ok
			? { bg: "#e7f6ec", border: "#2e9e5b", text: "#14532d" }
			: { bg: "#fdecec", border: "#d64545", text: "#7f1d1d" };
		$banner.html(`
			<div style="padding:20px;border-radius:10px;border:2px solid ${c.border};background:${c.bg};color:${c.text};">
				<div style="font-size:24px;font-weight:700;">${ok ? __("ALLOWED") : __("ENTRY DENIED")}</div>
				<div style="font-size:16px;margin-top:4px;">${esc(s.member_name)} (${esc(s.name)})</div>
				<div style="margin-top:8px;">${esc(s.message)}</div>
				${ok ? `<button class="btn btn-primary btn-lg gym-checkin" style="margin-top:16px;">${__("Check In")}</button>` : ""}
			</div>`);
		$banner.find(".gym-checkin").on("click", function () {
			const $btn = $(this).prop("disabled", true);
			frappe
				.call({ method: "gym_management.api.check_in_member", args: { member: s.name, method: "Front Desk" } })
				.then(
					() => {
						frappe.show_alert({ message: __("{0} checked in", [s.member_name]), indicator: "green" });
						reset();
					},
					() => $btn.prop("disabled", false)
				);
		});
	};

	const select = (member) => {
		$results.empty();
		frappe
			.call({ method: "gym_management.api.get_member_status", args: { member } })
			.then((r) => show_banner(r.message));
	};

	const do_search = (q) => {
		$banner.empty();
		if (q.length < 2) {
			results = [];
			$results.empty();
			return Promise.resolve([]);
		}
		return frappe.call({ method: "gym_management.api.search_members", args: { query: q } }).then((r) => {
			results = r.message || [];
			if (!results.length) {
				$results.html(`<div class="text-muted" style="padding:8px;">${__("No members found")}</div>`);
			} else {
				$results.html(
					results
						.map(
							(m) => `<div class="gym-result" data-name="${esc(m.name)}"
								style="cursor:pointer;padding:10px 12px;border:1px solid var(--border-color);
								border-radius:6px;margin-bottom:6px;background:var(--card-bg);">
								<strong>${esc(m.member_name)}</strong>
								<span class="text-muted">${esc(m.name)} &middot; ${esc(m.phone || "")}</span></div>`
						)
						.join("")
				);
			}
			return results;
		});
	};

	const search = frappe.utils.debounce((q) => do_search(q), 300);

	$q.on("input", () => search($q.val().trim()));
	// a QR scanner types the ID and presses Enter: search right away, open the member if it is unambiguous
	$q.on("keydown", (e) => {
		if (e.key !== "Enter") return;
		do_search($q.val().trim()).then((rs) => {
			if (rs.length === 1) select(rs[0].name);
		});
	});
	$results.on("click", ".gym-result", function () {
		select($(this).data("name"));
	});
	$q.focus();
};