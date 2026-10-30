"""Awaab's Law scope and deadlines, computed in code.

Source: Awaab's Law: guidance for social landlords - timeframes for repairs in
the social rented sector (MHCLG, updated 27 October 2025), implementing the
Hazards in Social Housing (Prescribed Requirements) (England) Regulations 2025.
"""
from datetime import date, datetime, timedelta

import httpx

GUIDANCE_URL = ("https://www.gov.uk/government/publications/awaabs-law-guidance-for-social-landlords/"
                "awaabs-law-guidance-for-social-landlords-timeframes-for-repairs-in-the-social-rented-sector")
IN_FORCE = date(2025, 10, 27)

# Used only if the gov.uk feed is unreachable.
FALLBACK_HOLIDAYS = {"2025-12-25", "2025-12-26", "2026-01-01", "2026-04-03", "2026-04-06", "2026-05-04",
                     "2026-05-25", "2026-08-31", "2026-12-25", "2026-12-28", "2027-01-01"}


def _load_holidays() -> set[str]:
    try:
        events = httpx.get("https://www.gov.uk/bank-holidays.json", timeout=10).json()["england-and-wales"]["events"]
        return {e["date"] for e in events}
    except Exception:
        return FALLBACK_HOLIDAYS


HOLIDAYS = _load_holidays()


def is_working_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in HOLIDAYS


def add_working_days(start: date, n: int) -> date:
    """Day zero is `start`; day one is the next working day."""
    d = start
    while n > 0:
        d += timedelta(days=1)
        if is_working_day(d):
            n -= 1
    return d


def working_days_between(a: date, b: date) -> int:
    """Working days after `a` up to and including `b` (negative if b < a)."""
    if b < a:
        return -working_days_between(b, a)
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if is_working_day(d):
            n += 1
    return n


def scope(landlord_type: str, tenure: str) -> dict:
    """Does Awaab's Law cover this home? Returns the route to use either way."""
    lt, tn = (landlord_type or "").lower(), (tenure or "").lower()
    if tn in {"owner", "leaseholder", "shared_ownership", "licence"}:
        return {"covered": False, "route": "not_covered",
                "why": "Awaab's Law covers social housing let under a tenancy. Owner-occupiers, long leaseholders, "
                       "shared owners and licensees are not covered."}
    if lt in {"council", "housing_association"}:
        return {"covered": True, "route": "awaabs_law",
                "why": "Your landlord is a social landlord in England, so since 27 October 2025 it must meet "
                       "Awaab's Law deadlines for damp and mould that presents a significant risk of harm."}
    if lt == "private":
        return {"covered": False, "route": "private",
                "why": "Awaab's Law currently applies to social housing. Private renters can ask the council's "
                       "environmental health team to inspect under the Housing Health and Safety Rating System."}
    return {"covered": None, "route": "unknown",
            "why": "We couldn't tell who your landlord is. If it's the council or a housing association, "
                   "Awaab's Law applies."}


def deadlines(reported: date, classification: str, investigated: date | None, today: date) -> list[dict]:
    """The landlord's legal deadlines, each with a status relative to today."""
    if classification == "emergency":
        due = reported + timedelta(days=1)
        return [_item("Investigate and make safe", "within 24 hours of being told", due, None, today)]

    inv_due = add_working_days(reported, 10)
    items = [_item("Investigate", "within 10 working days of being told", inv_due, investigated, today)]
    base = investigated or inv_due
    basis = "after the investigation" if investigated else "after the investigation deadline (latest)"
    items.append(_item("Send you a written summary", f"within 3 working days {basis}",
                       add_working_days(base, 3), None, today))
    items.append(_item("Make it safe", f"within 5 working days {basis}",
                       add_working_days(base, 5), None, today))
    items.append(_item("Start longer-term repairs", "as soon as reasonably practicable, within 12 weeks",
                       base + timedelta(weeks=12), None, today))
    return items


def _item(label, rule, due: date, done: date | None, today: date) -> dict:
    if done:
        status = "met" if done <= due else "late"
    elif today > due:
        status = "overdue"
    else:
        status = "pending"
    return {"label": label, "rule": rule, "due": due.isoformat(), "status": status,
            "days_overdue": working_days_between(due, today) if status == "overdue" else 0}


def parse_date(s) -> date | None:
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
