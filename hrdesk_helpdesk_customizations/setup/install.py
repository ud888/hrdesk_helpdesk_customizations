import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property

from hrdesk_helpdesk_customizations.feature_flags import (
    portal_team_restrictions_enabled,
)
from hrdesk_helpdesk_customizations.portal_constants import (
    COMMERCIAL_ROLE,
    COMMERCIAL_TEAM,
    ESCALATION_TEAM,
    INTERNAL_KB_ROLE,
    INTERNAL_TRIAGE_TEAM,
    KB_EDITOR_ROLE,
    PARTNER_PORTAL_ROLE,
    PARTNER_REQUEST_MANAGER_ROLE,
    PORTAL_ADMIN_ROLE,
)


def configure_site():
    """Idempotent one-site portal configuration, executed after site migration."""
    _ensure_roles()
    _ensure_custom_fields()
    _classify_existing_categories()
    _ensure_teams()
    _ensure_permissions()
    if portal_team_restrictions_enabled():
        _enforce_team_restriction()
    frappe.clear_cache()


def prepare_schema():
    """Create referenced roles and custom columns before migration-time hooks run."""
    _ensure_roles()
    _ensure_custom_fields()


def _ensure_roles():
    for role, desk_access in (
        (PARTNER_PORTAL_ROLE, 0),
        (PARTNER_REQUEST_MANAGER_ROLE, 0),
        (PORTAL_ADMIN_ROLE, 1),
        (KB_EDITOR_ROLE, 1),
        (INTERNAL_KB_ROLE, 1),
        (COMMERCIAL_ROLE, 1),
    ):
        if not frappe.db.exists("Role", role):
            frappe.get_doc(
                {"doctype": "Role", "role_name": role, "desk_access": desk_access}
            ).insert(ignore_permissions=True)


def _field(fieldname, label, fieldtype, **values):
    return {"fieldname": fieldname, "label": label, "fieldtype": fieldtype, **values}


def _ensure_custom_fields():
    create_custom_fields(
        {
            "HD Article Category": [
                _field(
                    "custom_hrdesk_audience",
                    "Knowledge Audience",
                    "Select",
                    options="Public\nCustomer\nPartner\nInternal",
                    default="Public",
                    reqd=1,
                    in_list_view=1,
                    in_standard_filter=1,
                )
            ],
            "HD Customer": [
                _field(
                    "custom_hrdesk_org_type",
                    "Portal Organization Type",
                    "Select",
                    options="Customer\nPartner",
                    default="Customer",
                    in_standard_filter=1,
                ),
                _field(
                    "custom_hrdesk_partner_active",
                    "Partner Active",
                    "Check",
                    default="0",
                ),
                _field(
                    "custom_hrdesk_l1_team",
                    "Partner L1 Support Team",
                    "Link",
                    options="HD Team",
                ),
                _field(
                    "custom_hrdesk_responsible_partner",
                    "Responsible Partner",
                    "Link",
                    options="HD Customer",
                    in_standard_filter=1,
                ),
            ],
            "HD Ticket": [
                _field(
                    "custom_portal_request_kind",
                    "Portal Request Kind",
                    "Select",
                    options="Customer Support\nPartner SOC",
                    default="Customer Support",
                    read_only=1,
                    in_standard_filter=1,
                ),
                _field(
                    "custom_partner_organization",
                    "Submitting Partner",
                    "Link",
                    options="HD Customer",
                    read_only=1,
                    in_standard_filter=1,
                ),
                _field(
                    "custom_partner_submitted_by",
                    "Partner Submitted By",
                    "Link",
                    options="User",
                    read_only=1,
                ),
                _field(
                    "custom_relevant_customer",
                    "Relevant Customer",
                    "Link",
                    options="HD Customer",
                    read_only=1,
                ),
                _field(
                    "custom_hrdesk_escalated",
                    "Escalated to HR Desk L2/L3",
                    "Check",
                    default="0",
                ),
                _field(
                    "custom_hrdesk_escalation_summary",
                    "Escalation Summary",
                    "Small Text",
                ),
            ],
        },
        update=True,
    )


def _classify_existing_categories():
    """Preserve current behavior: all pre-existing categories remain Public."""
    frappe.db.sql(
        """
        UPDATE `tabHD Article Category`
        SET custom_hrdesk_audience = 'Public'
        WHERE custom_hrdesk_audience IS NULL OR custom_hrdesk_audience = ''
        """
    )


def _ensure_teams():
    for team in (COMMERCIAL_TEAM, INTERNAL_TRIAGE_TEAM, ESCALATION_TEAM):
        if not frappe.db.exists("HD Team", {"team_name": team}):
            frappe.get_doc({"doctype": "HD Team", "team_name": team}).insert(
                ignore_permissions=True
            )


def _ensure_permissions():
    for role in (KB_EDITOR_ROLE, INTERNAL_KB_ROLE):
        _set_permission("HD Article", role, read=1)
        _set_permission("HD Article Category", role, read=1)
    _set_permission("HD Article", KB_EDITOR_ROLE, create=1, write=1, delete=1)
    _set_permission("HD Article Category", KB_EDITOR_ROLE, create=1, write=1, delete=1)


def _set_permission(doctype, role, **properties):
    if not frappe.db.exists(
        "Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}
    ):
        add_permission(doctype, role, 0)
    for property_name, value in properties.items():
        update_permission_property(doctype, role, 0, property_name, value)


def _enforce_team_restriction():
    frappe.db.set_single_value("HD Settings", "restrict_tickets_by_agent_group", 1)
    frappe.db.set_single_value(
        "HD Settings", "do_not_restrict_tickets_without_an_agent_group", 0
    )
