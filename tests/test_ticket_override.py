import importlib
import sys
import types
import unittest


class TicketOverrideTest(unittest.TestCase):
    def setUp(self):
        self.module_names = (
            "frappe",
            "helpdesk",
            "helpdesk.helpdesk",
            "helpdesk.helpdesk.doctype",
            "helpdesk.helpdesk.doctype.hd_ticket",
            "helpdesk.helpdesk.doctype.hd_ticket.api",
            "hrdesk_helpdesk_customizations.feature_flags",
            "hrdesk_helpdesk_customizations.overrides.ticket",
        )
        self.original_modules = {
            name: sys.modules.get(name) for name in self.module_names
        }
        self.calls = []
        self.enabled = False
        self.agent = False

        frappe = types.ModuleType("frappe")
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.whitelist = lambda **kwargs: lambda function: function

        def throw(message, exception):
            raise exception(message)

        frappe.throw = throw
        frappe._ = lambda value: value

        helpdesk = types.ModuleType("helpdesk")
        helpdesk.__path__ = []
        helpdesk_app = types.ModuleType("helpdesk.helpdesk")
        helpdesk_app.__path__ = []
        doctype = types.ModuleType("helpdesk.helpdesk.doctype")
        doctype.__path__ = []
        ticket = types.ModuleType("helpdesk.helpdesk.doctype.hd_ticket")
        ticket.__path__ = []
        ticket_api = types.ModuleType("helpdesk.helpdesk.doctype.hd_ticket.api")

        def upstream_new(doc, attachments):
            self.calls.append((doc, attachments))
            return {"name": "HD-TICKET-TEST"}

        ticket_api.new = upstream_new

        flags = types.ModuleType(
            "hrdesk_helpdesk_customizations.feature_flags"
        )
        flags.customer_portal_ticketing_enabled = lambda: self.enabled
        flags.has_agent_ticket_access = lambda: self.agent

        sys.modules.update(
            {
                "frappe": frappe,
                "helpdesk": helpdesk,
                "helpdesk.helpdesk": helpdesk_app,
                "helpdesk.helpdesk.doctype": doctype,
                "helpdesk.helpdesk.doctype.hd_ticket": ticket,
                "helpdesk.helpdesk.doctype.hd_ticket.api": ticket_api,
                "hrdesk_helpdesk_customizations.feature_flags": flags,
            }
        )
        sys.modules.pop(
            "hrdesk_helpdesk_customizations.overrides.ticket", None
        )
        self.override = importlib.import_module(
            "hrdesk_helpdesk_customizations.overrides.ticket"
        )
        self.frappe = frappe

    def tearDown(self):
        for name in self.module_names:
            original = self.original_modules[name]
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    def test_customer_creation_is_blocked_when_disabled(self):
        with self.assertRaises(self.frappe.PermissionError):
            self.override.new({"subject": "Blocked"})
        self.assertEqual(self.calls, [])

    def test_agent_creation_uses_upstream_when_disabled(self):
        self.agent = True
        result = self.override.new({"subject": "Allowed"}, [{"name": "file"}])
        self.assertEqual(result["name"], "HD-TICKET-TEST")
        self.assertEqual(len(self.calls), 1)

    def test_customer_creation_uses_upstream_when_reenabled(self):
        self.enabled = True
        result = self.override.new({"subject": "Allowed"})
        self.assertEqual(result["name"], "HD-TICKET-TEST")
        self.assertEqual(len(self.calls), 1)


if __name__ == "__main__":
    unittest.main()
