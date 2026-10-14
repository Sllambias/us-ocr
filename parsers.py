import re
from typing import Optional

ALL_FIELDS = ["lengths", "acquisition_protocol", "frequency", "gain", "zoom", "depth"]


def extract_d_mm_values(text: str) -> list:
    """Caliper lengths ('D= 32.1 mm', 'L 3.2 cm') as floats in millimetres."""
    pattern = r"[DL]\.?=?\s*([\d.]+)\s*(mm|cm)"
    values = []
    for value, unit in re.findall(pattern, text):
        try:
            number = float(value)
        except ValueError:
            continue
        values.append(number * 10 if unit == "cm" else number)
    return values


def extract_frequency(text: str) -> Optional[str]:
    """Probe frequency setting: 'Har-High/Mid/Low', then 'Resol'/'Penetration', then 'Freq <n> MHz'."""
    patterns = [
        r"Har-?\s*(High|Mid|Low)",
        r"(Resol|Penetration)",
        r"(Frq|Freq|Frequency)\s*([\d.]+\s*MHz?)?",
    ]
    for pattern in patterns:
        results = re.findall(pattern, text, re.IGNORECASE)
        if results:
            first = results[0]
            return first if isinstance(first, str) else " ".join(first).strip()
    return None


def extract_acquisition_protocol(text: str) -> Optional[str]:
    """Cervix acquisition protocol label ('Cervix', 'Cervix dybde 1-3'). Study-specific."""
    match = re.search(r"Cervix dybde [123]|Cervix", text)
    return match.group(0) if match else None


def extract_depth(text: str) -> Optional[float]:
    """Image depth in cm."""
    match = re.search(r"\s*([\d.]+)\s*(cm)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def extract_zoom(text: str) -> Optional[float]:
    """Zoom level: a decimal number adjacent to a 'Hz' or 'cm' token."""
    segments = []
    for seg in text.split("/"):
        segments.extend(seg.split(" "))
    segments = [s.strip() for s in segments if s.strip()]

    def has_unit(s):
        return "Hz" in s or "cm" in s

    for i in range(1, len(segments) - 1):
        prev_seg, curr_seg, next_seg = segments[i - 1], segments[i], segments[i + 1]
        if has_unit(curr_seg) or not (has_unit(prev_seg) or has_unit(next_seg)):
            continue
        match = re.search(r"^[^a-zA-Z0-9]*(\d+\.\d+)[^a-zA-Z0-9]*$", curr_seg)
        if match:
            return float(match.group(1))
    return None


def extract_gain(text: str) -> Optional[float]:
    """Gain: the number following 'Gn'."""
    results = re.findall(r"Gn\s*(-?)\s*([\d.]+)", text)
    if not results:
        return None
    sign, value = results[0]
    try:
        return float(f"{sign}{value}")
    except ValueError:
        return None


def parse_text(text: str, fields: dict) -> dict:
    """Run the enabled extractors on one image's OCR text."""
    row = {}
    if fields.get("lengths"):
        lengths = extract_d_mm_values(text)
        row["lengths_mm"] = ";".join(str(v) for v in lengths)
        row["CL_sum"] = float(sum(lengths))
        row["CL_max"] = float(max(lengths)) if lengths else 0.0
    if fields.get("acquisition_protocol"):
        row["protocol"] = extract_acquisition_protocol(text)
    if fields.get("frequency"):
        row["frequency"] = extract_frequency(text)
    if fields.get("gain"):
        row["gain"] = extract_gain(text)
    if fields.get("zoom"):
        row["zoom"] = extract_zoom(text)
    if fields.get("depth"):
        row["depth"] = extract_depth(text)
    return row
