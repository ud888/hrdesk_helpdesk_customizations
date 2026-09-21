import unittest

from hrdesk_helpdesk_customizations.ordering import CATEGORY_ORDER, sort_categories


class SortCategoriesTest(unittest.TestCase):
    def test_orders_approved_categories(self):
        source = [
            {"category_name": "Payroll", "article_count": 12},
            {"category_name": "Karyawan", "article_count": 20},
            {"category_name": "Panel Admin", "article_count": 5},
            {"category_name": "Panduan Tampilan", "article_count": 2},
            {"category_name": "Klaim & Loan", "article_count": 8},
            {"category_name": "Cuti & Lembur", "article_count": 4},
            {"category_name": "Kehadiran", "article_count": 10},
        ]

        result = sort_categories(source)

        self.assertEqual(
            [category["category_name"] for category in result],
            list(CATEGORY_ORDER),
        )

    def test_preserves_unlisted_categories_after_approved_categories(self):
        source = [
            {"category_name": "Future B"},
            {"category_name": "Payroll"},
            {"category_name": "Future A"},
            {"category_name": "Karyawan"},
        ]

        result = sort_categories(source)

        self.assertEqual(
            [category["category_name"] for category in result],
            ["Karyawan", "Payroll", "Future B", "Future A"],
        )

    def test_does_not_mutate_input(self):
        source = [
            {"category_name": "Payroll"},
            {"category_name": "Karyawan"},
        ]

        sort_categories(source)

        self.assertEqual(
            [category["category_name"] for category in source],
            ["Payroll", "Karyawan"],
        )


if __name__ == "__main__":
    unittest.main()
