"""Knowledge-base-only behavior for the Helpdesk customer portal."""

from html import escape

import frappe
from frappe import _

from hrdesk_helpdesk_customizations.feature_flags import (
    customer_portal_ticketing_enabled,
    has_agent_ticket_access,
    is_customer_portal_user,
)

HELPDESK_ROOTS = {"/helpdesk", "/helpdesk/"}
CUSTOMER_TICKET_PREFIX = "/helpdesk/my-tickets"
KNOWLEDGE_BASE_PATH = "/helpdesk/kb-public"
PORTAL_SCRIPT_PATH = (
    "/assets/hrdesk_helpdesk_customizations/js/customer_portal_kb_only.js"
)
INJECTION_MARKER = "data-hrdesk-customer-portal-mode"
DISABLED_MESSAGE = _(
    "Customer portal ticketing is currently disabled. Please use the Knowledge Base."
)


def after_request(response, request) -> None:
    """Redirect blocked customer routes and inject the KB-only UI guard."""
    if not _is_helpdesk_page_request(request):
        return
    if customer_portal_ticketing_enabled() or not is_customer_portal_user():
        return

    path = request.path.rstrip("/") or "/"
    if path == "/helpdesk" or path.startswith(CUSTOMER_TICKET_PREFIX):
        _redirect_to_knowledge_base(response)
        return

    if not _is_html_response(response):
        return

    html = response.get_data(as_text=True)
    if INJECTION_MARKER in html or "</body>" not in html:
        return

    script = (
        f'<script src="{escape(PORTAL_SCRIPT_PATH, quote=True)}" '
        f'{INJECTION_MARKER}="kb-only" '
        'data-ticketing-enabled="false" '
        'data-customer-portal-user="true"></script>'
    )
    response.set_data(html.replace("</body>", f"{script}</body>", 1))
    response.headers["Cache-Control"] = "private, no-store"
    response.headers.add("Vary", "Cookie")


def guard_customer_ticket_insert(doc, method=None) -> None:
    """Prevent customer-role inserts while preserving agent/email processing."""
    del method
    if getattr(doc, "custom_portal_request_kind", None) == "Partner SOC":
        from hrdesk_helpdesk_customizations.partner_access import get_membership

        if get_membership():
            return
    if customer_portal_ticketing_enabled() or has_agent_ticket_access():
        return

    roles = set(frappe.get_roles(frappe.session.user))
    customer_roles = {"HD Customer", "HD Customer Manager"}
    if frappe.session.user == "Guest" or roles.intersection(customer_roles):
        frappe.throw(DISABLED_MESSAGE, frappe.PermissionError)


def _is_helpdesk_page_request(request) -> bool:
    return request.method in {"GET", "HEAD"} and (
        request.path in HELPDESK_ROOTS or request.path.startswith("/helpdesk/")
    )


def _is_html_response(response) -> bool:
    return bool(
        response
        and not response.is_streamed
        and response.content_type
        and response.content_type.startswith("text/html")
    )


def _redirect_to_knowledge_base(response) -> None:
    response.status_code = 302
    response.headers["Location"] = KNOWLEDGE_BASE_PATH
    response.headers["Cache-Control"] = "private, no-store"
    response.headers.add("Vary", "Cookie")
    response.set_data(b"")
