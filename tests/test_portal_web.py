import importlib
import sys
import types
import unittest


class RequestRedirect(Exception):
    code = 308

    def __init__(self, new_url):
        super().__init__(new_url)
        self.new_url = new_url


class PartnerDomainRedirectTest(unittest.TestCase):
    def setUp(self):
        self.module_names = (
            "frappe",
            "werkzeug",
            "werkzeug.routing",
            "hrdesk_helpdesk_customizations.portal_constants",
            "hrdesk_helpdesk_customizations.portal_web",
        )
        self.original_modules = {
            name: sys.modules.get(name) for name in self.module_names
        }

        frappe = types.ModuleType("frappe")
        frappe.local = types.SimpleNamespace(request=None)

        werkzeug = types.ModuleType("werkzeug")
        routing = types.ModuleType("werkzeug.routing")
        routing.RequestRedirect = RequestRedirect
        werkzeug.routing = routing

        constants = types.ModuleType(
            "hrdesk_helpdesk_customizations.portal_constants"
        )
        constants.PARTNER_DOMAIN = "partner.hrdesk.id"

        sys.modules.update(
            {
                "frappe": frappe,
                "werkzeug": werkzeug,
                "werkzeug.routing": routing,
                "hrdesk_helpdesk_customizations.portal_constants": constants,
            }
        )
        sys.modules.pop("hrdesk_helpdesk_customizations.portal_web", None)
        self.portal_web = importlib.import_module(
            "hrdesk_helpdesk_customizations.portal_web"
        )
        self.frappe = frappe

    def tearDown(self):
        for name in self.module_names:
            original = self.original_modules[name]
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original

    @staticmethod
    def request(host, path="/", method="GET"):
        return types.SimpleNamespace(host=host, path=path, method=method)

    def test_partner_root_raises_valid_temporary_http_redirect(self):
        self.frappe.local.request = self.request("partner.hrdesk.id")

        with self.assertRaises(RequestRedirect) as raised:
            self.portal_web.before_request()

        self.assertEqual(raised.exception.new_url, "/partners")
        self.assertEqual(raised.exception.code, 302)

    def test_support_root_is_unchanged(self):
        self.frappe.local.request = self.request("support.hrdesk.id")
        self.portal_web.before_request()

    def test_partner_portal_path_is_unchanged(self):
        self.frappe.local.request = self.request(
            "partner.hrdesk.id", path="/partners"
        )
        self.portal_web.before_request()

    def test_non_read_request_is_unchanged(self):
        self.frappe.local.request = self.request(
            "partner.hrdesk.id", method="POST"
        )
        self.portal_web.before_request()


if __name__ == "__main__":
    unittest.main()
