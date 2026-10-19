import frappe

from hrdesk_helpdesk_customizations.partner_access import (
    get_membership,
    has_membership_record,
    is_internal,
    is_request_manager,
)


def _soc_scope(user):
    if is_internal(user):
        return None
    membership = get_membership(user)
    if not membership:
        return "1 = 0"
    partner = frappe.db.escape(membership.partner)
    condition = f"`tabHRD SOC Request`.partner = {partner}"
    if not (membership.request_manager and is_request_manager(user)):
        submitter = frappe.db.escape(user)
        condition += f" AND `tabHRD SOC Request`.submitted_by = {submitter}"
    return condition


def soc_request_query(user=None, doctype=None):
    del doctype
    user = user or frappe.session.user
    if has_membership_record(user) and not get_membership(user):
        return "1 = 0"
    return _soc_scope(user) or ""


def can_access_soc_request(doc, user=None):
    user = user or frappe.session.user
    if is_internal(user):
        return True
    membership = get_membership(user)
    if not membership or doc.partner != membership.partner:
        return False
    return bool(
        membership.request_manager and is_request_manager(user)
    ) or doc.submitted_by == user


def soc_request_has_permission(doc, ptype=None, user=None, debug=False):
    del debug
    if ptype in {"create", "write", "delete", "share", "submit", "cancel"}:
        return is_internal(user)
    return can_access_soc_request(doc, user)


def soc_document_query(user=None, doctype=None):
    del doctype
    user = user or frappe.session.user
    if is_internal(user):
        return ""
    membership = get_membership(user)
    if not membership:
        return "1 = 0"
    partner = frappe.db.escape(membership.partner)
    request_scope = f"soc.partner = {partner}"
    if not (membership.request_manager and is_request_manager(user)):
        request_scope += f" AND soc.submitted_by = {frappe.db.escape(user)}"
    return (
        "`tabHRD SOC Document`.released = 1 AND EXISTS ("
        "SELECT 1 FROM `tabHRD SOC Request` soc "
        "WHERE soc.name = `tabHRD SOC Document`.soc_request AND "
        f"{request_scope})"
    )


def can_access_soc_document(doc, user=None):
    user = user or frappe.session.user
    if is_internal(user):
        return True
    if not doc.released:
        return False
    request = frappe.get_doc("HRD SOC Request", doc.soc_request)
    return can_access_soc_request(request, user)


def soc_document_has_permission(doc, ptype=None, user=None, debug=False):
    del debug
    if ptype in {"create", "write", "delete", "share", "submit", "cancel"}:
        return is_internal(user)
    return can_access_soc_document(doc, user)

