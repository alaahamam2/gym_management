import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

DEFAULT_ITEM_GROUP = "Gym Services"


class MembershipPlan(Document):
    def validate(self):
        self.validate_values()
        self.ensure_item()

    def on_update(self):
        self.sync_item_price()

    def validate_values(self):
        if not self.duration_value or self.duration_value <= 0:
            frappe.throw(_("Duration Value must be greater than zero."))
        if flt(self.price) < 0:
            frappe.throw(_("Price cannot be negative."))
        if (self.classes_included or 0) < 0:
            frappe.throw(_("Classes Included cannot be negative."))
        if (self.max_freeze_days or 0) < 0:
            frappe.throw(_("Max Freeze Days cannot be negative."))

        # For a class pack, the duration value is the number of classes.
        if self.duration_type == "Class Pack":
            self.classes_included = self.duration_value

    def ensure_item(self):
        """Back every plan with a non-stock service Item (created if empty)."""
        if self.item:
            if frappe.db.get_value("Item", self.item, "is_stock_item"):
                frappe.throw(
                    _("Item {0} is a stock item. A Membership Plan needs a service Item.").format(
                        self.item
                    )
                )
            return

        # Reuse an Item with the same code if one already exists.
        if frappe.db.exists("Item", self.plan_name):
            self.item = self.plan_name
            return

        item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": self.plan_name,
                "item_name": self.plan_name,
                "item_group": self.get_item_group(),
                "stock_uom": "Nos",
                "is_stock_item": 0,
                "is_sales_item": 1,
                "is_purchase_item": 0,
                "description": _("Gym membership plan: {0}").format(self.plan_name),
            }
        )
        # Front Desk / managers may not have Item create rights.
        item.insert(ignore_permissions=True)
        self.item = item.name

    def get_item_group(self):
        group = frappe.db.get_single_value("Gym Settings", "default_item_group") or DEFAULT_ITEM_GROUP
        if not frappe.db.exists("Item Group", group):
            frappe.get_doc(
                {
                    "doctype": "Item Group",
                    "item_group_name": group,
                    "parent_item_group": "All Item Groups",
                    "is_group": 0,
                }
            ).insert(ignore_permissions=True)
        return group

    def sync_item_price(self):
        """Keep the selling Item Price in step with the plan price."""
        price_list = (
            frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
        )
        if not frappe.db.exists("Price List", price_list):
            return

        existing = frappe.db.get_value(
            "Item Price",
            {"item_code": self.item, "price_list": price_list, "selling": 1},
            "name",
        )
        if existing:
            frappe.db.set_value("Item Price", existing, "price_list_rate", flt(self.price))
        else:
            frappe.get_doc(
                {
                    "doctype": "Item Price",
                    "item_code": self.item,
                    "price_list": price_list,
                    "price_list_rate": flt(self.price),
                    "selling": 1,
                }
            ).insert(ignore_permissions=True)