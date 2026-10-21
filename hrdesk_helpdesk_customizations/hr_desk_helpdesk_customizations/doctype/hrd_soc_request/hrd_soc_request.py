import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today, validate_email_address

from hrdesk_helpdesk_customizations.partner_access import (
    get_membership,
    is_internal,
    roles_for,
)
from hrdesk_helpdesk_customizations.portal_constants import (
    COMMERCIAL_ROLE,
    TECHNICAL_ROLE,
)
from hrdesk_helpdesk_customizations.soc_rules import (
    SOC_STATUSES,
    actor_can_transition,
    can_transition,
    normalize_nonnegative,
    subscription_period,
)


STRUCTURED_FIELDS = {
    "soc_type",
    "customer",
    "customer_company_name",
    "customer_address",
    "customer_tax_id",
    "customer_pic_name",
    "customer_pic_position",
    "customer_pic_email",
    "customer_pic_phone",
    "super_admin_name",
    "super_admin_position",
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
    "subscription_number",
    "package_description",
    "monthly_price",
    "annual_subtotal",
    "partner_discount_percent",
    "annual_total_after_discount",
    "payment_scheme",
    "add_ons",
}

REQUIRED_BUSINESS_FIELDS = (
    ("customer_company_name", "Customer Company Name"),
    ("customer_address", "Customer Address"),
    ("customer_tax_id", "Customer Tax ID / NPWP"),
    ("customer_pic_name", "Customer PIC Name"),
    ("customer_pic_position", "Customer PIC Position"),
    ("customer_pic_email", "Customer PIC Email"),
    ("customer_pic_phone", "Customer PIC Phone"),
    ("super_admin_name", "Super Admin Name"),
    ("super_admin_position", "Super Admin Position"),
    ("super_admin_email", "Email for Super Admin"),
    ("domain_workspace", "Domain Workspace"),
    ("reseller_billing_contact_email", "Reseller Billing Contact Email"),
    ("reseller_billing_contact_phone", "Reseller Billing Contact Phone"),
    ("package_type", "Package Type"),
    ("subscription_start_date", "Subscription Start Date"),
    ("subscription_end_date", "Subscription End Date"),
    ("payment_term", "Term of Payment to HR Desk"),
    ("go_live_target_date", "Go-Live Target Date"),
    ("subscription_number", "Subscription Number"),
    ("package_description", "Package Description"),
    ("payment_scheme", "Payment Scheme"),
)


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
        monthly_price = float(self.monthly_price or 0)
        discount = float(self.partner_discount_percent or 0)
        self.annual_subtotal = monthly_price * 12
        self.annual_total_after_discount = self.annual_subtotal * (100 - discount) / 100

    def _validate_values(self):
        if self.soc_status not in SOC_STATUSES:
            frappe.throw(_("Status SOC tidak valid."))
        if self.soc_status == "Cancelled":
            return
        missing = [label for fieldname, label in REQUIRED_BUSINESS_FIELDS if not self.get(fieldname)]
        if missing:
            frappe.throw(
                _("Lengkapi seluruh field SOC yang wajib: {0}.").format(
                    ", ".join(missing)
                )
            )
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

        for fieldname, label in (
            ("estimated_employee_count", _("Estimated Employee Count")),
            ("number_of_admin_users", _("Number of Admin Users")),
            ("number_of_payroll_groups", _("Number of Payroll Groups")),
        ):
            if int(self.get(fieldname) or 0) <= 0:
                frappe.throw(_("{0} harus lebih besar dari nol.").format(label))

        if float(self.monthly_price or 0) <= 0:
            frappe.throw(_("Monthly Price harus lebih besar dari nol."))
        if not 0 <= float(self.partner_discount_percent or 0) <= 100:
            frappe.throw(_("Partner Discount Percent harus berada antara 0 dan 100."))

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
            if self.soc_status != "SOC Requested":
                frappe.throw(_("Status awal SOC tidak valid."), frappe.PermissionError)
            return

        if old and old.soc_status != self.soc_status:
            if not (
                getattr(self.flags, "hrdesk_workflow_action", False)
                or getattr(self.flags, "hrdesk_emergency_override", False)
            ):
                frappe.throw(
                    _("Status SOC hanya dapat diubah melalui aksi workflow."),
                    frappe.PermissionError,
                )
            if not getattr(self.flags, "hrdesk_emergency_override", False) and not can_transition(
                old.soc_status, self.soc_status
            ):
                frappe.throw(
                    _("Perubahan status dari {0} ke {1} tidak diizinkan.").format(
                        old.soc_status, self.soc_status
                    )
                )

            if not getattr(self.flags, "hrdesk_emergency_override", False):
                actor = getattr(self.flags, "hrdesk_workflow_actor", "")
                if not actor_can_transition(actor, old.soc_status, self.soc_status):
                    frappe.throw(_("Aktor tidak diizinkan melakukan transisi SOC ini."), frappe.PermissionError)

        if is_internal():
            roles = roles_for()
            changed = [field for field in STRUCTURED_FIELDS if self.has_value_changed(field)]
            if (
                TECHNICAL_ROLE in roles
                and COMMERCIAL_ROLE not in roles
                and not getattr(self.flags, "hrdesk_workflow_action", False)
            ):
                frappe.throw(
                    _("HDT hanya dapat mengubah SOC melalui aksi provisioning."),
                    frappe.PermissionError,
                )
            if changed and TECHNICAL_ROLE in roles and COMMERCIAL_ROLE not in roles:
                frappe.throw(_("HDT tidak dapat mengubah data komersial SOC."), frappe.PermissionError)
            if (
                changed
                and frappe.session.user != "Administrator"
                and not roles.intersection({"System Manager", COMMERCIAL_ROLE})
            ):
                frappe.throw(_("Hanya HDS yang dapat mengubah data komersial SOC."), frappe.PermissionError)
            self._protect_published_values(old)
            return

        membership = get_membership()
        if not membership or self.partner != membership.partner:
            frappe.throw(_("Akses SOC tidak diizinkan."), frappe.PermissionError)

        if getattr(self.flags, "hrdesk_link_ticket", False):
            changed = [field for field in STRUCTURED_FIELDS if self.has_value_changed(field)]
            if changed or self.has_value_changed("soc_status"):
                frappe.throw(_("Link ticket tidak boleh mengubah data SOC."), frappe.PermissionError)
            return

        if getattr(self.flags, "hrdesk_partner_cancellation", False):
            changed = [field for field in STRUCTURED_FIELDS if self.has_value_changed(field)]
            if changed or self.has_value_changed("soc_status"):
                frappe.throw(_("Cancellation request tidak boleh mengubah data SOC."), frappe.PermissionError)
            return

        if not getattr(self.flags, "hrdesk_partner_revision", False):
            frappe.throw(_("Partner tidak dapat mengubah SOC tanpa permintaan amendment."), frappe.PermissionError)
        if old.soc_status != "SOC Requested" or not old.partner_update_allowed:
            frappe.throw(_("SOC hanya dapat diperbarui setelah amendment dibuka oleh HDS."), frappe.PermissionError)
        for fieldname in ("partner", "submitted_by", "submission_date", "ticket", "client_request_id"):
            if self.has_value_changed(fieldname):
                frappe.throw(_("Field identitas SOC tidak dapat diubah."), frappe.PermissionError)

    def _protect_published_values(self, old):
        if not old:
            return
        changed = [field for field in STRUCTURED_FIELDS if self.has_value_changed(field)]
        if not changed:
            return
        if old.soc_status in {"Workspace Creation", "Workspace Created", "Cancelled"}:
            frappe.throw(_("Data SOC tidak dapat diubah pada status ini."))
        if old.soc_status in {"SOC Published", "SOC Signed"} and self.soc_status != "SOC Requested":
            frappe.throw(_("Gunakan aksi Reopen for Amendment sebelum mengubah data yang sudah dipublikasikan."))

