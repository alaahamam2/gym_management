import frappe
from frappe.utils import add_days, nowdate


def _uid():
    return frappe.generate_hash(length=6)


def make_room(capacity=20):
    return frappe.get_doc(
        {"doctype": "Gym Room", "room_name": f"Room {_uid()}", "capacity": capacity}
    ).insert()


def make_trainer():
    company = frappe.get_all("Company", pluck="name", limit_page_length=1)[0]
    employee = frappe.get_doc(
        {
            "doctype": "Employee",
            "first_name": f"Trainer {_uid()}",
            "gender": "Male",
            "date_of_birth": "1995-01-01",
            "date_of_joining": "2024-01-01",
            "company": company,
        }
    ).insert()
    return frappe.get_doc({"doctype": "Gym Trainer", "employee": employee.name}).insert()


def make_class(room, trainer, capacity=None, duration=60):
    return frappe.get_doc(
        {
            "doctype": "Gym Class",
            "class_name": f"Class {_uid()}",
            "category": "Other",
            "default_trainer": trainer.name,
            "default_room": room.name,
            "duration_minutes": duration,
            "default_capacity": capacity or room.capacity,
        }
    ).insert()


def make_plan(max_freeze_days=7, duration_type="Months", duration_value=1, price=500):
    return frappe.get_doc(
        {
            "doctype": "Membership Plan",
            "plan_name": f"Plan {_uid()}",
            "duration_type": duration_type,
            "duration_value": duration_value,
            "price": price,
            "max_freeze_days": max_freeze_days,
        }
    ).insert()


def make_member():
    return frappe.get_doc({"doctype": "Gym Member", "member_name": f"Member {_uid()}"}).insert()


def make_membership(member, plan, start_date=None, submit=True):
    membership = frappe.get_doc(
        {
            "doctype": "Gym Membership",
            "member": member.name,
            "membership_plan": plan.name,
            "start_date": start_date or nowdate(),
        }
    ).insert()
    if submit:
        membership.submit()
    return membership


def make_session(gym_class, days_ahead=5, start_time="10:00:00"):
    return frappe.get_doc(
        {
            "doctype": "Class Session",
            "gym_class": gym_class.name,
            "session_date": add_days(nowdate(), days_ahead),
            "start_time": start_time,
        }
    ).insert()