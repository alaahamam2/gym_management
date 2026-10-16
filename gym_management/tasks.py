import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, nowdate


def check_expired_memberships():
    """Daily job: expire memberships past their end date and keep Active/Frozen in sync."""
    today = getdate(nowdate())

    expire_memberships(today)
    sync_frozen_status(today)


def expire_memberships(today):
    expired = frappe.get_all(
        "Gym Membership",
        filters={"docstatus": 1, "status": ["in", ["Active", "Frozen"]], "end_date": ["<", today]},
        fields=["name", "member"],
    )
    for row in expired:
        try:
            frappe.db.set_value("Gym Membership", row.name, "status", "Expired")

            member = frappe.db.get_value(
                "Gym Member", row.member, ["active_membership", "status"], as_dict=True
            )
            if member and member.active_membership == row.name:
                updates = {"active_membership": None}
                # Never override Blacklisted / Prospect
                if member.status == "Active":
                    updates["status"] = "Inactive"
                frappe.db.set_value("Gym Member", row.member, updates)
        except Exception:
            frappe.log_error(title=f"Failed to expire membership {row.name}")


def sync_frozen_status(today):
    """A membership is Frozen only while today falls inside one of its freeze periods."""
    with_freezes = frappe.db.sql_list(
        "select distinct parent from `tabMembership Freeze` where parenttype = 'Gym Membership'"
    )
    if not with_freezes:
        return

    memberships = frappe.get_all(
        "Gym Membership",
        filters={
            "name": ["in", with_freezes],
            "docstatus": 1,
            "status": ["in", ["Active", "Frozen"]],
            "end_date": [">=", today],
        },
        fields=["name", "status"],
    )
    for row in memberships:
        try:
            doc = frappe.get_doc("Gym Membership", row.name)
            new_status = "Frozen" if doc.is_frozen_on(today) else "Active"
            if new_status != row.status:
                frappe.db.set_value("Gym Membership", row.name, "status", new_status)
        except Exception:
            frappe.log_error(title=f"Failed to sync freeze status for {row.name}")


def send_expiry_reminders():
    """Daily job: email members whose membership ends in `expiry_reminder_days` days."""
    days = cint(frappe.db.get_single_value("Gym Settings", "expiry_reminder_days"))
    if days <= 0:
        return

    target = add_days(getdate(nowdate()), days)
    memberships = frappe.get_all(
        "Gym Membership",
        filters={"docstatus": 1, "status": "Active", "end_date": target},
        fields=["name", "member", "end_date"],
    )
    for row in memberships:
        email, member_name = frappe.db.get_value("Gym Member", row.member, ["email", "member_name"])
        if not email:
            continue
        try:
            frappe.sendmail(
                recipients=[email],
                subject=_("Your gym membership expires soon"),
                message=_("Hi {0}, your membership {1} expires on {2}. Renew it to keep training with us.").format(
                    member_name, row.name, row.end_date
                ),
                reference_doctype="Gym Membership",
                reference_name=row.name,
            )
        except Exception:
            frappe.log_error(title=f"Expiry reminder failed for {row.name}")