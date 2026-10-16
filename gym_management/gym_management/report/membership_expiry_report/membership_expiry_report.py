import frappe
from frappe import _
from frappe.utils import date_diff, getdate, nowdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    return get_columns(), get_data(filters)


def validate_filters(filters):
    if filters.from_date and filters.to_date and getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("End Date From cannot be after End Date To."))


def get_columns():
    return [
        {"label": _("Membership"), "fieldname": "name", "fieldtype": "Link", "options": "Gym Membership", "width": 170},
        {"label": _("Member"), "fieldname": "member", "fieldtype": "Link", "options": "Gym Member", "width": 110},
        {"label": _("Member Name"), "fieldname": "member_name", "fieldtype": "Data", "width": 160},
        {"label": _("Plan"), "fieldname": "membership_plan", "fieldtype": "Link", "options": "Membership Plan", "width": 140},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
        {"label": _("Start Date"), "fieldname": "start_date", "fieldtype": "Date", "width": 100},
        {"label": _("End Date"), "fieldname": "end_date", "fieldtype": "Date", "width": 100},
        {"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
        {"label": _("Email"), "fieldname": "email", "fieldtype": "Data", "width": 190},
        {"label": _("Phone"), "fieldname": "phone", "fieldtype": "Data", "width": 130},
    ]


def get_data(filters):
    conditions = {"docstatus": ["in", [1, 2]]}
    if filters.status:
        conditions["status"] = filters.status
    if filters.membership_plan:
        conditions["membership_plan"] = filters.membership_plan
    if filters.from_date and filters.to_date:
        conditions["end_date"] = ["between", [filters.from_date, filters.to_date]]
    elif filters.from_date:
        conditions["end_date"] = [">=", filters.from_date]
    elif filters.to_date:
        conditions["end_date"] = ["<=", filters.to_date]

    rows = frappe.get_list(
        "Gym Membership",
        filters=conditions,
        fields=["name", "member", "member_name", "membership_plan", "status", "start_date", "end_date"],
        order_by="end_date asc",
    )
    if not rows:
        return []

    # one query for all contact details instead of one per row
    contacts = {
        m.name: m
        for m in frappe.get_list(
            "Gym Member",
            filters={"name": ["in", list({r.member for r in rows})]},
            fields=["name", "email", "phone"],
        )
    }

    today = getdate(nowdate())
    for r in rows:
        r.days_left = date_diff(r.end_date, today) if r.end_date else None
        contact = contacts.get(r.member)
        r.email = contact.email if contact else None
        r.phone = contact.phone if contact else None
    return rows