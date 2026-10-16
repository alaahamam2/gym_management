"""Sample data. Run: bench --site <site> execute gym_management.seed.seed  (safe to run twice)."""
import frappe
from frappe.utils import add_days, nowdate

from gym_management.tasks import check_expired_memberships

SPECIALTIES = ["Yoga", "HIIT", "Spin", "Strength", "Cardio"]
ROOMS = [("Studio A", 20), ("Spin Room", 12), ("Mini Studio", 2)]
PLANS = [  # name, duration_type, duration_value, price, max_freeze_days
    ("Monthly", "Months", 1, 500, 7),
    ("Quarterly", "Months", 3, 1350, 14),
    ("Annual", "Months", 12, 4800, 30),
    ("10-Class Pack", "Class Pack", 10, 700, 0),
]
TRAINERS = [  # name, gender, specialties
    ("Sara Ali", "Female", ["Yoga", "Cardio"]),
    ("Omar Hassan", "Male", ["HIIT", "Strength"]),
    ("Nour Khaled", "Female", ["Spin"]),
]
CLASSES = [  # name, category, trainer index, room, minutes, capacity
    ("Morning Yoga", "Yoga", 0, "Studio A", 60, 15),
    ("HIIT Blast", "HIIT", 1, "Studio A", 45, 20),
    ("Strength Basics", "Strength", 1, "Studio A", 60, 10),
    ("Spin 45", "Spin", 2, "Spin Room", 45, 12),
    ("Intro Class", "Other", 0, "Mini Studio", 30, 2),
]
SCHEDULE = [  # class, start time (every day for the next 5 days)
    ("Morning Yoga", "08:00:00"),
    ("HIIT Blast", "10:00:00"),
    ("Strength Basics", "12:00:00"),
    ("Intro Class", "17:00:00"),
    ("Spin 45", "18:00:00"),
]
MEMBERS = [  # name, plan, start offset (days), frozen now?
    ("Ahmed Samir", "Monthly", 0, False),
    ("Mona Adel", "Quarterly", -10, False),
    ("Youssef Tarek", "10-Class Pack", -3, False),
    ("Laila Fathy", "Monthly", -60, False),  # ends up Expired -> check-in is blocked
    ("Karim Nabil", "Monthly", -5, True),  # Frozen today -> check-in is blocked
    ("Hana Mostafa", "Annual", -20, False),
]


def ensure(doctype, name, values):
    if frappe.db.exists(doctype, name):
        doc = frappe.get_doc(doctype, name)
        doc.update(values)  # bring records created earlier (older field layout) up to date
        doc.save()
        return doc
    return frappe.get_doc({"doctype": doctype, **values}).insert()


def seed():
    frappe.set_user("Administrator")
    frappe.flags.mute_emails = True
    company = frappe.get_all("Company", pluck="name", limit_page_length=1)[0]

    frappe.db.set_single_value(
        "Gym Settings",
        {"enable_waitlist": 1, "cancellation_window_hours": 24, "no_show_limit": 3, "expiry_reminder_days": 7},
    )

    for name in SPECIALTIES:
        ensure("Gym Specialty", name, {"specialty_name": name})

    for name, capacity in ROOMS:
        ensure("Gym Room", name, {"room_name": name, "capacity": capacity})

    for name, kind, value, price, freeze in PLANS:
        ensure(
            "Membership Plan",
            name,
            {
                "plan_name": name,
                "duration_type": kind,
                "duration_value": value,
                "price": price,
                "max_freeze_days": freeze,
            },
        )

    trainers = []
    for name, gender, specialties in TRAINERS:
        employee = frappe.db.get_value("Employee", {"employee_name": name})
        if not employee:
            first, last = name.split(" ", 1)
            employee = frappe.get_doc(
                {
                    "doctype": "Employee",
                    "first_name": first,
                    "last_name": last,
                    "gender": gender,
                    "date_of_birth": "1992-01-01",
                    "date_of_joining": "2024-01-01",
                    "company": company,
                }
            ).insert().name
        trainer = ensure(
            "Gym Trainer",
            employee,
            {"employee": employee, "specialties": [{"specialty": s} for s in specialties]},
        )
        trainers.append(trainer.name)

    for name, category, trainer_index, room, minutes, capacity in CLASSES:
        ensure(
            "Gym Class",
            name,
            {
                "class_name": name,
                "category": category,
                "default_trainer": trainers[trainer_index],
                "default_room": room,
                "duration_minutes": minutes,
                "default_capacity": capacity,
            },
        )

    for day in range(1, 6):
        date = add_days(nowdate(), day)
        for class_name, start in SCHEDULE:
            if not frappe.db.exists(
                "Class Session", {"gym_class": class_name, "session_date": date, "start_time": start}
            ):
                frappe.get_doc(
                    {"doctype": "Class Session", "gym_class": class_name, "session_date": date, "start_time": start}
                ).insert()

    members = {}
    for index, (name, plan, offset, frozen) in enumerate(MEMBERS, start=1):
        member = frappe.db.get_value("Gym Member", {"member_name": name})
        if not member:
            member = frappe.get_doc(
                {
                    "doctype": "Gym Member",
                    "member_name": name,
                    "email": name.lower().replace(" ", ".") + "@example.com",
                    "phone": f"+20100{index:06d}",
                }
            ).insert().name
        members[name] = member

        if not frappe.db.exists("Gym Membership", {"member": member, "docstatus": 1}):
            membership = frappe.get_doc(
                {
                    "doctype": "Gym Membership",
                    "member": member,
                    "membership_plan": plan,
                    "start_date": add_days(nowdate(), offset),
                }
            ).insert()
            membership.submit()
            if frozen:
                membership.append(
                    "freeze_history",
                    {"freeze_from": add_days(nowdate(), -1), "freeze_to": add_days(nowdate(), 3), "reason": "Travelling"},
                )
                membership.save()

    check_expired_memberships()  # marks Laila's membership Expired

    # 3 bookings into a 2-seat session: the third lands on the waitlist
    tomorrow = add_days(nowdate(), 1)
    intro = frappe.db.get_value("Class Session", {"gym_class": "Intro Class", "session_date": tomorrow})
    for name in ("Ahmed Samir", "Mona Adel", "Youssef Tarek"):
        member = members[name]
        if frappe.db.exists("Class Booking", {"class_session": intro, "member": member}):
            continue
        try:
            frappe.get_doc({"doctype": "Class Booking", "class_session": intro, "member": member}).insert()
        except frappe.ValidationError as e:
            print(f"Booking skipped for {name}: {e}")

    frappe.db.commit()
    print("Seed data ready.")