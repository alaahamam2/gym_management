import frappe

from gym_management.tests.utils import (
    make_class,
    make_member,
    make_membership,
    make_plan,
    make_room,
    make_session,
    make_trainer,
)

try:
    from frappe.tests import IntegrationTestCase as TestBase
except ImportError:
    from frappe.tests.utils import FrappeTestCase as TestBase


def book(session, member):
    return frappe.get_doc(
        {"doctype": "Class Booking", "class_session": session.name, "member": member.name}
    ).insert()


def status_of(booking):
    return frappe.db.get_value("Class Booking", booking.name, "status")


class TestClassBooking(TestBase):
    def setUp(self):
        frappe.db.set_single_value("Gym Settings", "enable_waitlist", 1)
        plan = make_plan()
        room = make_room(capacity=2)
        self.session = make_session(make_class(room, make_trainer(), capacity=2))
        self.members = [make_member() for _ in range(3)]
        for member in self.members:
            make_membership(member, plan)

    def booked_count(self):
        return frappe.db.get_value("Class Session", self.session.name, "booked_count")

    def test_full_session_goes_to_waitlist(self):
        bookings = [book(self.session, m) for m in self.members]
        self.assertEqual([b.status for b in bookings], ["Booked", "Booked", "Waitlisted"])
        self.assertEqual(self.booked_count(), 2)

    def test_cancel_promotes_earliest_waitlisted(self):
        first, second, third = [book(self.session, m) for m in self.members]
        first.status = "Cancelled"
        first.save()

        self.assertEqual(status_of(first), "Cancelled")
        self.assertEqual(status_of(second), "Booked")
        self.assertEqual(status_of(third), "Booked")
        self.assertEqual(self.booked_count(), 2)

    def test_duplicate_booking_is_blocked(self):
        book(self.session, self.members[0])
        with self.assertRaises(frappe.ValidationError):
            book(self.session, self.members[0])

    def test_full_session_without_waitlist_is_rejected(self):
        frappe.db.set_single_value("Gym Settings", "enable_waitlist", 0)
        book(self.session, self.members[0])
        book(self.session, self.members[1])
        with self.assertRaises(frappe.ValidationError):
            book(self.session, self.members[2])
        self.assertEqual(self.booked_count(), 2)

    def test_member_without_membership_cannot_book(self):
        with self.assertRaises(frappe.ValidationError):
            book(self.session, make_member())