import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
    add_to_date,
    cint,
    get_datetime,
    get_first_day,
    getdate,
    now_datetime,
    nowdate,
    to_timedelta,
)

# status -> statuses it may move to (Waitlisted -> Booked is system-only, see promote_waitlist)
ALLOWED_TRANSITIONS = {
    "Booked": {"Attended", "No Show", "Cancelled"},
    "Waitlisted": {"Cancelled"},
    "Attended": set(),
    "No Show": set(),
    "Cancelled": set(),
}


def session_start(session):
    return get_datetime(session.session_date) + to_timedelta(session.start_time)


def lock_session(name):
    """Row lock (SELECT ... FOR UPDATE) on the session. Concurrent bookings queue up here,
    and a locking read always returns the latest committed values."""
    session = frappe.db.get_value(
        "Class Session",
        name,
        ["name", "status", "session_date", "start_time", "capacity", "booked_count"],
        as_dict=True,
        for_update=True,
    )
    if not session:
        frappe.throw(_("Class Session {0} not found.").format(name))
    return session


def adjust_booked_count(session, delta):
    # Atomic update in SQL: no read-modify-write, no re-validation of the session
    frappe.db.sql(
        "update `tabClass Session` set booked_count = greatest(booked_count + %s, 0) where name = %s",
        (delta, session),
    )


def uses_allowance(membership):
    """True when the membership's plan limits the number of classes."""
    plan = frappe.db.get_value("Gym Membership", membership, "membership_plan")
    return cint(frappe.db.get_value("Membership Plan", plan, "classes_included")) > 0


class ClassBooking(Document):
    def validate(self):
        prev = self.get_doc_before_save()
        self.flags.prev_status = prev.status if prev else None
        if prev:
            self.validate_status_change(prev)
        else:
            self.validate_new_booking()

    def after_insert(self):
        if self.status == "Booked":
            self.confirm_seat()

    def on_update(self):
        prev = self.flags.prev_status
        if prev == "Booked" and self.status == "Cancelled":
            self.release_seat()
        elif prev == "Waitlisted" and self.status == "Booked":
            self.confirm_seat()

    # ---------- validation ----------

    def validate_new_booking(self):
        session = lock_session(self.class_session)

        if session.status != "Scheduled":
            frappe.throw(_("Session {0} is {1} and cannot be booked.").format(session.name, session.status))
        if session_start(session) <= now_datetime():
            frappe.throw(_("This session has already started."))

        if frappe.db.exists(
            "Class Booking",
            {
                "class_session": self.class_session,
                "member": self.member,
                "status": ["!=", "Cancelled"],
                "name": ["!=", self.name],
            },
        ):
            frappe.throw(_("Member {0} already has a booking for this session.").format(self.member))

        self.membership = self.get_valid_membership(session.session_date)
        if not self.membership:
            frappe.throw(
                _("Member {0} has no active membership on {1} (it may be expired, frozen, cancelled, or out of classes).").format(
                    self.member, session.session_date
                )
            )

        if cint(session.booked_count) < cint(session.capacity):
            self.status = "Booked"
        elif cint(frappe.db.get_single_value("Gym Settings", "enable_waitlist")):
            self.status = "Waitlisted"
            frappe.msgprint(_("The session is full. The booking was added to the waitlist."), alert=True)
        else:
            frappe.throw(_("This session is fully booked."))

        self.booked_on = now_datetime()
        self.cancelled_on = None

    def validate_status_change(self, prev):
        if prev.class_session != self.class_session or prev.member != self.member:
            frappe.throw(_("Session and Member cannot be changed. Cancel this booking and create a new one."))
        if prev.status == self.status:
            return

        promoting = prev.status == "Waitlisted" and self.status == "Booked" and self.flags.promoting
        if not promoting and self.status not in ALLOWED_TRANSITIONS.get(prev.status, set()):
            frappe.throw(_("A booking cannot move from {0} to {1}.").format(prev.status, self.status))

        session = lock_session(self.class_session)
        if self.status == "Cancelled":
            if session_start(session) <= now_datetime():
                frappe.throw(_("A session that has started cannot be cancelled."))
            self.cancelled_on = now_datetime()
            self.flags.late_cancel = self.is_late_cancel(session)
        elif self.status in ("Attended", "No Show"):
            if getdate(session.session_date) > getdate(nowdate()):
                frappe.throw(_("Attendance cannot be marked before the session date."))
            if self.status == "No Show":
                self.warn_if_over_no_show_limit()

    def get_valid_membership(self, session_date):
        """Membership valid ON THE SESSION DATE (not frozen, not expired, classes left). None if there is none."""
        candidates = frappe.get_all(
            "Gym Membership",
            filters={
                "member": self.member,
                "docstatus": 1,
                "status": ["in", ["Active", "Frozen"]],
                "start_date": ["<=", session_date],
                "end_date": [">=", session_date],
            },
            pluck="name",
            order_by="start_date desc",
        )
        for name in candidates:
            if frappe.get_doc("Gym Membership", name).is_frozen_on(session_date):
                continue
            if uses_allowance(name):
                remaining = frappe.db.get_value("Gym Membership", name, "classes_remaining", for_update=True)
                if cint(remaining) <= 0:
                    continue
            return name
        return None

    def is_late_cancel(self, session):
        hours = cint(frappe.db.get_single_value("Gym Settings", "cancellation_window_hours"))
        return now_datetime() > add_to_date(session_start(session), hours=-hours)

    def warn_if_over_no_show_limit(self):
        limit = cint(frappe.db.get_single_value("Gym Settings", "no_show_limit"))
        if not limit:
            return
        count = 1 + frappe.db.count(
            "Class Booking",
            {"member": self.member, "status": "No Show", "modified": [">=", get_first_day(nowdate())]},
        )
        if count > limit:
            frappe.msgprint(
                _("Member {0} has {1} no-shows this month (limit {2}).").format(self.member, count, limit),
                indicator="orange",
                alert=True,
            )

    # ---------- seats, classes and waitlist ----------

    def confirm_seat(self):
        adjust_booked_count(self.class_session, 1)
        if uses_allowance(self.membership):
            frappe.db.sql(
                "update `tabGym Membership` set classes_remaining = classes_remaining - 1 where name = %s",
                self.membership,
            )

    def release_seat(self):
        adjust_booked_count(self.class_session, -1)
        # Cancelling inside the cancellation window forfeits the class
        if not self.flags.late_cancel and uses_allowance(self.membership):
            frappe.db.sql(
                "update `tabGym Membership` set classes_remaining = classes_remaining + 1 where name = %s",
                self.membership,
            )
        self.promote_waitlist()

    def promote_waitlist(self):
        session = lock_session(self.class_session)
        free = cint(session.capacity) - cint(session.booked_count)
        if free <= 0 or session.status != "Scheduled":
            return

        waiting = frappe.get_all(
            "Class Booking",
            filters={"class_session": session.name, "status": "Waitlisted"},
            pluck="name",
            order_by="booked_on asc, creation asc",
        )
        for name in waiting:
            if free <= 0:
                break
            booking = frappe.get_doc("Class Booking", name)
            membership = booking.get_valid_membership(session.session_date)
            if not membership:  # their membership lapsed meanwhile: skip, keep them waitlisted
                continue
            booking.membership = membership
            booking.status = "Booked"
            booking.flags.promoting = True
            booking.save(ignore_permissions=True)
            booking.notify_promotion()
            free -= 1

    def notify_promotion(self):
        email = frappe.db.get_value("Gym Member", self.member, "email")
        if not email:
            return
        try:
            frappe.sendmail(
                recipients=[email],
                subject=_("A spot opened up in your class"),
                message=_("Good news! Your waitlisted booking {0} is now confirmed.").format(self.name),
                reference_doctype=self.doctype,
                reference_name=self.name,
            )
        except Exception:
            frappe.log_error(title="Waitlist promotion email failed")