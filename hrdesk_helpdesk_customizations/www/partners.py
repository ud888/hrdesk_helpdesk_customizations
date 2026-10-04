import frappe

from hrdesk_helpdesk_customizations.partner_access import require_partner


def get_context(context):
    if frappe.session.user == "Guest":
        frappe.redirect("/login?redirect-to=/partners")
    membership = require_partner()
    context.no_cache = 1
    context.title = "HR Desk Partner Portal"
    context.partner_user = frappe.session.user
    context.partner_name = frappe.db.get_value(
        "HD Customer", membership.partner, "customer_name"
    ) or membership.partner
    context.request_manager = bool(membership.request_manager)
    context.l1_support_access = bool(membership.l1_support_access)
    return context

