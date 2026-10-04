import frappe
from frappe import _
from frappe.model.document import Document

from hrdesk_helpdesk_customizations.partner_access import is_portal_admin
from hrdesk_helpdesk_customizations.portal_constants import (
    PARTNER_PORTAL_ROLE,
    PARTNER_REQUEST_MANAGER_ROLE,
)


class HRDPartnerMembership(Document):
    def validate(self):
        if not is_portal_admin():
            frappe.throw(
                _("Only an HR Desk portal administrator may manage partner access."),
                frappe.PermissionError,
            )
        partner = frappe.db.get_value(
            "HD Customer",
            self.partner,
            ["custom_hrdesk_org_type", "custom_hrdesk_partner_active"],
            as_dict=True,
        )
        if not partner or partner.custom_hrdesk_org_type != "Partner":
            frappe.throw(_("Partner Organization must reference an approved partner."))
        if self.active and not partner.custom_hrdesk_partner_active:
            frappe.throw(_("Activate the partner organization before its membership."))

    def on_update(self):
        self._sync_roles()
        self._clear_sessions_if_inactive()

    def on_trash(self):
        if not is_portal_admin():
            frappe.throw(
                _("Only an HR Desk portal administrator may revoke partner access."),
                frappe.PermissionError,
            )
        frappe.throw(
            _("Deactivate partner membership instead of deleting it so access revocation remains enforceable and auditable."),
            frappe.ValidationError,
        )

    def _sync_roles(self):
        user = frappe.get_doc("User", self.user)
        current = {row.role for row in user.roles}
        wanted = set()
        if self.active and self.portal_access:
            wanted.add(PARTNER_PORTAL_ROLE)
        if self.active and self.request_manager:
            wanted.add(PARTNER_REQUEST_MANAGER_ROLE)

        managed = {PARTNER_PORTAL_ROLE, PARTNER_REQUEST_MANAGER_ROLE}
        final_roles = (current - managed) | wanted
        if final_roles != current:
            user.set("roles", [{"role": role} for role in sorted(final_roles)])
            user.save(ignore_permissions=True)

    def _clear_sessions_if_inactive(self):
        if self.active and self.portal_access:
            return
        frappe.sessions.clear_sessions(user=self.user, force=True)
