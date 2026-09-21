import frappe
from frappe import _
from helpdesk.helpdesk.doctype.hd_ticket.api import new as create_helpdesk_ticket

from hrdesk_helpdesk_customizations.feature_flags import (
    customer_portal_ticketing_enabled,
    has_agent_ticket_access,
)


@frappe.whitelist()
def new(doc: dict, attachments: list[dict] | None = None):
    """Block customer portal creation while retaining the upstream agent API."""
    if not customer_portal_ticketing_enabled() and not has_agent_ticket_access():
        frappe.throw(
            _(
                "Customer portal ticketing is currently disabled. "
                "Please use the Knowledge Base."
            ),
            frappe.PermissionError,
        )
    return create_helpdesk_ticket(doc, attachments or [])
