import frappe
from frappe import _
from frappe.model.document import Document


class GymTrainer(Document):
    def validate(self):
        status = frappe.db.get_value("Employee", self.employee, "status")
        if status and status != "Active":
            frappe.throw(
                _("Employee {0} is {1}. Only Active employees can be trainers.").format(
                    self.employee, status
                )
            )