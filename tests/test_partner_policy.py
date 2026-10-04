import types
import unittest

from hrdesk_helpdesk_customizations.portal_policy import (
    can_access_soc,
    ticket_scope_sql,
)


class PartnerPolicyTest(unittest.TestCase):
    def test_member_sees_only_own_soc_request(self):
        membership = types.SimpleNamespace(
            user="member@example.invalid",
            partner="PARTNER-A",
            request_manager=0,
            l1_support_access=0,
        )
        sql = ticket_scope_sql(
            membership.user, membership, lambda value: f"'{value}'"
        )
        self.assertIn("custom_partner_submitted_by = 'member@example.invalid'", sql)
        self.assertNotIn("custom_partner_organization = 'PARTNER-A'", sql)

    def test_request_manager_scope_is_partner_bound(self):
        membership = types.SimpleNamespace(
            user="manager@example.invalid",
            partner="PARTNER-A",
            request_manager=1,
            l1_support_access=0,
        )
        sql = ticket_scope_sql(
            membership.user, membership, lambda value: f"'{value}'"
        )
        self.assertIn("custom_partner_organization = 'PARTNER-A'", sql)

    def test_l1_scope_requires_responsible_partner_mapping(self):
        membership = types.SimpleNamespace(
            user="agent@example.invalid",
            partner="PARTNER-A",
            request_manager=0,
            l1_support_access=1,
        )
        sql = ticket_scope_sql(
            membership.user, membership, lambda value: f"'{value}'"
        )
        self.assertIn("customer.custom_hrdesk_responsible_partner = 'PARTNER-A'", sql)

    def test_soc_access_never_crosses_partner(self):
        membership = types.SimpleNamespace(
            user="manager@example.invalid",
            partner="PARTNER-A",
            request_manager=1,
        )
        other = types.SimpleNamespace(
            custom_partner_organization="PARTNER-B",
            custom_partner_submitted_by="other@example.invalid",
        )
        self.assertFalse(can_access_soc(other, membership))


if __name__ == "__main__":
    unittest.main()

