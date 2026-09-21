import frappe
from helpdesk.api.knowledge_base import get_categories as get_helpdesk_categories

from hrdesk_helpdesk_customizations.ordering import sort_categories


@frappe.whitelist(allow_guest=True)
def get_categories() -> list[dict]:
    """Preserve Helpdesk category filtering and apply HR Desk presentation order."""
    return list(sort_categories(get_helpdesk_categories()))

