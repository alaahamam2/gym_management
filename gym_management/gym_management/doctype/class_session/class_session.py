from datetime import timedelta

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import to_timedelta


def _fmt(td):
    """timedelta -> 'HH:MM:SS' string accepted by Time fields."""
    total = int(td.total_seconds())
    return "{:02d}:{:02d}:{:02d}".format(total // 3600, (total % 3600) // 60, total % 60)


class ClassSession(Document):
    def validate(self):
        self.set_defaults_from_class()
        self.set_end_time()
        self.validate_resources()
        self.validate_capacity()
        self.validate_overlaps()

    def set_defaults_from_class(self):
        gym_class = frappe.db.get_value(
            "Gym Class",
            self.gym_class,
            ["default_trainer", "default_room", "default_capacity"],
            as_dict=True,
        )
        if not gym_class:
            return
        self.trainer = self.trainer or gym_class.default_trainer
        self.room = self.room or gym_class.default_room
        self.capacity = self.capacity or gym_class.default_capacity

    def set_end_time(self):
        duration = frappe.db.get_value("Gym Class", self.gym_class, "duration_minutes") or 0
        start = to_timedelta(self.start_time)
        end = start + timedelta(minutes=duration)
        if end >= timedelta(days=1):
            frappe.throw(_("The session must end before midnight."))
        self.end_time = _fmt(end)

    def validate_resources(self):
        if not self.trainer:
            frappe.throw(_("Trainer is required (set one here or a default trainer on the class)."))
        if not self.room:
            frappe.throw(_("Room is required (set one here or a default room on the class)."))
        if self.is_new() and self.status == "Scheduled":
            if not frappe.db.get_value("Gym Trainer", self.trainer, "is_active"):
                frappe.throw(_("Trainer {0} is not active.").format(self.trainer))
            if not frappe.db.get_value("Gym Room", self.room, "is_active"):
                frappe.throw(_("Room {0} is not active.").format(self.room))

    def validate_capacity(self):
        room_capacity = frappe.db.get_value("Gym Room", self.room, "capacity") or 0
        if not self.capacity:
            self.capacity = room_capacity
        if self.capacity <= 0:
            frappe.throw(_("Capacity must be greater than zero."))
        if self.capacity > room_capacity:
            frappe.throw(
                _("Capacity ({0}) cannot exceed the capacity of room {1} ({2}).").format(
                    self.capacity, self.room, room_capacity
                )
            )
        if self.capacity < (self.booked_count or 0):
            frappe.throw(
                _("Capacity ({0}) cannot be lower than the number of confirmed bookings ({1}).").format(
                    self.capacity, self.booked_count
                )
            )

    def validate_overlaps(self):
        if self.status == "Cancelled":
            return
        for field, label in (("trainer", _("Trainer")), ("room", _("Room"))):
            clash = frappe.db.get_value(
                "Class Session",
                {
                    field: self.get(field),
                    "session_date": self.session_date,
                    "status": ["!=", "Cancelled"],
                    "name": ["!=", self.name],
                    "start_time": ["<", self.end_time],
                    "end_time": [">", self.start_time],
                },
                "name",
            )
            if clash:
                frappe.throw(
                    _("{0} {1} already has an overlapping session: {2}.").format(
                        label, self.get(field), clash
                    )
                )