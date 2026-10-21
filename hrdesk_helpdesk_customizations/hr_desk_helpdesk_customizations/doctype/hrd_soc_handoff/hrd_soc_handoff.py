import frappe
from frappe import _
from frappe.model.document import Document


class HRDSOCHandoff(Document):
    def validate(self):
        if self.is_new():
            if frappe.db.exists("HRD SOC Handoff", {"soc_request": self.soc_request}):
                frappe.throw(_("Workspace handoff untuk SOC ini sudah ada."))
            return
        if not getattr(self.flags, "hrdesk_handoff_action", False):
            frappe.throw(_("Workspace handoff hanya dapat diubah melalui aksi workflow."))

    def on_trash(self):
        frappe.throw(_("Workspace handoff tidak dapat dihapus."))

