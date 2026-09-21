import importlib
import sys
import types
import unittest


class FeatureFlagsTest(unittest.TestCase):
    def setUp(self):
        self.module_names = (
            "frappe",
            "helpdesk",
            "helpdesk.utils",
            "hrdesk_helpdesk_customizations.feature_flags",
        )
        self.original_modules = {
            name: sys.modules.get(name) for name in self.module_names
        }
        self.roles = {}
        self.agent_users = set()

        frappe = types.ModuleType("frappe")
        frappe.conf = {}
        frappe.session = types.SimpleNamespace(user="customer@example.com")
        frappe.get_roles = lambda user: self.roles.get(user, [])

        helpdesk = types.ModuleType("helpdesk")
        helpdesk.__path__ = []
        helpdesk_utils = types.ModuleType("helpdesk.utils")
        helpdesk_utils.is_agent = lambda user=None: user in self.agent_users

        sys.modules.update(
            {
                "frappe": frappe,
                "helpdesk": helpdesk,
                "helpdesk.utils": helpdesk_utils,
            }
        )
        sys.modules.pop("hrdesk_helpdesk_customizations.feature_flags", None)
        self.flags = importlib.import_module(
            "hrdesk_helpdesk_customizations.feature_flags"
        )
        self.frappe = frappe

    def tearDown(self):
        for name in self.module_names:
            original = self.original_modules[name]
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def test_ticketing_defaults_to_disabled(self):
        self.assertFalse(self.flags.customer_portal_ticketing_enabled())

    def test_ticketing_accepts_boolean_and_string_values(self):
        key = self.flags.CUSTOMER_PORTAL_TICKETING_ENABLED
        for value in (True, 1, "true", "YES", "on"):
            with self.subTest(value=value):
                self.frappe.conf[key] = value
                self.assertTrue(self.flags.customer_portal_ticketing_enabled())
        for value in (False, 0, "false", "no", "off"):
            with self.subTest(value=value):
                self.frappe.conf[key] = value
                self.assertFalse(self.flags.customer_portal_ticketing_enabled())

    def test_agent_and_system_manager_keep_desk_access(self):
        self.agent_users.add("agent@example.com")
        self.assertTrue(self.flags.has_agent_ticket_access("agent@example.com"))

        self.roles["manager@example.com"] = ["System Manager"]
        self.assertTrue(self.flags.has_agent_ticket_access("manager@example.com"))
        self.assertFalse(self.flags.is_customer_portal_user("manager@example.com"))

    def test_customer_is_customer_portal_user(self):
        self.roles["customer@example.com"] = ["HD Customer"]
        self.assertTrue(
            self.flags.is_customer_portal_user("customer@example.com")
        )


if __name__ == "__main__":
    unittest.main()
