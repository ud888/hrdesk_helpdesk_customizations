import frappe
from frappe import _

from hrdesk_helpdesk_customizations.feature_flags import (
    portal_team_restrictions_enabled,
)
from hrdesk_helpdesk_customizations.partner_access import (
    get_membership,
    has_membership_record,
    is_internal,
)
from hrdesk_helpdesk_customizations.portal_constants import (
    COMMERCIAL_TEAM,
    CUSTOMER_REQUEST_KIND,
    INTERNAL_TRIAGE_TEAM,
    SOC_REQUEST_KIND,
)
from hrdesk_helpdesk_customizations.portal_policy import (
    can_access_soc,
    ticket_scope_sql,
)


def ticket_query(user=None, doctype=None):
    del doctype
    user = user or frappe.session.user
    if is_internal(user):
        return ""
    membership = get_membership(user)
    if not membership:
        if has_membership_record(user):
            return "1 = 0"
        return ""
    return ticket_scope_sql(user, membership, frappe.db.escape)


def ticket_has_permission(doc, ptype=None, user=None, debug=False):
    del ptype, debug
    user = user or frappe.session.user
    if is_internal(user):
        return True
    membership = get_membership(user)
    if not membership:
        if has_membership_record(user):
            return False
        return True
    if doc.get("custom_portal_request_kind") == SOC_REQUEST_KIND:
        return can_access_soc(doc, membership)
    if user in {doc.owner, doc.contact, doc.raised_by}:
        return True
    if not membership.l1_support_access or not doc.customer:
        return False
    responsible = frappe.db.get_value(
        "HD Customer", doc.customer, "custom_hrdesk_responsible_partner"
    )
    return responsible == membership.partner


def route_ticket(doc, method=None):
    del method
    if doc.get("custom_portal_request_kind") == SOC_REQUEST_KIND:
        doc.agent_group = COMMERCIAL_TEAM
        return
    doc.custom_portal_request_kind = CUSTOMER_REQUEST_KIND
    if not portal_team_restrictions_enabled():
        return
    team = None
    if doc.customer:
        partner = frappe.db.get_value(
            "HD Customer", doc.customer, "custom_hrdesk_responsible_partner"
        )
        if partner:
            active, team = frappe.db.get_value(
                "HD Customer",
                partner,
                ["custom_hrdesk_partner_active", "custom_hrdesk_l1_team"],
            ) or (0, None)
            if not active:
                team = None
    doc.agent_group = team or INTERNAL_TRIAGE_TEAM


def validate_ticket(doc, method=None):
    del method
    old = doc.get_doc_before_save()
    if not old or is_internal():
        return
    membership = get_membership()
    if not membership:
        return
    protected = {
        "custom_portal_request_kind",
        "custom_partner_organization",
        "custom_partner_submitted_by",
        "agent_group",
        "custom_hrdesk_escalated",
        "custom_hrdesk_escalation_summary",
    }
    changed = [field for field in protected if doc.has_value_changed(field)]
    if changed:
        frappe.throw(
            _("Partner tidak dapat mengubah routing atau field internal."),
            frappe.PermissionError,
        )


def validate_partner_file(doc, method=None):
    del method
    membership = get_membership()
    if not membership or is_internal():
        return
    if not doc.is_private:
        frappe.throw(_("Lampiran partner wajib disimpan sebagai file privat."))
    if not doc.attached_to_doctype:
        return
    if doc.attached_to_doctype not in {"HD Ticket", "Communication"}:
        frappe.throw(_("Tujuan lampiran tidak diizinkan."), frappe.PermissionError)
