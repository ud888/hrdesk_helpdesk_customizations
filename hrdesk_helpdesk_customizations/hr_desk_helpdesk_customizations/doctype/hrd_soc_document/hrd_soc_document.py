import frappe
from frappe import _
from frappe.model.document import Document


class HRDSOCDocument(Document):
    def validate(self):
        if self.is_new():
            duplicate = frappe.db.exists(
                "HRD SOC Document",
                {
                    "soc_request": self.soc_request,
                    "version": self.version,
                    "document_type": self.document_type,
                },
            )
            if duplicate:
                frappe.throw(
                    _("Dokumen {0} untuk versi request ini sudah ada.").format(
                        self.document_type
                    )
                )
            return
        if not getattr(self.flags, "hrdesk_document_action", False):
            old = self.get_doc_before_save()
            protected = (
                "soc_request",
                "ticket",
                "request_version",
                "document_type",
                "version",
                "print_format",
                "file",
                "document_status",
                "released",
                "signed_file",
            )
            if old and any(self.has_value_changed(field) for field in protected):
                frappe.throw(_("Dokumen SOC/SAC hanya dapat diubah melalui aksi workflow."))

    def on_trash(self):
        frappe.throw(
            _("Versi dokumen SOC dipertahankan untuk audit dan tidak dapat dihapus."),
            frappe.ValidationError,
        )

