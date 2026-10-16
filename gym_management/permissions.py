import frappe

# A user holding only the Trainer role is restricted to their own sessions.
# Anyone who also has one of these roles keeps full access.
STAFF_ROLES = {"System Manager", "Gym Manager", "Front Desk"}


def _is_trainer_only(user):
    if user == "Administrator":
        return False
    roles = set(frappe.get_roles(user))
    return "Trainer" in roles and not (roles & STAFF_ROLES)


def _trainer_names(user):
    """Gym Trainer records linked (through Employee.user_id) to this user."""
    employees = frappe.get_all("Employee", filters={"user_id": user}, pluck="name")
    if not employees:
        return []
    return frappe.get_all("Gym Trainer", filters={"employee": ["in", employees]}, pluck="name")


def _in_clause(values):
    return ", ".join(frappe.db.escape(v) for v in values)


# ---------- Class Session ----------

def class_session_query(user=None):
    user = user or frappe.session.user
    if not _is_trainer_only(user):
        return ""
    names = _trainer_names(user)
    if not names:
        return "1=0"  # a Trainer user with no trainer profile sees nothing
    return f"`tabClass Session`.trainer in ({_in_clause(names)})"


def class_session_has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not _is_trainer_only(user):
        return None  # no opinion: normal role permissions decide
    return doc.trainer in _trainer_names(user)


# ---------- Class Booking (a trainer marks attendance on their own sessions) ----------

def class_booking_query(user=None):
    user = user or frappe.session.user
    if not _is_trainer_only(user):
        return ""
    names = _trainer_names(user)
    if not names:
        return "1=0"
    return (
        "`tabClass Booking`.class_session in "
        f"(select name from `tabClass Session` where trainer in ({_in_clause(names)}))"
    )


def class_booking_has_permission(doc, ptype=None, user=None):
    user = user or frappe.session.user
    if not _is_trainer_only(user):
        return None
    trainer = frappe.db.get_value("Class Session", doc.class_session, "trainer")
    return trainer in _trainer_names(user)