import frappe
from frappe.utils import add_days, nowdate

from gym_management.tasks import check_expired_memberships
from gym_management.tests.utils import make_member, make_membership, make_plan

try:
    from frappe.tests import IntegrationTestCase as TestBase
except ImportError:
    from frappe.tests.utils import FrappeTestCase as TestBase


def check_in(member):
    return frappe.get_doc({"doctype": "Gym Check In", "member": member.name}).insert()


class TestGymCheckIn(TestBase):
    def setUp(self):
        self.member = make_member()
        self.plan = make_plan(max_freeze_days=7)

    def test_active_member_can_check_in(self):
        membership = make_membership(self.member, self.plan)
        entry = check_in(self.member)
        self.assertEqual(entry.membership, membership.name)

    def test_expired_member_is_blocked(self):
        # a 1-month plan that started 60 days ago ended about a month ago
        make_membership(self.member, self.plan, start_date=add_days(nowdate(), -60))
        with self.assertRaises(frappe.ValidationError) as ctx:
            check_in(self.member)
        self.assertIn("expired", str(ctx.exception))

    def test_daily_job_marks_expired_and_check_in_stays_blocked(self):
        membership = make_membership(self.member, self.plan, start_date=add_days(nowdate(), -60))
        check_expired_memberships()
        self.assertEqual(frappe.db.get_value("Gym Membership", membership.name, "status"), "Expired")
        with self.assertRaises(frappe.ValidationError):
            check_in(self.member)

    def test_frozen_member_is_blocked(self):
        membership = make_membership(self.member, self.plan)
        membership.append(
            "freeze_history",
            {"freeze_from": nowdate(), "freeze_to": add_days(nowdate(), 3)},
        )
        membership.save()
        with self.assertRaises(frappe.ValidationError) as ctx:
            check_in(self.member)
        self.assertIn("Frozen", str(ctx.exception))

    def test_member_without_membership_is_blocked(self):
        with self.assertRaises(frappe.ValidationError):
            check_in(self.member)