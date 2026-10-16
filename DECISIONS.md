# Decisions

**R1. ERPNext Subscription or custom renewal?** Custom logic. Submitting a Gym Membership creates and submits one
Sales Invoice for the plan's Item. The invoice is idempotent: it is skipped if `sales_invoice` is set or an invoice
already points to the membership through the `gym_membership` custom field. Renewal is a new Gym Membership (Renew button).
Subscription would give automatic invoice generation, proration and grace periods, but it needs a Subscription Plan per
Membership Plan (a second record to keep in sync), it is built for open-ended recurring billing, and neither class packs
(consumption, not time) nor freezes (pausing and extending the end date) map onto it. A freeze would mean cancelling and
recreating the subscription. The cost of my choice: renewals are manual. `auto_renew` and `subscription` exist as specified
but no job acts on them yet.

**R2. Trainers.** A separate Gym Trainer whose name is the Employee ID (`autoname: field:employee`), so the 1:1 link is
enforced by the database and not only by validation. Custom fields on Employee would mix gym data into HR records, and the Trainer
role would need access to Employee. A separate doctype keeps `is_active` independent of employment status and holds the
specialties. Cost: two helper doctypes (Gym Specialty, Gym Trainer Specialty), because a Table MultiSelect requires a child
table. A Trainer user is linked to its profile through `Employee.user_id` and only sees its own sessions
(`permission_query_conditions` and `has_permission` hooks).

**R3. Pro-rated refund on cancellation (design only).** Refund = amount paid x unused / total, where for time-based plans
unused = days from the cancellation date to `end_date` and total = plan days (frozen days included in both). For class packs it is
`classes_remaining / classes_included`. A configurable cancellation fee in Gym Settings is deducted. Implementation: a "Cancel and
Refund" action creates a return Sales Invoice (credit note, `is_return`, `return_against`) for the computed amount and, if the original
was paid, a Payment Entry of type Pay. If the invoice is unpaid it is simply cancelled. Guards: refunds only for submitted
memberships, never twice (look for an existing return), rounding with the currency precision. Today, cancelling a membership
cancels its whole invoice, so there is no partial refund yet.

**R4. Two people booking the last seat.** `validate` takes a row lock on the Class Session (`SELECT ... FOR UPDATE`, i.e.
`for_update=True`), then checks duplicates, validity of the membership and the remaining capacity inside that lock. The seat is taken by an
atomic `UPDATE ... SET booked_count = booked_count + 1` and not by read-modify-write, `classes_remaining` is decremented the same way,
and waitlist promotion runs under the same lock. The second request waits for the first transaction, then sees the updated
count and is waitlisted or rejected. Alternatives I rejected: a unique index on (session, member) (cancelled bookings would
need a partial index, which MariaDB lacks) and a Redis lock (extra moving part, and it does not cover the transaction). Caveat: the
automated tests exercise this logic sequentially; I did not write a multi-process concurrency test.

**R5. References.** Frappe docs: Controllers, Document Events and hooks (`scheduler_events`, `fixtures`,
`permission_query_conditions`, `has_permission`), Table MultiSelect, Script Report, Calendar View, Page, Form Client Scripting. Source:
`frappe/model/document.py` (`run_method`, why `validate` does not run on submitted documents and `before_update_after_submit` does),
`frappe/desk/calendar.py`, `erpnext/selling/doctype/customer/customer.py` (`validate_customer_group`),
`erpnext/accounts/doctype/subscription/subscription.py` (for R1).

**Other choices.** No Server Scripts: all logic lives in the app. Class pack validity of 12 months is an assumption.
Early renewal is allowed because the single-active rule only blocks overlapping memberships.