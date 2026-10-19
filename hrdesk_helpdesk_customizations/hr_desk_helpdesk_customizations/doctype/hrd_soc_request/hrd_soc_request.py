import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today, validate_email_address

from hrdesk_helpdesk_customizations.partner_access import get_membership, is_internal
from hrdesk_helpdesk_customizations.soc_rules import (
    SOC_STATUSES,
    can_transition,
    normalize_nonnegative,
    subscription_period,
)


STRUCTURED_FIELDS = {
    "soc_type",
    "customer",
    "customer_company_name",
    "customer_address",
    "customer_pic_name",
    "customer_pic_position",
    "customer_pic_email",
    "customer_pic_phone",
    "super_admin_email",
    "domain_workspace",
    "reseller_billing_contact_email",
    "reseller_billing_contact_phone",
    "package_type",
    "subscription_start_date",
    "subscription_end_date",
    "payment_term",
    "go_live_target_date",
    "estimated_employee_count",
    "number_of_admin_users",
    "number_of_payroll_groups",
    "implementation_included",
    "training_included",
    "add_ons",
}


class HRDSOCRequest(Document):
    def validate(self):
        self._set_derived_values()
        self._validate_values()
        self._validate_actor_and_transition()

    def _set_derived_values(self):
        self.submission_date = self.submission_date or today()
        start = getdate(self.subscription_start_date) if self.subscription_start_date else None
        end = getdate(self.subscription_end_date) if self.subscription_end_date else None
        self.subscription_period = subscription_period(start, end)

    def _validate_values(self):
        if self.soc_status not in SOC_STATUSES:
            frappe.throw(_("Status SOC tidak valid."))
        if self.subscription_start_date and self.subscription_end_date:
            if getdate(self.subscription_end_date) < getdate(self.subscription_start_date):
                frappe.throw(_("Tanggal akhir subscription tidak boleh mendahului tanggal mulai."))

        for fieldname, label in (
            ("estimated_employee_count", _("Estimated Employee Count")),
            ("number_of_admin_users", _("Number of Admin Users")),
            ("number_of_payroll_groups", _("Number of Payroll Groups")),
        ):
            try:
                self.set(fieldname, normalize_nonnegative(self.get(fieldname), label))
            except (TypeError, ValueError) as error:
                frappe.throw(str(error))

        for fieldname in (
            "customer_pic_email",
            "super_admin_email",
            "reseller_billing_contact_email",
        ):
            if self.get(fieldname):
                validate_email_address(self.get(fieldname), throw=True)

        seen = set()
        for row in self.add_ons or []:
            if row.add_on in seen:
                frappe.throw(_("Module / add-on tidak boleh dipilih lebih dari satu kali."))
            seen.add(row.add_on)
            if int(row.quantity or 0) <= 0:
                frappe.throw(_("Quantity add-on harus lebih besar dari nol."))

        if self.customer:
            responsible = frappe.db.get_value(
                "HD Customer", self.customer, "custom_hrdesk_responsible_partner"
            )
            if responsible != self.partner:
                frappe.throw(_("Customer yang dipilih tidak berada dalam cakupan partner."))

    def _validate_actor_and_transition(self):
        old = self.get_doc_before_save()
        if self.is_new():
            if is_internal():
                return
            membership = get_membership()
            if not membership or self.partner != membership.partner:
                frappe.throw(_("Partner SOC tidak valid."), frappe.PermissionError)
            if self.submitted_by != frappe.session.user:
                frappe.throw(_("Submitted By harus menggunakan user aktif."), frappe.PermissionError)
            if self.soc_status not in {"Draft", "Submitted"}:
                frappe.throw(_("Status awal SOC tidak valid."), frappe.PermissionError)
            return

        if old and old.soc_status != self.soc_status:
            if not can_transition(old.soc_status, self.soc_status):
                frappe.throw(
                    _("Perubahan status dari {0} ke {1} tidak diizinkan.").format(
                        old.soc_status, self.soc_status
                    )
                )

        if is_internal():
            self._protect_approved_values(old)
            if old and old.soc_status != "Approved" and self.soc_status == "Approved":
                self.approved_by = frappe.session.user
                self.approved_on = now_datetime()
            if self.soc_status == "Under Review" and old and old.soc_status in {"Approved", "PDF Sent"}:
                self.approved_by = None
                self.approved_on = None
            return

        membership = get_membership()
        if not membership or self.partner != membership.partner:
            frappe.throw(_("Akses SOC tidak diizinkan."), frappe.PermissionError)

        if getattr(self.flags, "hrdesk_link_ticket", False):
            changed = [field for field in STRUCTURED_FIELDS if self.has_value_changed(field)]
            if changed or self.has_value_changed("soc_status"):
                frappe.throw(_("Link ticket tidak boleh mengubah data SOC."), frappe.PermissionError)
            return

        if not getattr(self.flags, "hrdesk_partner_revision", False):
            frappe.throw(_("Partner tidak dapat mengubah SOC tanpa permintaan revisi."), frappe.PermissionError)
        if old.soc_status != "Revision Requested" or self.soc_status != "Under Review":
            frappe.throw(_("SOC hanya dapat diperbarui saat revisi diminta."), frappe.PermissionError)
        for fieldname in ("partner", "submitted_by", "submission_date", "ticket", "client_request_id"):
            if self.has_value_changed(fieldname):
                frappe.throw(_("Field identitas SOC tidak dapat diubah."), frappe.PermissionError)

    def _protect_approved_values(self, old):
        if not old:
            return
        changed = [field for field in STRUCTURED_FIELDS if self.has_value_changed(field)]
        if not changed:
            return
        if old.soc_status == "Completed":
            frappe.throw(_("SOC yang sudah completed tidak dapat diubah."))
        if old.soc_status in {"Approved", "PDF Sent"} and self.soc_status != "Under Review":
            frappe.throw(_("Kembalikan SOC ke Under Review sebelum mengubah data yang sudah disetujui."))

