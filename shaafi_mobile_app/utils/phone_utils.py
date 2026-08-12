# apps/shaafi_mobile_app/shaafi_mobile_app/utils/phone_utils.py

import re


def normalize_somali_mobile(raw):
    """
    Canonical local Somali mobile: 9 digits, e.g. 613656021.

    Strips spaces/+/- , country code 252, and a single leading 0.
    Returns None if empty or not a plausible local mobile after cleaning.
    """
    if raw is None:
        return None

    digits = re.sub(r"\D", "", str(raw).strip())
    if not digits:
        return None

    if digits.startswith("252"):
        digits = digits[3:]

    if digits.startswith("0"):
        digits = digits[1:]

    # Somali mobiles are typically 9 digits starting with 6
    if len(digits) != 9 or not digits.startswith("6"):
        return None

    return digits


def mobile_variants(raw):
    """
    Common stored formats for the same Somali number (for DB IN filters).
    Accepts already-canonical or dirty input; returns deduped non-empty strings.
    """
    canonical = normalize_somali_mobile(raw)
    if not canonical:
        return []

    variants = [
        canonical,  # 613656021
        f"0{canonical}",  # 0613656021
        f"252{canonical}",  # 252613656021
        f"2520{canonical}",  # 2520613656021
        f"+252{canonical}",  # +252613656021
        f"+2520{canonical}",  # +2520613656021
    ]

    # Preserve order, drop duplicates
    seen = set()
    result = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result
