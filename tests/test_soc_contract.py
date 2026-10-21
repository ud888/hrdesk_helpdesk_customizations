import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "hrdesk_helpdesk_customizations"
MODULE = PACKAGE / "hr_desk_helpdesk_customizations"


class SOCContractTest(unittest.TestCase):
    def read_json(self, *parts):
        return json.loads((MODULE.joinpath(*parts)).read_text(encoding="utf-8"))

    def test_soc_request_links_one_ticket_and_has_idempotency_key(self):
        data = self.read_json(
            "doctype", "hrd_soc_request", "hrd_soc_request.json"
        )
        fields = {field["fieldname"]: field for field in data["fields"]}
        self.assertEqual(fields["ticket"]["options"], "HD Ticket")
        self.assertEqual(fields["ticket"]["unique"], 1)
        self.assertEqual(fields["client_request_id"]["unique"], 1)
        self.assertEqual(fields["partner"]["options"], "HD Customer")

    def test_add_ons_are_a_child_table_backed_by_configurable_master(self):
        request = self.read_json(
            "doctype", "hrd_soc_request", "hrd_soc_request.json"
        )
        fields = {field["fieldname"]: field for field in request["fields"]}
        self.assertEqual(fields["add_ons"]["options"], "HRD SOC Request Add-on")
        child = self.read_json(
            "doctype", "hrd_soc_request_add_on", "hrd_soc_request_add_on.json"
        )
        self.assertEqual(child["istable"], 1)
        child_fields = {field["fieldname"]: field for field in child["fields"]}
        self.assertEqual(child_fields["add_on"]["options"], "HRD SOC Add-on Master")

    def test_hyphenated_doctypes_expose_frappe_controller_aliases(self):
        master = (
            MODULE / "doctype" / "hrd_soc_add_on_master" / "hrd_soc_add_on_master.py"
        ).read_text(encoding="utf-8")
        child = (
            MODULE
            / "doctype"
            / "hrd_soc_request_add_on"
            / "hrd_soc_request_add_on.py"
        ).read_text(encoding="utf-8")
        self.assertIn("HRDSOCAddonMaster = HRDSOCAddOnMaster", master)
        self.assertIn("HRDSOCRequestAddon = HRDSOCRequestAddOn", child)

    def test_partner_has_no_direct_doctype_permission(self):
        for doctype in ("hrd_soc_request", "hrd_soc_document"):
            data = self.read_json("doctype", doctype, f"{doctype}.json")
            roles = {row["role"] for row in data["permissions"]}
            self.assertNotIn("Partner Portal User", roles)

    def test_pdf_release_uses_native_helpdesk_agent_reply(self):
        service = (PACKAGE / "soc_service.py").read_text(encoding="utf-8")
        self.assertIn("ticket.reply_via_agent", service)
        self.assertIn("is_private=1", service)
        self.assertIn("publish_document_pair", service)
        self.assertIn('document.document_status = "Published"', service)

    def test_workflow_has_paired_documents_and_protected_handoff(self):
        request = self.read_json(
            "doctype", "hrd_soc_request", "hrd_soc_request.json"
        )
        fields = {field["fieldname"]: field for field in request["fields"]}
        self.assertEqual(
            fields["soc_status"]["options"].splitlines(),
            [
                "SOC Requested",
                "SOC Published",
                "SOC Signed",
                "Workspace Creation",
                "Workspace Created",
                "Cancelled",
            ],
        )
        document = self.read_json(
            "doctype", "hrd_soc_document", "hrd_soc_document.json"
        )
        document_fields = {field["fieldname"]: field for field in document["fields"]}
        self.assertIn("Partner SOC", document_fields["document_type"]["options"])
        self.assertIn("End Customer SAC", document_fields["document_type"]["options"])
        handoff = self.read_json(
            "doctype", "hrd_soc_handoff", "hrd_soc_handoff.json"
        )
        handoff_fields = {field["fieldname"]: field for field in handoff["fields"]}
        self.assertEqual(handoff_fields["access_secret"]["fieldtype"], "Password")
        self.assertNotIn("Partner Portal User", {row["role"] for row in handoff["permissions"]})
        service = (PACKAGE / "soc_service.py").read_text(encoding="utf-8")
        self.assertIn("frappe.session.user != request.submitted_by", service)
        self.assertIn("def get_workspace_handoff", service)

    def test_hds_is_authority_superset_and_hdt_is_restricted(self):
        service = (PACKAGE / "soc_service.py").read_text(encoding="utf-8")
        self.assertIn("{COMMERCIAL_ROLE, TECHNICAL_ROLE}", service)
        self.assertIn("def require_hds", service)
        self.assertIn("def require_hdt", service)
        request = self.read_json(
            "doctype", "hrd_soc_request", "hrd_soc_request.json"
        )
        permissions = {row["role"]: row for row in request["permissions"]}
        self.assertEqual(permissions["HR Desk Technical"]["read"], 1)
        self.assertNotIn("create", permissions["HR Desk Technical"])

    def test_print_formats_use_blank_signature_placeholders(self):
        for directory, filename in (
            ("partner_soc_new_customer", "partner_soc_new_customer.json"),
            ("end_customer_sac_new_customer", "end_customer_sac_new_customer.json"),
        ):
            data = self.read_json("print_format", directory, filename)
            self.assertIn("[Tanda Tangan]", data["html"])
            self.assertIn("[Nama]", data["html"])
            self.assertIn("[Jabatan]", data["html"])
            self.assertIn("[Tanggal]", data["html"])

    def test_request_captures_template_commercial_fields(self):
        request = self.read_json(
            "doctype", "hrd_soc_request", "hrd_soc_request.json"
        )
        fields = {field["fieldname"] for field in request["fields"]}
        self.assertTrue(
            {
                "customer_tax_id",
                "super_admin_name",
                "super_admin_position",
                "subscription_number",
                "package_description",
                "monthly_price",
                "partner_discount_percent",
                "payment_scheme",
            }.issubset(fields)
        )

    def test_file_permission_hook_covers_soc_documents_and_tickets(self):
        access = (PACKAGE / "knowledge_access.py").read_text(encoding="utf-8")
        self.assertIn('doc.attached_to_doctype == "HRD SOC Document"', access)
        self.assertIn('doc.attached_to_doctype == "HD Ticket"', access)
        self.assertIn('doc.attached_to_doctype == "Communication"', access)

    def test_end_customer_guard_explicitly_exempts_active_partner(self):
        portal = (PACKAGE / "customer_portal.py").read_text(encoding="utf-8")
        self.assertIn("PARTNER_PORTAL_ROLE in frappe.get_roles", portal)
        self.assertIn("if get_membership():", portal)


if __name__ == "__main__":
    unittest.main()

