from __future__ import annotations


def luhn_valid(imo: int | str) -> bool:
    """Return True if the 7-digit IMO number passes the Luhn check digit."""
    s = str(imo).strip()
    if not s.isdigit() or len(s) != 7:
        return False
    total = sum(int(d) * (7 - i) for i, d in enumerate(s[:6]))
    return total % 10 == int(s[6])
