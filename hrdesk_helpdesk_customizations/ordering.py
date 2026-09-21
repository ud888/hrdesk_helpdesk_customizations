from collections.abc import Iterable, Mapping
from typing import Any

CATEGORY_ORDER = (
    "Panduan Tampilan",
    "Karyawan",
    "Kehadiran",
    "Cuti & Lembur",
    "Klaim & Loan",
    "Payroll",
    "Panel Admin",
)

_CATEGORY_RANK = {name: index for index, name in enumerate(CATEGORY_ORDER)}
_UNLISTED_RANK = len(CATEGORY_ORDER)


def sort_categories(
    categories: Iterable[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Return categories in the approved portal order.

    Python's stable sort preserves the upstream relative order for any category
    that is not explicitly listed.
    """
    return sorted(
        categories,
        key=lambda category: _CATEGORY_RANK.get(
            str(category.get("category_name", "")), _UNLISTED_RANK
        ),
    )

