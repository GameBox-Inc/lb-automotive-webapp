"""
Normalize Twilio E.164 caller IDs vs digits-only CRM / appointment storage.

Twilio sends From like +1XXXXXXXXXX; customers.phone and many legacy rows use 10-digit
national numbers. Matching must compare digit-stripped forms (10 vs 11 with country code).
"""
from __future__ import annotations

import re
from typing import List

_NON_DIGITS = re.compile(r"\D+")


def phone_digit_variants(phone: str | None) -> List[str]:
    """
    Distinct digit-only strings for SQL IN (...) matching on regexp_replace(phone, ...).

    Covers US/CA-style numbers where storage may be 10 digits or 11 with leading 1.
    """
    d = _NON_DIGITS.sub("", phone or "")
    if not d:
        return []
    variants = {d}
    if len(d) == 11 and d.startswith("1"):
        variants.add(d[1:])
    elif len(d) == 10:
        variants.add("1" + d)
    return list(variants)


def normalize_phone_for_storage(phone: str | None) -> str:
    """
    Prefer 10-digit national storage when Twilio sends +1XXXXXXXXXX so IVR bookings
    align with customers created via the dashboard (digits-only, often 10 digits).
    """
    d = _NON_DIGITS.sub("", phone or "")
    if not d:
        return (phone or "").strip()
    if len(d) == 11 and d.startswith("1"):
        return d[1:]
    return d
