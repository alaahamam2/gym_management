import frappe
from frappe.model.document import Document
from frappe.utils import add_days, date_diff

class GymMembership(Document):
    def validate(self):
        # 1. حساب تاريخ النهاية تلقائياً بناءً على أيام الخطة
        if self.plan and self.start_date:
            plan = frappe.get_doc("Membership Plan", self.plan)
            if plan.duration_days:
                self.end_date = add_days(self.start_date, plan.duration_days)

        # 2. التحقق من جدول التجميد (Membership Freeze Validation)
        if self.freeze_history and self.plan:
            plan = frappe.get_doc("Membership Plan", self.plan)
            total_freeze_days = 0
            
            for freeze in self.freeze_history:
                if freeze.freeze_from and freeze.freeze_to:
                    if freeze.freeze_to < freeze.freeze_from:
                        frappe.throw("تاريخ نهاية التجميد يجب أن يكون بعد تاريخ البداية.")
                    
                    # حساب الأيام لكل صف تجميد
                    days = date_diff(freeze.freeze_to, freeze.freeze_from) + 1
                    freeze.days = days
                    total_freeze_days += days

            if plan.max_freeze_days and total_freeze_days > plan.max_freeze_days:
                frappe.throw(f"إجمالي أيام التجميد ({total_freeze_days} يوم) يتجاوز الحد الأقصى المسموح به لهذه الخطة وهو ({plan.max_freeze_days} يوم).")

    def on_submit(self):
        # إنشاء وترابط فاتورة المبيعات تلقائياً عند اعتماد الاشتراكات الجديدة
        self.create_sales_invoice()

    def create_sales_invoice(self):
        if self.sales_invoice:
            return

        plan = frappe.get_doc("Membership Plan", self.plan)
        
        # التأكد من وجود عميل مرتبط أو إنشاء عميل تجريبي / افتراضي للاشتراك
        customer = getattr(self, "customer", None)
        if not customer:
            existing_cust = frappe.get_all("Customer", filters={"customer_type": "Individual"}, limit=1)
            if existing_cust:
                customer = existing_cust[0].name
            else:
                cust = frappe.new_doc("Customer")
                cust.customer_name = "Gym Member"
                cust.customer_type = "Individual"
                cust.customer_group = "Individual"
                cust.territory = "Rest of the World"
                cust.insert(ignore_permissions=True)
                customer = cust.name

        # التحقق من وجود الصنف (Item) أو إنشاؤه
        item_code = plan.item or "Gym Membership Plan"
        if not frappe.db.exists("Item", item_code):
            item = frappe.new_doc("Item")
            item.item_code = item_code
            item.item_name = "Gym Membership Plan"
            item.item_group = "Services"
            item.stock_uom = "Nos"
            item.is_stock_item = 0
            item.insert(ignore_permissions=True)

        # إنشاء فاتورة المبيعات واعتمادها
        invoice = frappe.new_doc("Sales Invoice")
        invoice.customer = customer
        invoice.append("items", {
            "item_code": item_code,
            "qty": 1,
            "rate": plan.price
        })
        invoice.insert(ignore_permissions=True)
        invoice.submit()

        # ربط الفاتورة بالمستند الحالي
        self.db_set("sales_invoice", invoice.name)