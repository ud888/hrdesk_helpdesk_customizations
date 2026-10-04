import importlib
import sys
import types
import unittest


class KnowledgeBaseOverrideTest(unittest.TestCase):
    def setUp(self):
        self.original_modules = {
            name: sys.modules.get(name)
            for name in (
                "frappe",
                "frappe.utils",
                "hrdesk_helpdesk_customizations.knowledge_access",
                "hrdesk_helpdesk_customizations.partner_access",
            )
        }

        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value

        class Row(dict):
            __getattr__ = dict.__getitem__

        frappe.get_all = lambda *args, **kwargs: [
            Row(name="payroll", category_name="Payroll", modified=""),
            Row(name="appearance", category_name="Panduan Tampilan", modified=""),
            Row(name="employee", category_name="Karyawan", modified=""),
        ]
        frappe.db = types.SimpleNamespace(count=lambda *args, **kwargs: 1)

        def whitelist(*, allow_guest=False):
            self.assertTrue(allow_guest)
            return lambda function: function

        frappe.whitelist = whitelist

        frappe_utils = types.ModuleType("frappe.utils")
        frappe_utils.get_user_info_for_avatar = lambda user: {"name": user}
        frappe_utils.strip_html_tags = lambda value: value
        knowledge_access = types.ModuleType(
            "hrdesk_helpdesk_customizations.knowledge_access"
        )
        knowledge_access.require_category = lambda category: None
        partner_access = types.ModuleType(
            "hrdesk_helpdesk_customizations.partner_access"
        )
        partner_access.allowed_audiences = lambda user=None: {"Public"}
        partner_access.can_read_article = lambda article, user=None: True

        sys.modules.update(
            {
                "frappe": frappe,
                "frappe.utils": frappe_utils,
                "hrdesk_helpdesk_customizations.knowledge_access": knowledge_access,
                "hrdesk_helpdesk_customizations.partner_access": partner_access,
            }
        )
        sys.modules.pop(
            "hrdesk_helpdesk_customizations.overrides.knowledge_base", None
        )

    def tearDown(self):
        sys.modules.pop(
            "hrdesk_helpdesk_customizations.overrides.knowledge_base", None
        )
        for name, module in self.original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_override_preserves_upstream_data_and_applies_order(self):
        override = importlib.import_module(
            "hrdesk_helpdesk_customizations.overrides.knowledge_base"
        )

        result = override.get_categories()

        self.assertEqual(
            [category["category_name"] for category in result],
            ["Panduan Tampilan", "Karyawan", "Payroll"],
        )


if __name__ == "__main__":
    unittest.main()
