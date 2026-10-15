import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, nowdate, validate_email_address, validate_phone_number


class GymMember(Document):
    def validate(self):
        self.validate_date_of_birth()
        self.validate_contact_details()
        self.validate_unique_customer()
        self.ensure_customer()

    def validate_date_of_birth(self):
        if self.date_of_birth and getdate(self.date_of_birth) > getdate(nowdate()):
            frappe.throw(_("Date of Birth cannot be in the future."))

    def validate_contact_details(self):
        if self.email:
            validate_email_address(self.email, throw=True)
        if self.phone:
            validate_phone_number(self.phone, throw=True)
        if self.emergency_contact_phone:
            validate_phone_number(self.emergency_contact_phone, throw=True)

    def validate_unique_customer(self):
        if not self.customer:
            return
        other = frappe.db.get_value(
            "Gym Member",
            {"customer": self.customer, "name": ["!=", self.name]},
            "name",
        )
        if other:
            frappe.throw(
                _("Customer {0} is already linked to Gym Member {1}.").format(
                    self.customer, other
                )
            )

    def ensure_customer(self):
        """One Gym Member <-> one Customer. Create the Customer on first save if empty."""
        if self.customer:
            return

        selling = frappe.get_cached_doc("Selling Settings")
        customer = frappe.get_doc(
            {
                "doctype": "Customer",
                "customer_name": self.member_name,
                "customer_type": "Individual",
                "customer_group": selling.customer_group or "Individual",
                "territory": selling.territory or "All Territories",
            }
        )
        # Front Desk users cannot create Customers directly, so bypass permissions here.
        customer.insert(ignore_permissions=True)
        self.customer = customer.name