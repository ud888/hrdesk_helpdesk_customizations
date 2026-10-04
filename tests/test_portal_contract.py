import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PartnerPortalContractTest(unittest.TestCase):
    def test_membership_schema_has_unique_user_and_partner(self):
        path = ROOT / "hrdesk_helpdesk_customizations" / "hr_desk_helpdesk_customizations" / "doctype" / "hrd_partner_membership" / "hrd_partner_membership.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        fields = {field["fieldname"]: field for field in data["fields"]}
        self.assertEqual(fields["user"]["unique"], 1)
        self.assertEqual(fields["partner"]["options"], "HD Customer")

    def test_hooks_cover_all_public_kb_paths(self):
        hooks = (ROOT / "hrdesk_helpdesk_customizations" / "hooks.py").read_text(
            encoding="utf-8"
        )
        for endpoint in (
            "get_categories",
            "get_category_articles",
            "get_article",
            "get_category_title",
            "increment_views",
            "helpdesk.api.article.search",
        ):
            self.assertIn(endpoint, hooks)

    def test_partner_page_does_not_expose_internal_notes(self):
        api = (ROOT / "hrdesk_helpdesk_customizations" / "api" / "partner_portal.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"HD Ticket Comment"', api)
        self.assertIn('"Communication"', api)

    def test_restricted_article_files_are_secured_after_file_creation(self):
        hooks = (ROOT / "hrdesk_helpdesk_customizations" / "hooks.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"after_insert": "hrdesk_helpdesk_customizations.knowledge_access.secure_article_file"', hooks)
        self.assertIn('"on_update": "hrdesk_helpdesk_customizations.knowledge_access.secure_article_file"', hooks)
        self.assertNotIn("protect_article_file", hooks)

    def test_suspended_partner_membership_denies_ticket_access(self):
        ticket_access = (ROOT / "hrdesk_helpdesk_customizations" / "ticket_access.py").read_text(
            encoding="utf-8"
        )
        membership = (ROOT / "hrdesk_helpdesk_customizations" / "hr_desk_helpdesk_customizations" / "doctype" / "hrd_partner_membership" / "hrd_partner_membership.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('return "1 = 0"', ticket_access)
        self.assertIn("Deactivate partner membership instead of deleting", membership)


if __name__ == "__main__":
    unittest.main()
