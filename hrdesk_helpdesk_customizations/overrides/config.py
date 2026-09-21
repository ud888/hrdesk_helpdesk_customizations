import frappe
from helpdesk.api.config import get_config as get_helpdesk_config

from hrdesk_helpdesk_customizations.feature_flags import (
    customer_portal_ticketing_enabled,
)


@frappe.whitelist(allow_guest=True)
def get_config():
    """Preserve Helpdesk configuration and expose the customer portal flag."""
    config = get_helpdesk_config()
    config["customer_portal_ticketing_enabled"] = int(
        customer_portal_ticketing_enabled()
    )
    return config
