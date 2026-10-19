import frappe
from frappe import _
from frappe.model.document import Document


class HRDSOCDocument(Document):
    def on_trash(self):
        frappe.throw(
            _("Versi dokumen SOC dipertahankan untuk audit dan tidak dapat dihapus."),
            frappe.ValidationError,
        )

