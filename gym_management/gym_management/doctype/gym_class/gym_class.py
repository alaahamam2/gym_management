import frappe
from frappe import _
from frappe.model.document import Document


class GymClass(Document):
    def validate(self):
        if not self.duration_minutes or self.duration_minutes <= 0:
            frappe.throw(_("Duration must be greater than zero minutes."))
        self.validate_capacity()
        self.validate_trainer_and_room()

    def validate_capacity(self):
        if self.default_capacity and self.default_capacity < 0:
            frappe.throw(_("Default Capacity cannot be negative."))

        if self.default_room:
            room_capacity = frappe.db.get_value("Gym Room", self.default_room, "capacity") or 0
            # Fall back to the room's capacity when none is given.
            if not self.default_capacity:
                self.default_capacity = room_capacity
            elif self.default_capacity > room_capacity:
                frappe.throw(
                    _("Default Capacity ({0}) cannot exceed the capacity of room {1} ({2}).").format(
                        self.default_capacity, self.default_room, room_capacity
                    )
                )

    def validate_trainer_and_room(self):
        if self.default_trainer and not frappe.db.get_value(
            "Gym Trainer", self.default_trainer, "is_active"
        ):
            frappe.throw(_("Trainer {0} is not active.").format(self.default_trainer))
        if self.default_room and not frappe.db.get_value("Gym Room", self.default_room, "is_active"):
            frappe.throw(_("Room {0} is not active.").format(self.default_room))