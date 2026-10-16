import frappe
from frappe import _
from frappe.utils import (
    add_days,
    cint,
    get_datetime,
    get_first_day,
    get_last_day,
    getdate,
    now_datetime,
    nowdate,
    strip_html,
    to_timedelta,
)

MAX_RANGE_DAYS = 93
STAFF_ROLES = ["System Manager", "Gym Manager"]
DESK_ROLES = ["System Manager", "Gym Manager", "Front Desk"]


@frappe.whitelist()
def book_class(session, member):
    """Book `member` into `session`.

    Goes through the normal Class Booking controller, so every rule applies: valid membership
    on the session date, no duplicate booking, capacity (row-locked) and waitlist.
    """
    if not session or not member:
        frappe.throw(_("Session and Member are required."))

    booking = frappe.get_doc({"doctype": "Class Booking", "class_session": session, "member": member})
    booking.insert()  # runs with the caller's permissions

    if booking.status == "Waitlisted":
        message = _("The session is full. You were added to the waitlist.")
    else:
        message = _("Your booking is confirmed.")

    return {"booking": booking.name, "status": booking.status, "message": message}


@frappe.whitelist()
def get_available_sessions(date_from, date_to):
    """Upcoming scheduled sessions between two dates, with the number of spots left."""
    date_from, date_to = getdate(date_from), getdate(date_to)
    if date_to < date_from:
        frappe.throw(_("Date To cannot be before Date From."))
    if (date_to - date_from).days > MAX_RANGE_DAYS:
        frappe.throw(_("Please choose a range of at most {0} days.").format(MAX_RANGE_DAYS))

    waitlist_enabled = cint(frappe.db.get_single_value("Gym Settings", "enable_waitlist"))

    sessions = frappe.get_list(  # respects the caller's permissions
        "Class Session",
        filters={"status": "Scheduled", "session_date": ["between", [date_from, date_to]]},
        fields=[
            "name",
            "gym_class",
            "trainer",
            "room",
            "session_date",
            "start_time",
            "end_time",
            "capacity",
            "booked_count",
        ],
        order_by="session_date asc, start_time asc",
    )

    now = now_datetime()
    available = []
    for s in sessions:
        if get_datetime(s.session_date) + to_timedelta(s.start_time) <= now:
            continue  # already started
        spots_left = max(cint(s.capacity) - cint(s.booked_count), 0)
        if spots_left == 0 and not waitlist_enabled:
            continue  # full and nobody can join
        s["spots_left"] = spots_left
        s["is_full"] = spots_left == 0
        available.append(s)

    return available


@frappe.whitelist()
def get_dashboard_data():
    """All numbers for the gym-dashboard page in a single call."""
    frappe.only_for(STAFF_ROLES)
    today = getdate(nowdate())

    active_members = frappe.db.sql(
        """select count(distinct member) from `tabGym Membership`
        where docstatus = 1 and status = 'Active' and end_date >= %s""",
        (today,),
    )[0][0]

    expiring = frappe.db.count(
        "Gym Membership",
        {"docstatus": 1, "status": "Active", "end_date": ["between", [today, add_days(today, 7)]]},
    )

    sessions = frappe.db.sql(
        """select s.name, s.gym_class, s.start_time, s.end_time, s.capacity, s.booked_count, t.trainer_name
        from `tabClass Session` s left join `tabGym Trainer` t on t.name = s.trainer
        where s.session_date = %s and s.status != 'Cancelled' order by s.start_time""",
        (today,),
        as_dict=True,
    )
    for s in sessions:
        s["fill_rate"] = round(cint(s.booked_count) * 100 / s.capacity) if s.capacity else 0

    revenue = frappe.db.sql(
        """select coalesce(sum(grand_total), 0) from `tabSales Invoice`
        where docstatus = 1 and ifnull(gym_membership, '') != '' and posting_date between %s and %s""",
        (get_first_day(today), get_last_day(today)),
    )[0][0]

    company = frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
    currency = frappe.get_cached_value("Company", company, "default_currency") if company else None

    return {
        "active_members": active_members,
        "expiring_soon": expiring,
        "sessions": sessions,
        "revenue": revenue,
        "currency": currency,
    }


@frappe.whitelist()
def search_members(query):
    """Front desk search by name, phone, or member ID (what a QR code encodes)."""
    frappe.only_for(DESK_ROLES)
    query = (query or "").strip()
    if len(query) < 2:
        return []
    if frappe.db.exists("Gym Member", query):  # exact ID, e.g. scanned QR
        return frappe.get_list(
            "Gym Member", filters={"name": query}, fields=["name", "member_name", "phone", "status"]
        )
    like = f"%{query}%"
    return frappe.get_list(
        "Gym Member",
        or_filters=[["member_name", "like", like], ["phone", "like", like], ["name", "like", like]],
        fields=["name", "member_name", "phone", "status"],
        order_by="member_name asc",
        limit_page_length=8,
    )


@frappe.whitelist()
def get_member_status(member):
    """Can this member enter right now? Reuses the exact rules of Gym Check In."""
    frappe.only_for(DESK_ROLES)
    info = frappe.db.get_value("Gym Member", member, ["name", "member_name", "phone"], as_dict=True)
    if not info:
        frappe.throw(_("Member {0} not found.").format(member))

    entry = frappe.get_doc({"doctype": "Gym Check In", "member": member, "check_in_time": now_datetime()})
    result = dict(info)
    try:
        entry.validate_member()
        entry.resolve_membership()
    except frappe.ValidationError as e:
        frappe.clear_messages()
        result.update(allowed=0, message=strip_html(str(e)))
        return result

    m = frappe.db.get_value(
        "Gym Membership", entry.membership, ["name", "membership_plan", "end_date"], as_dict=True
    )
    result.update(
        allowed=1,
        membership=m.name,
        message=_("{0}: valid until {1}").format(m.membership_plan, m.end_date),
    )
    return result


@frappe.whitelist()
def check_in_member(member, method="Front Desk"):
    frappe.only_for(DESK_ROLES)
    entry = frappe.get_doc({"doctype": "Gym Check In", "member": member, "method": method}).insert()
    return {"name": entry.name, "membership": entry.membership}