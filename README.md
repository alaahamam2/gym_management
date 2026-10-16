# Gym Management (Frappe / ERPNext v15)

A Frappe app for gym members, membership plans, class scheduling, bookings (with waitlist) and check-ins.
Billing is done with ERPNext's Customer, Item and Sales Invoice rather than re-implemented.

## Requirements
Frappe + ERPNext `version-15`, Python 3.10+, bench CLI. ERPNext's setup wizard must be completed
(a Company with a chart of accounts), because memberships create Sales Invoices.

## Install
```bash
bench get-app --branch version-15 erpnext
bench new-site gym.local --admin-password admin
bench --site gym.local install-app erpnext
bench get-app <path-or-url-of-this-repo>
bench --site gym.local install-app gym_management
bench --site gym.local execute gym_management.seed.seed      # optional sample data (safe to re-run)
bench start
```
Installing creates the roles **Gym Manager**, **Front Desk** and **Trainer** (fixtures) and the custom field
`gym_membership` on Sales Invoice.

## Screens
- `/app/gym-dashboard` active members, expiring in 7 days, today's sessions with fill rate, revenue this month
- `/app/front-desk-checkin` search by name / phone / member ID (QR), green or red banner, one-click check-in
- `/app/class-session/view/calendar` class timetable
- `/app/query-report/Membership Expiry Report` filters: end date range, plan, status

## Tests
```bash
bench --site gym.local set-config allow_tests true
bench --site gym.local run-tests --app gym_management
```
Covered: capacity and waitlist (including promotion on cancel), freeze limits, end date and invoice on submit,
check-in blocked for expired / frozen / cancelled members.

## Assumptions
- A class pack stays valid for 12 months (`CLASS_PACK_VALIDITY_MONTHS` in `gym_membership.py`).
- Cancelling a booking inside the cancellation window forfeits the class on a class pack.
- Only Gym Manager and System Manager can submit a membership; Front Desk can create and edit drafts.
- Bookings are normal (non-submittable) documents; "Cancelled" is a status.
- The Trainer role only sees its own sessions and their bookings (linked through `Employee.user_id`).
- `auto_renew` and `subscription` are stored but no job acts on them yet (see DECISIONS.md, R1).
- Two helper DocTypes, Gym Specialty and Gym Trainer Specialty, exist because a Table MultiSelect needs a child table.

## Layout
`gym_management/api.py` whitelisted APIs, `tasks.py` daily jobs, `permissions.py` trainer restrictions,
`seed.py` sample data, `gym_management/doctype/*` DocTypes, `report/` and `page/` for the report and the pages.