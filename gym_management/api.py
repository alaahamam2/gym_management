import frappe
from frappe import _
from frappe.utils import cint, get_datetime, getdate, now_datetime, to_timedelta

MAX_RANGE_DAYS = 93


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