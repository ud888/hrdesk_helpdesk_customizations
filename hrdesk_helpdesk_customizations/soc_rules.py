from __future__ import annotations

from datetime import date


SOC_STATUSES = (
    "SOC Requested",
    "SOC Published",
    "SOC Signed",
    "Workspace Creation",
    "Workspace Created",
    "Cancelled",
)

SOC_TYPES = ("New Subscription", "Renewal", "Addendum")

STATUS_TRANSITIONS = {
    "SOC Requested": {"SOC Published", "Cancelled"},
    "SOC Published": {"SOC Requested", "SOC Signed", "Cancelled"},
    "SOC Signed": {"SOC Requested", "SOC Published", "Workspace Creation", "Cancelled"},
    "Workspace Creation": {"Workspace Created", "Cancelled"},
    "Workspace Created": set(),
    "Cancelled": set(),
}

HDS_TRANSITIONS = {
    ("SOC Requested", "SOC Published"),
    ("SOC Published", "SOC Requested"),
    ("SOC Signed", "SOC Requested"),
    ("SOC Signed", "SOC Published"),
    ("SOC Signed", "Workspace Creation"),
}

PARTNER_TRANSITIONS = {("SOC Published", "SOC Signed")}
HDT_TRANSITIONS = {("Workspace Creation", "Workspace Created")}


def can_transition(current: str, target: str) -> bool:
    if current == target:
        return True
    return target in STATUS_TRANSITIONS.get(current, set())


def actor_can_transition(actor: str, current: str, target: str) -> bool:
    transition = (current, target)
    if target == "Cancelled":
        return actor == "hds"
    if actor == "hds":
        return transition in HDS_TRANSITIONS or transition in HDT_TRANSITIONS
    if actor == "hdt":
        return transition in HDT_TRANSITIONS
    if actor == "partner":
        return transition in PARTNER_TRANSITIONS
    return False


def subscription_period(start_date: date | None, end_date: date | None) -> str:
    if not start_date or not end_date:
        return ""
    return f"{start_date:%d-%m-%Y} s.d. {end_date:%d-%m-%Y}"


def normalize_nonnegative(value, label: str) -> int:
    number = int(value or 0)
    if number < 0:
        raise ValueError(f"{label} tidak boleh negatif.")
    return number

