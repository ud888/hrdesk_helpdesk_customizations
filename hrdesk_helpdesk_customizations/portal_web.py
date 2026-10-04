import frappe

from hrdesk_helpdesk_customizations.portal_constants import PARTNER_DOMAIN


def before_request():
    request = getattr(frappe.local, "request", None)
    if not request or request.method not in {"GET", "HEAD"}:
        return
    host = (request.host or "").split(":", 1)[0].lower()
    if host == PARTNER_DOMAIN and request.path in {"", "/"}:
        frappe.redirect("/partners")


def after_request(response, request):
    if request.path == "/partners" or request.path.startswith("/partners/"):
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
        response.headers.add("Vary", "Cookie")

