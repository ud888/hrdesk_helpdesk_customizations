import datetime
import unittest

from hrdesk_helpdesk_customizations.soc_rules import (
    actor_can_transition,
    can_transition,
    normalize_nonnegative,
    subscription_period,
)


class SOCRulesTest(unittest.TestCase):
    def test_expected_review_transitions(self):
        self.assertTrue(can_transition("SOC Requested", "SOC Published"))
        self.assertTrue(can_transition("SOC Published", "SOC Signed"))
        self.assertTrue(can_transition("SOC Signed", "Workspace Creation"))
        self.assertTrue(can_transition("Workspace Creation", "Workspace Created"))

    def test_terminal_statuses_cannot_reopen(self):
        self.assertFalse(can_transition("Workspace Created", "SOC Requested"))
        self.assertFalse(can_transition("Cancelled", "SOC Requested"))

    def test_approved_data_can_return_to_review(self):
        self.assertTrue(can_transition("SOC Published", "SOC Requested"))
        self.assertTrue(can_transition("SOC Signed", "SOC Requested"))

    def test_role_ownership_matches_approved_hierarchy(self):
        self.assertTrue(actor_can_transition("partner", "SOC Published", "SOC Signed"))
        self.assertFalse(actor_can_transition("partner", "SOC Signed", "Workspace Creation"))
        self.assertTrue(actor_can_transition("hds", "SOC Signed", "Workspace Creation"))
        self.assertTrue(actor_can_transition("hds", "Workspace Creation", "Workspace Created"))
        self.assertTrue(actor_can_transition("hdt", "Workspace Creation", "Workspace Created"))
        self.assertFalse(actor_can_transition("hdt", "SOC Signed", "Workspace Creation"))

    def test_subscription_period_is_display_only_date_range(self):
        result = subscription_period(
            datetime.date(2026, 10, 1), datetime.date(2027, 9, 30)
        )
        self.assertEqual(result, "01-10-2026 s.d. 30-09-2027")

    def test_quantities_must_be_nonnegative(self):
        self.assertEqual(normalize_nonnegative("2", "Users"), 2)
        with self.assertRaises(ValueError):
            normalize_nonnegative(-1, "Users")


if __name__ == "__main__":
    unittest.main()

