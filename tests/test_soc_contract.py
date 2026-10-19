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

    def test_partner_has_no_direct_doctype_permission(self):
        for doctype in ("hrd_soc_request", "hrd_soc_document"):
            data = self.read_json("doctype", doctype, f"{doctype}.json")
            roles = {row["role"] for row in data["permissions"]}
            self.assertNotIn("Partner Portal User", roles)

    def test_pdf_release_uses_native_helpdesk_agent_reply(self):
        service = (PACKAGE / "soc_service.py").read_text(encoding="utf-8")
        self.assertIn("ticket.reply_via_agent", service)
        self.assertIn("is_private=1", service)
        self.assertIn('document.released = 1', service)

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

