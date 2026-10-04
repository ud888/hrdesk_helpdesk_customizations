import frappe
from frappe import _

from hrdesk_helpdesk_customizations.portal_constants import (
    AUDIENCE_CUSTOMER,
    AUDIENCE_INTERNAL,
    AUDIENCE_PARTNER,
    AUDIENCE_PUBLIC,
    COMMERCIAL_ROLE,
    INTERNAL_KB_ROLE,
    KB_EDITOR_ROLE,
    PARTNER_REQUEST_MANAGER_ROLE,
    PORTAL_ADMIN_ROLE,
)

INTERNAL_ROLES = {
    "Administrator",
    "System Manager",
    PORTAL_ADMIN_ROLE,
    INTERNAL_KB_ROLE,
    KB_EDITOR_ROLE,
    COMMERCIAL_ROLE,
}
EDITOR_ROLES = {"Administrator", "System Manager", KB_EDITOR_ROLE}
PORTAL_ADMIN_ROLES = {"Administrator", "System Manager", PORTAL_ADMIN_ROLE}
CUSTOMER_ROLES = {"HD Customer", "HD Customer Manager"}


def roles_for(user: str | None = None) -> set[str]:
    user = user or frappe.session.user
    if user == "Administrator":
        return {"Administrator"}
    return set(frappe.get_roles(user))


def is_internal(user: str | None = None) -> bool:
    return bool(roles_for(user).intersection(INTERNAL_ROLES))


def is_editor(user: str | None = None) -> bool:
    return bool(roles_for(user).intersection(EDITOR_ROLES))


def is_portal_admin(user: str | None = None) -> bool:
    return bool(roles_for(user).intersection(PORTAL_ADMIN_ROLES))


def get_membership(user: str | None = None):
    user = user or frappe.session.user
    if not user or user == "Guest":
        return None
    name = frappe.db.get_value(
        "HRD Partner Membership",
        {"user": user, "active": 1, "portal_access": 1},
        "name",
    )
    if not name:
        return None
    membership = frappe.db.get_value(
        "HRD Partner Membership",
        name,
        ["name", "user", "partner", "request_manager", "l1_support_access"],
        as_dict=True,
    )
    if not membership:
        return None
    active_partner = frappe.db.get_value(
        "HD Customer",
        membership.partner,
        ["custom_hrdesk_org_type", "custom_hrdesk_partner_active"],
        as_dict=True,
    )
    if not active_partner:
        return None
    if active_partner.custom_hrdesk_org_type != "Partner":
        return None
    if not active_partner.custom_hrdesk_partner_active:
        return None
    return membership


def has_membership_record(user: str | None = None) -> bool:
    """Identify suspended partner identities without granting any access."""
    user = user or frappe.session.user
    if not user or user == "Guest":
        return False
    return bool(frappe.db.exists("HRD Partner Membership", {"user": user}))


def require_partner(user: str | None = None):
    membership = get_membership(user)
    if not membership:
        frappe.throw(
            _("Akses Partner Portal memerlukan keanggotaan partner yang aktif."),
            frappe.PermissionError,
        )
    return membership


def allowed_audiences(user: str | None = None) -> set[str]:
    user = user or frappe.session.user
    if is_internal(user):
        return {
            AUDIENCE_PUBLIC,
            AUDIENCE_CUSTOMER,
            AUDIENCE_PARTNER,
            AUDIENCE_INTERNAL,
        }
    allowed = {AUDIENCE_PUBLIC}
    roles = roles_for(user)
    if user != "Guest" and roles.intersection(CUSTOMER_ROLES):
        allowed.add(AUDIENCE_CUSTOMER)
    if get_membership(user):
        allowed.update({AUDIENCE_CUSTOMER, AUDIENCE_PARTNER})
    return allowed


def can_read_category(category: str, user: str | None = None) -> bool:
    audience = frappe.db.get_value(
        "HD Article Category", category, "custom_hrdesk_audience"
    ) or AUDIENCE_PUBLIC
    return audience in allowed_audiences(user)


def can_read_article(article, user: str | None = None) -> bool:
    user = user or frappe.session.user
    status = article.get("status") if hasattr(article, "get") else article.status
    if status != "Published":
        return is_editor(user)
    category = (
        article.get("category") if hasattr(article, "get") else article.category
    )
    return bool(category and can_read_category(category, user))


def require_article(article, user: str | None = None) -> None:
    if not can_read_article(article, user):
        frappe.throw(_("Anda tidak memiliki akses ke artikel ini."), frappe.PermissionError)


def is_request_manager(user: str | None = None) -> bool:
    membership = get_membership(user)
    if not membership:
        return False
    return bool(
        membership.request_manager
        and PARTNER_REQUEST_MANAGER_ROLE in roles_for(user)
    )
