import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, date_diff, getdate, nowdate

# A class pack has no duration of its own, so it stays valid for this long.
CLASS_PACK_VALIDITY_MONTHS = 12


class GymMembership(Document):
    # The Sales Invoice links back to this document; don't let that block cancel.
    ignore_linked_doctypes = ("Sales Invoice",)

    def validate(self):
        if self.docstatus == 0 or self.status == "Draft":
            self.validate_member_and_plan()
        self.set_classes_remaining()
        frozen_days = self.validate_freezes()
        self.set_end_date(frozen_days)
        self.set_status()

    def before_submit(self):
        self.validate_single_active_membership()

    def on_submit(self):
        self.create_sales_invoice()
        frappe.db.set_value(
            "Gym Member",
            self.member,
            {"active_membership": self.name, "status": "Active"},
        )

    def before_cancel(self):
        self.cancel_sales_invoice()

    def on_cancel(self):
        self.db_set("status", "Cancelled")
        if frappe.db.get_value("Gym Member", self.member, "active_membership") == self.name:
            frappe.db.set_value("Gym Member", self.member, "active_membership", None)

    # ---------- validations ----------

    def validate_member_and_plan(self):
        if frappe.db.get_value("Gym Member", self.member, "status") == "Blacklisted":
            frappe.throw(_("Member {0} is blacklisted.").format(self.member))
        if not frappe.db.get_value("Membership Plan", self.membership_plan, "is_active"):
            frappe.throw(_("Membership Plan {0} is not active.").format(self.membership_plan))

    def validate_single_active_membership(self):
        other = frappe.db.get_value(
            "Gym Membership",
            {
                "member": self.member,
                "docstatus": 1,
                "status": ["in", ["Active", "Frozen"]],
                "name": ["!=", self.name],
            },
            "name",
        )
        if other:
            frappe.throw(
                _("Member {0} already has an active membership: {1}.").format(self.member, other)
            )

    def validate_freezes(self):
        """Validate freeze rows and return the total number of frozen days."""
        if not self.freeze_history:
            return 0

        max_days = frappe.db.get_value("Membership Plan", self.membership_plan, "max_freeze_days") or 0
        total = 0
        last_to = None

        for row in sorted(self.freeze_history, key=lambda r: getdate(r.freeze_from)):
            f_from, f_to = getdate(row.freeze_from), getdate(row.freeze_to)
            if f_to <= f_from:
                frappe.throw(_("Row {0}: Freeze To must be after Freeze From.").format(row.idx))
            if f_from < getdate(self.start_date):
                frappe.throw(_("Row {0}: Freeze cannot start before the membership start date.").format(row.idx))
            if last_to and f_from <= last_to:
                frappe.throw(_("Row {0}: Freeze period overlaps with another row.").format(row.idx))

            row.days = date_diff(f_to, f_from) + 1  # inclusive
            total += row.days
            last_to = f_to

        if total > max_days:
            frappe.throw(
                _("Total freeze days ({0}) exceed the maximum allowed by the plan ({1}).").format(
                    total, max_days
                )
            )
        return total

    # ---------- calculations ----------

    def set_classes_remaining(self):
        if self.docstatus == 0:
            self.classes_remaining = frappe.db.get_value(
                "Membership Plan", self.membership_plan, "classes_included"
            ) or 0

    def set_end_date(self, frozen_days=0):
        if not (self.start_date and self.membership_plan):
            return
        plan = frappe.get_cached_doc("Membership Plan", self.membership_plan)
        start = getdate(self.start_date)

        if plan.duration_type == "Days":
            end = add_days(start, plan.duration_value - 1)
        elif plan.duration_type == "Months":
            end = add_days(add_months(start, plan.duration_value), -1)
        else:  # Class Pack
            end = add_days(add_months(start, CLASS_PACK_VALIDITY_MONTHS), -1)

        # Each frozen day pushes the end date out by one day.
        self.end_date = add_days(end, frozen_days)

    def set_status(self):
        if self.docstatus == 0:
            self.status = "Draft"
        elif self.docstatus == 1 and self.status in ("Draft", "Active", "Frozen"):
            self.status = "Frozen" if self.is_frozen_on(nowdate()) else "Active"

    def is_frozen_on(self, date):
        date = getdate(date)
        return any(
            getdate(r.freeze_from) <= date <= getdate(r.freeze_to) for r in self.freeze_history
        )

    # ---------- billing ----------

    def create_sales_invoice(self):
        """Idempotent: if an invoice already exists for this membership, reuse it."""
        existing = self.sales_invoice or frappe.db.get_value(
            "Sales Invoice", {"gym_membership": self.name, "docstatus": ["!=", 2]}, "name"
        )
        if existing:
            if not self.sales_invoice:
                self.db_set("sales_invoice", existing)
            return

        customer = frappe.db.get_value("Gym Member", self.member, "customer")
        if not customer:
            frappe.throw(_("Gym Member {0} has no linked Customer.").format(self.member))

        plan = frappe.get_cached_doc("Membership Plan", self.membership_plan)
        row = {
            "item_code": plan.item,
            "qty": 1,
            "rate": plan.price,
            "description": _("Gym membership: {0}").format(plan.plan_name),
        }
        income_account = frappe.db.get_single_value("Gym Settings", "default_income_account")
        if income_account:
            row["income_account"] = income_account

        invoice = frappe.get_doc(
            {
                "doctype": "Sales Invoice",
                "customer": customer,
                "gym_membership": self.name,
                "posting_date": nowdate(),
                "due_date": nowdate(),
                "items": [row],
            }
        )
        # Front Desk / Gym Manager may not have rights on Sales Invoice.
        invoice.insert(ignore_permissions=True)
        invoice.submit()
        self.db_set("sales_invoice", invoice.name)

    def cancel_sales_invoice(self):
        if not self.sales_invoice:
            return
        invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
        if invoice.docstatus == 1:
            invoice.flags.ignore_links = True  # it links back to this membership
            invoice.cancel()