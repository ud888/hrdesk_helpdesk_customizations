"""Feature flags owned by the HR Desk Helpdesk customization app."""

import frappe
from helpdesk.utils import is_agent

CUSTOMER_PORTAL_TICKETING_ENABLED = "CUSTOMER_PORTAL_TICKETING_ENABLED"


def customer_portal_ticketing_enabled() -> bool:
    """Return the site-config flag, defaulting to KB-only mode."""
    value = frappe.conf.get(CUSTOMER_PORTAL_TICKETING_ENABLED, False)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def has_agent_ticket_access(user: str | None = None) -> bool:
    """Match Helpdesk's agent/administrator access without changing roles."""
    user = user or frappe.session.user
    return is_agent(user) or "System Manager" in frappe.get_roles(user)


def is_customer_portal_user(user: str | None = None) -> bool:
    """Users without Helpdesk desk access use the customer portal."""
    return not has_agent_ticket_access(user)
