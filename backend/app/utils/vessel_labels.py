from __future__ import annotations

_FLAG_NAMES = {
    "AG": "Antigua and Barbuda",
    "BH": "Bahrain",
    "BS": "Bahamas",
    "BZ": "Belize",
    "CN": "China",
    "CY": "Cyprus",
    "DE": "Germany",
    "DK": "Denmark",
    "ER": "Eritrea",
    "FR": "France",
    "GA": "Gabon",
    "GB": "United Kingdom",
    "GQ": "Equatorial Guinea",
    "GR": "Greece",
    "HK": "Hong Kong",
    "ID": "Indonesia",
    "IN": "India",
    "IR": "Iran",
    "JP": "Japan",
    "KH": "Cambodia",
    "KM": "Comoros",
    "KY": "Cayman Islands",
    "LR": "Liberia",
    "MD": "Moldova",
    "MH": "Marshall Islands",
    "MT": "Malta",
    "MY": "Malaysia",
    "NL": "Netherlands",
    "NO": "Norway",
    "NR": "Nauru",
    "PA": "Panama",
    "PH": "Philippines",
    "PW": "Palau",
    "RU": "Russia",
    "SE": "Sweden",
    "SG": "Singapore",
    "SL": "Sierra Leone",
    "ST": "Sao Tome and Principe",
    "TZ": "Tanzania",
    "TV": "Tuvalu",
    "VN": "Vietnam",
}

_VESSEL_TYPE_LABELS = {
    "BC": "Bulk Carrier",
    "CS": "Container Ship",
    "GC": "General Cargo Ship",
    "GT": "Gas Tanker",
    "TA": "Oil Tanker",
    "TC": "Chemical Tanker",
    "container": "Container Ship",
    "container ship": "Container Ship",
    "bulk": "Bulk Carrier",
    "bulk carrier": "Bulk Carrier",
    "general cargo": "General Cargo Ship",
    "tanker": "Tanker",
}


def normalize_flag_code(flag: str | None) -> str | None:
    if not flag:
        return None
    code = flag.strip().upper()
    return code or None


def flag_emoji(flag: str | None) -> str | None:
    code = normalize_flag_code(flag)
    if not code or len(code) != 2 or not code.isalpha():
        return None
    return "".join(chr(0x1F1E6 + ord(char) - ord("A")) for char in code)


def flag_name(flag: str | None) -> str | None:
    code = normalize_flag_code(flag)
    if not code:
        return None
    return _FLAG_NAMES.get(code, code)


def vessel_type_label(vessel_type: str | None) -> str | None:
    if not vessel_type:
        return None
    raw = vessel_type.strip()
    if not raw:
        return None
    return _VESSEL_TYPE_LABELS.get(raw.upper()) or _VESSEL_TYPE_LABELS.get(raw.lower()) or raw


def display_vessel_name(name: str, flag: str | None) -> str:
    emoji = flag_emoji(flag)
    clean_name = name.strip() or "Unknown"
    return f"{emoji} {clean_name}" if emoji else clean_name
