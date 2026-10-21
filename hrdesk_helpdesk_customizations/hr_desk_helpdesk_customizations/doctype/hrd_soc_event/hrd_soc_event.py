import frappe
from frappe import _
from frappe.model.document import Document


class HRDSOCEvent(Document):
    def validate(self):
        if not self.is_new():
            frappe.throw(_("Riwayat SOC bersifat permanen dan tidak dapat diubah."))

    def on_trash(self):
        frappe.throw(_("Riwayat SOC bersifat permanen dan tidak dapat dihapus."))

