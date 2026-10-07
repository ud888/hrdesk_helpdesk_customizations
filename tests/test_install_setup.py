import importlib
import sys
import types
import unittest


class InstallSetupTest(unittest.TestCase):
    def setUp(self):
        self.original_modules = {
            name: sys.modules.get(name)
            for name in (
                "frappe",
                "frappe.custom",
                "frappe.custom.doctype",
                "frappe.custom.doctype.custom_field",
                "frappe.custom.doctype.custom_field.custom_field",
                "frappe.permissions",
                "hrdesk_helpdesk_customizations.feature_flags",
            )
        }

        self.created = []
        frappe = types.ModuleType("frappe")
        frappe.db = types.SimpleNamespace(exists=lambda *args, **kwargs: False)

        class Document:
            def __init__(document, values):
                document.values = values

            def insert(document, *, ignore_permissions=False):
                self.assertTrue(ignore_permissions)
                self.created.append(document.values)

        frappe.get_doc = lambda values: Document(values)

        custom = types.ModuleType("frappe.custom")
        doctype = types.ModuleType("frappe.custom.doctype")
        custom_field = types.ModuleType("frappe.custom.doctype.custom_field")
        custom_field_module = types.ModuleType(
            "frappe.custom.doctype.custom_field.custom_field"
        )
        custom_field_module.create_custom_fields = lambda *args, **kwargs: None
        permissions = types.ModuleType("frappe.permissions")
        permissions.add_permission = lambda *args, **kwargs: None
        permissions.update_permission_property = lambda *args, **kwargs: None
        feature_flags = types.ModuleType(
            "hrdesk_helpdesk_customizations.feature_flags"
        )
        feature_flags.portal_team_restrictions_enabled = lambda: False

        sys.modules.update(
            {
                "frappe": frappe,
                "frappe.custom": custom,
                "frappe.custom.doctype": doctype,
                "frappe.custom.doctype.custom_field": custom_field,
                "frappe.custom.doctype.custom_field.custom_field": custom_field_module,
                "frappe.permissions": permissions,
                "hrdesk_helpdesk_customizations.feature_flags": feature_flags,
            }
        )
        sys.modules.pop("hrdesk_helpdesk_customizations.setup.install", None)

    def tearDown(self):
        sys.modules.pop("hrdesk_helpdesk_customizations.setup.install", None)
        for name, module in self.original_modules.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module

    def test_bootstrap_teams_include_required_neutral_member(self):
        install = importlib.import_module(
            "hrdesk_helpdesk_customizations.setup.install"
        )

        install._ensure_teams()

        self.assertEqual(len(self.created), 3)
        for team in self.created:
            self.assertEqual(team["doctype"], "HD Team")
            self.assertEqual(team["users"], [{"user": "Administrator"}])


if __name__ == "__main__":
    unittest.main()
