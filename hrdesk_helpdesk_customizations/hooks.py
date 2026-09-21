app_name = "hrdesk_helpdesk_customizations"
app_title = "HR Desk Helpdesk Customizations"
app_publisher = "HR Desk"
app_description = "Focused Helpdesk customizations for the HR Desk customer portal"
app_email = "support@hrdesk.id"
app_license = "MIT"

required_apps = ["helpdesk"]

override_whitelisted_methods = {
    "helpdesk.api.knowledge_base.get_categories": (
        "hrdesk_helpdesk_customizations.overrides.knowledge_base.get_categories"
    ),
    "helpdesk.api.config.get_config": (
        "hrdesk_helpdesk_customizations.overrides.config.get_config"
    ),
    "helpdesk.helpdesk.doctype.hd_ticket.api.new": (
        "hrdesk_helpdesk_customizations.overrides.ticket.new"
    ),
}

after_request = [
    "hrdesk_helpdesk_customizations.customer_portal.after_request",
]

doc_events = {
    "HD Ticket": {
        "before_insert": (
            "hrdesk_helpdesk_customizations.customer_portal.guard_customer_ticket_insert"
        )
    }
}
