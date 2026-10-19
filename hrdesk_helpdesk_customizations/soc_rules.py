from __future__ import annotations

from datetime import date


SOC_STATUSES = (
    "Draft",
    "Submitted",
    "Under Review",
    "Revision Requested",
    "Approved",
    "PDF Sent",
    "Completed",
    "Cancelled",
)

SOC_TYPES = ("New Subscription", "Renewal", "Addendum")

STATUS_TRANSITIONS = {
    "Draft": {"Submitted", "Cancelled"},
    "Submitted": {"Under Review", "Cancelled"},
    "Under Review": {"Revision Requested", "Approved", "Cancelled"},
    "Revision Requested": {"Under Review", "Cancelled"},
    "Approved": {"Under Review", "PDF Sent", "Cancelled"},
    "PDF Sent": {"Under Review", "Completed"},
    "Completed": set(),
    "Cancelled": set(),
}


def can_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in STATUS_TRANSITIONS.get(current, set())


def subscription_period(start_date: date | None, end_date: date | None) -> str:
    if not start_date or not end_date:
        return ""
    return f"{start_date:%d-%m-%Y} s.d. {end_date:%d-%m-%Y}"


def normalize_nonnegative(value, label: str) -> int:
    number = int(value or 0)
    if number < 0:
        raise ValueError(f"{label} tidak boleh negatif.")
    return number

