import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, now_datetime


class GymCheckIn(Document):
    def validate(self):
        self.check_in_time = self.check_in_time or now_datetime()
        self.validate_times()
        self.validate_member()
        self.resolve_membership()
        if self.is_new():
            self.validate_class_booking()

    def after_insert(self):
        self.mark_booking_attended()

    def validate_times(self):
        if self.check_out_time and get_datetime(self.check_out_time) < get_datetime(self.check_in_time):
            frappe.throw(_("Check Out Time cannot be before Check In Time."))

    def validate_member(self):
        if frappe.db.get_value("Gym Member", self.member, "status") == "Blacklisted":
            frappe.throw(_("Entry denied: member {0} is blacklisted.").format(self.member))

    def resolve_membership(self):
        """Find the membership valid on the check-in day, or block entry with a clear reason."""
        day = getdate(self.check_in_time)
        memberships = frappe.get_all(
            "Gym Membership",
            filters={"member": self.member, "docstatus": ["in", [1, 2]]},
            fields=["name", "status", "docstatus", "start_date", "end_date"],
            order_by="end_date desc",
        )
        if not memberships:
            frappe.throw(_("Entry denied: member {0} has no membership.").format(self.member))

        frozen = None
        for m in memberships:
            valid_now = (
                m.docstatus == 1
                and m.status in ("Active", "Frozen")
                and getdate(m.start_date) <= day <= getdate(m.end_date)
            )
            if not valid_now:
                continue
            if frappe.get_doc("Gym Membership", m.name).is_frozen_on(day):
                frozen = m.name
                continue
            self.membership = m.name
            return

        if frozen:
            frappe.throw(_("Entry denied: membership {0} is Frozen.").format(frozen))

        latest = memberships[0]
        if latest.docstatus == 2 or latest.status == "Cancelled":
            frappe.throw(_("Entry denied: membership {0} is Cancelled.").format(latest.name))
        if latest.status == "Expired" or getdate(latest.end_date) < day:
            frappe.throw(
                _("Entry denied: membership {0} expired on {1}.").format(latest.name, latest.end_date)
            )
        frappe.throw(
            _("Entry denied: membership {0} starts on {1}.").format(latest.name, latest.start_date)
        )

    def validate_class_booking(self):
        if not self.class_booking:
            return
        booking = frappe.db.get_value(
            "Class Booking", self.class_booking, ["member", "status"], as_dict=True
        )
        if booking.member != self.member:
            frappe.throw(_("Class Booking {0} belongs to another member.").format(self.class_booking))
        if booking.status != "Booked":
            frappe.throw(
                _("Class Booking {0} is {1}, only Booked bookings can be checked in.").format(
                    self.class_booking, booking.status
                )
            )

    def mark_booking_attended(self):
        if not self.class_booking:
            return
        booking = frappe.get_doc("Class Booking", self.class_booking)
        booking.status = "Attended"
        booking.save(ignore_permissions=True)