import frappe
from frappe.utils import nowdate, getdate

def check_expired_memberships():
    """فحص الاشتراكات يومياً وتغيير حالتها لـ Expired وتحديث العضو"""
    today = getdate(nowdate())
    
    # جلب جميع الاشتراكات النشطة التي انتهى تاريخها
    expired_memberships = frappe.get_all(
        "Gym Membership",
        filters={
            "docstatus": 1,
            "status": "Active",
            "end_date": ["<", today]
        },
        fields=["name", "member"]
    )
    
    for membership in expired_memberships:
        # تحديث حالة الاشتراك
        frappe.db.set_value("Gym Membership", membership.name, "status", "Expired")
        
        # تحديث حالة العضو إلى Inactive إذا كان هذا اشتراكه الحالي
        member = frappe.get_doc("Gym Member", membership.member)
        if member.active_membership == membership.name:
            member.active_membership = None
            member.status = "Inactive"
            member.save(ignore_permissions=True)
            
    frappe.db.commit()