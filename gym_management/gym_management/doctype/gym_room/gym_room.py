import frappe
from frappe import _
from frappe.model.document import Document


class GymRoom(Document):
    def validate(self):
        if not self.capacity or self.capacity <= 0:
            frappe.throw(_("Capacity must be greater than zero."))
			