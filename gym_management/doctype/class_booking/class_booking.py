import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class ClassBooking(Document):

    def validate(self):
        self.validate_membership()
        self.check_session_capacity()

    def validate_membership(self):
        session = frappe.get_doc("Class Session", self.class_session)
        active_membership = frappe.db.get_value(
            "Gym Membership",
            {
                "member": self.member,
                "docstatus": 1,
                "status": "Active",
                "start_date": ["<=", session.session_date],
                "end_date": [">=", session.session_date],
            },
            "name",
        )

        if not active_membership:
            frappe.throw("The member does not have an active membership for this session date.")

        self.membership = active_membership

    def check_session_capacity(self):
        if self.is_new():
            session = frappe.get_doc("Class Session", self.class_session)
            booked_count = session.booked_count or 0
            if booked_count >= session.capacity:
                settings = frappe.get_single("Gym Settings") if frappe.db.exists("DocType", "Gym Settings") else None
                enable_waitlist = settings.enable_waitlist if settings else False

                if enable_waitlist:
                    self.status = "Waitlisted"
                    frappe.msgprint("Session is full. Booking placed on Waitlist.")
                else:
                    frappe.throw("This class session is fully booked.")
            else:
                self.status = "Booked"

    def on_submit(self):
        if self.status == "Booked":
            self.update_booked_count(1)

    def on_cancel(self):
        self.status = "Cancelled"
        self.cancelled_on = now_datetime()
        if self.docstatus == 1:
            self.update_booked_count(-1)
        self.promote_waitlist()

    def update_booked_count(self, delta):
        session = frappe.get_doc("Class Session", self.class_session)
        session.booked_count = max(0, (session.booked_count or 0) + delta)
        session.save(ignore_permissions=True)

    def promote_waitlist(self):
        waitlisted = frappe.db.get_value(
            "Class Booking",
            {
                "class_session": self.class_session,
                "status": "Waitlisted",
                "docstatus": 1,
            },
            "name",
            order_by="creation asc",
        )
        if waitlisted:
            wb = frappe.get_doc("Class Booking", waitlisted)
            wb.status = "Booked"
            wb.save(ignore_permissions=True)
            wb.update_booked_count(1)
            frappe.msgprint(f"Booking {wb.name} has been promoted from Waitlist to Booked.")