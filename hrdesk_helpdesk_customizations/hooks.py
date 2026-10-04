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
    "helpdesk.api.knowledge_base.get_category_articles": (
        "hrdesk_helpdesk_customizations.overrides.knowledge_base.get_category_articles"
    ),
    "helpdesk.api.knowledge_base.get_article": (
        "hrdesk_helpdesk_customizations.overrides.knowledge_base.get_article"
    ),
    "helpdesk.api.knowledge_base.get_category_title": (
        "hrdesk_helpdesk_customizations.overrides.knowledge_base.get_category_title"
    ),
    "helpdesk.api.knowledge_base.increment_views": (
        "hrdesk_helpdesk_customizations.overrides.knowledge_base.increment_views"
    ),
    "helpdesk.api.article.search": (
        "hrdesk_helpdesk_customizations.overrides.knowledge_base.search"
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
    "hrdesk_helpdesk_customizations.portal_web.after_request",
]

before_request = ["hrdesk_helpdesk_customizations.portal_web.before_request"]

web_include_css = [
    "/assets/hrdesk_helpdesk_customizations/css/partner_portal.css",
]

before_migrate = ["hrdesk_helpdesk_customizations.setup.install.prepare_schema"]
after_migrate = ["hrdesk_helpdesk_customizations.setup.install.configure_site"]

permission_query_conditions = {
    "HD Article": "hrdesk_helpdesk_customizations.knowledge_access.article_query",
    "HD Article Category": "hrdesk_helpdesk_customizations.knowledge_access.category_query",
    "HD Ticket": "hrdesk_helpdesk_customizations.ticket_access.ticket_query",
}

has_permission = {
    "HD Article": "hrdesk_helpdesk_customizations.knowledge_access.article_has_permission",
    "HD Article Category": "hrdesk_helpdesk_customizations.knowledge_access.category_has_permission",
    "HD Ticket": "hrdesk_helpdesk_customizations.ticket_access.ticket_has_permission",
    "File": "hrdesk_helpdesk_customizations.knowledge_access.file_has_permission",
}

doc_events = {
    "HD Ticket": {
        "before_insert": [
            "hrdesk_helpdesk_customizations.customer_portal.guard_customer_ticket_insert",
            "hrdesk_helpdesk_customizations.ticket_access.route_ticket",
        ],
        "validate": "hrdesk_helpdesk_customizations.ticket_access.validate_ticket",
    },
    "HD Article": {
        "validate": "hrdesk_helpdesk_customizations.knowledge_access.validate_article",
        "on_update": "hrdesk_helpdesk_customizations.knowledge_access.secure_article_attachments",
    },
    "HD Article Category": {
        "validate": "hrdesk_helpdesk_customizations.knowledge_access.validate_category",
        "on_update": "hrdesk_helpdesk_customizations.knowledge_access.secure_category_attachments",
    },
    "File": {
        "validate": "hrdesk_helpdesk_customizations.ticket_access.validate_partner_file",
        "after_insert": "hrdesk_helpdesk_customizations.knowledge_access.secure_article_file",
        "on_update": "hrdesk_helpdesk_customizations.knowledge_access.secure_article_file",
    },
}
