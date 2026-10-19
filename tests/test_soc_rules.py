import datetime
import unittest

from hrdesk_helpdesk_customizations.soc_rules import (
    can_transition,
    normalize_nonnegative,
    subscription_period,
)


class SOCRulesTest(unittest.TestCase):
    def test_expected_review_transitions(self):
        self.assertTrue(can_transition("Submitted", "Under Review"))
        self.assertTrue(can_transition("Under Review", "Revision Requested"))
        self.assertTrue(can_transition("Revision Requested", "Under Review"))
        self.assertTrue(can_transition("Under Review", "Approved"))
        self.assertTrue(can_transition("Approved", "PDF Sent"))
        self.assertTrue(can_transition("PDF Sent", "Completed"))

    def test_terminal_statuses_cannot_reopen(self):
        self.assertFalse(can_transition("Completed", "Under Review"))
        self.assertFalse(can_transition("Cancelled", "Submitted"))

    def test_approved_data_can_return_to_review(self):
        self.assertTrue(can_transition("Approved", "Under Review"))
        self.assertTrue(can_transition("PDF Sent", "Under Review"))

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

