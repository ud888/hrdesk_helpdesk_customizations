import importlib
import sys
import types
import unittest


class Headers(dict):
    def add(self, key, value):
        self[key] = f"{self[key]}, {value}" if key in self else value


class Response:
    def __init__(self, body="<html><body><div id='app'></div></body></html>"):
        self.status_code = 200
        self.headers = Headers()
        self.content_type = "text/html; charset=utf-8"
        self.is_streamed = False
        self.body = body

    def get_data(self, as_text=False):
        if as_text:
            return self.body.decode() if isinstance(self.body, bytes) else self.body
        return self.body.encode() if isinstance(self.body, str) else self.body

    def set_data(self, body):
        self.body = body


class CustomerPortalHookTest(unittest.TestCase):
    def setUp(self):
        self.module_names = (
            "frappe",
            "hrdesk_helpdesk_customizations.feature_flags",
            "hrdesk_helpdesk_customizations.customer_portal",
        )
        self.original_modules = {
            name: sys.modules.get(name) for name in self.module_names
        }

        frappe = types.ModuleType("frappe")
        frappe._ = lambda value: value
        frappe.PermissionError = type("PermissionError", (Exception,), {})
        frappe.session = types.SimpleNamespace(user="customer@example.com")
        frappe.get_roles = lambda user: ["HD Customer"]

        def throw(message, exception):
            raise exception(message)

        frappe.throw = throw

        flags = types.ModuleType(
            "hrdesk_helpdesk_customizations.feature_flags"
        )
        flags.customer_portal_ticketing_enabled = lambda: False
        flags.has_agent_ticket_access = lambda user=None: False
        flags.is_customer_portal_user = lambda user=None: True

        sys.modules.update(
            {
                "frappe": frappe,
                "hrdesk_helpdesk_customizations.feature_flags": flags,
            }
        )
        sys.modules.pop("hrdesk_helpdesk_customizations.customer_portal", None)
        self.portal = importlib.import_module(
            "hrdesk_helpdesk_customizations.customer_portal"
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
    def request(path, method="GET"):
        return types.SimpleNamespace(path=path, method=method)

    def test_customer_root_redirects_to_knowledge_base(self):
        response = Response()
        self.portal.after_request(response, self.request("/helpdesk"))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/helpdesk/kb-public")

    def test_customer_ticket_routes_redirect_to_knowledge_base(self):
        for path in (
            "/helpdesk/my-tickets",
            "/helpdesk/my-tickets/new",
            "/helpdesk/my-tickets/123",
        ):
            with self.subTest(path=path):
                response = Response()
                self.portal.after_request(response, self.request(path))
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.headers["Location"], "/helpdesk/kb-public"
                )

    def test_knowledge_base_gets_ui_guard_script(self):
        response = Response()
        self.portal.after_request(response, self.request("/helpdesk/kb-public"))
        body = response.get_data(as_text=True)
        self.assertIn("customer_portal_kb_only.js", body)
        self.assertIn("data-ticketing-enabled=\"false\"", body)

    def test_agent_page_is_unchanged(self):
        self.portal.is_customer_portal_user = lambda: False
        response = Response()
        self.portal.after_request(response, self.request("/helpdesk/tickets"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("customer_portal_kb_only.js", response.body)

    def test_customer_insert_is_blocked(self):
        with self.assertRaises(self.frappe.PermissionError):
            self.portal.guard_customer_ticket_insert(object())

    def test_agent_insert_is_allowed(self):
        self.portal.has_agent_ticket_access = lambda: True
        self.portal.guard_customer_ticket_insert(object())

    def test_reenabled_ticketing_removes_all_guards(self):
        self.portal.customer_portal_ticketing_enabled = lambda: True
        response = Response()
        self.portal.after_request(response, self.request("/helpdesk/my-tickets"))
        self.assertEqual(response.status_code, 200)
        self.portal.guard_customer_ticket_insert(object())


if __name__ == "__main__":
    unittest.main()
