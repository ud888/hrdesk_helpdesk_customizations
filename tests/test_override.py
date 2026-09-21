import importlib
import sys
import types
import unittest


class KnowledgeBaseOverrideTest(unittest.TestCase):
    def setUp(self):
        self.original_modules = {
            name: sys.modules.get(name)
            for name in ("frappe", "helpdesk", "helpdesk.api", "helpdesk.api.knowledge_base")
        }

        frappe = types.ModuleType("frappe")

        def whitelist(*, allow_guest=False):
            self.assertTrue(allow_guest)
            return lambda function: function

        frappe.whitelist = whitelist

        helpdesk = types.ModuleType("helpdesk")
        helpdesk.__path__ = []
        helpdesk_api = types.ModuleType("helpdesk.api")
        helpdesk_api.__path__ = []
        knowledge_base = types.ModuleType("helpdesk.api.knowledge_base")
        knowledge_base.get_categories = lambda: [
            {"category_name": "Payroll"},
            {"category_name": "Panduan Tampilan"},
            {"category_name": "Karyawan"},
        ]

        sys.modules.update(
            {
                "frappe": frappe,
                "helpdesk": helpdesk,
                "helpdesk.api": helpdesk_api,
                "helpdesk.api.knowledge_base": knowledge_base,
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
