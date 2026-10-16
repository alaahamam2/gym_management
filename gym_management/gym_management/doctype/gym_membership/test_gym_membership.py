import frappe
from frappe.utils import add_days, add_months, getdate, nowdate

from gym_management.tests.utils import make_member, make_membership, make_plan

try:
    from frappe.tests import IntegrationTestCase as TestBase
except ImportError:
    from frappe.tests.utils import FrappeTestCase as TestBase


class TestGymMembership(TestBase):
    def setUp(self):
        self.member = make_member()
        self.plan = make_plan(max_freeze_days=7)
        self.membership = make_membership(self.member, self.plan)

    def freeze(self, start_offset, end_offset):
        self.membership.append(
            "freeze_history",
            {
                "freeze_from": add_days(nowdate(), start_offset),
                "freeze_to": add_days(nowdate(), end_offset),
            },
        )
        self.membership.save()

    def test_end_date_is_calculated_from_plan(self):
        expected = add_days(add_months(nowdate(), 1), -1)
        self.assertEqual(getdate(self.membership.end_date), getdate(expected))

    def test_invoice_is_created_on_submit(self):
        self.assertTrue(self.membership.sales_invoice)
        self.assertEqual(
            frappe.db.get_value("Sales Invoice", self.membership.sales_invoice, "docstatus"), 1
        )

    def test_freeze_within_limit_extends_end_date(self):
        before = getdate(self.membership.end_date)
        self.freeze(3, 7)  # 5 days, inclusive
        self.assertEqual(self.membership.freeze_history[0].days, 5)
        self.assertEqual(getdate(self.membership.end_date), add_days(before, 5))

    def test_freeze_days_over_plan_limit_are_blocked(self):
        self.freeze(3, 7)  # 5 days
        with self.assertRaises(frappe.ValidationError):
            self.freeze(10, 14)  # 5 more = 10 > 7

    def test_freeze_to_must_be_after_freeze_from(self):
        with self.assertRaises(frappe.ValidationError):
            self.freeze(5, 5)

    def test_only_one_active_membership_per_member(self):
        with self.assertRaises(frappe.ValidationError):
            make_membership(self.member, self.plan)