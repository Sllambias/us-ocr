import re
from typing import Optional

ALL_FIELDS = ["lengths", "acquisition_protocol", "frequency", "gain", "zoom", "depth"]


def parse_float(value: str) -> Optional[float]:
    """float(value), or None if OCR garbled it (e.g. '1.2.3')."""
    try:
        return float(value)
    except ValueError:
        return None


def extract_d_mm_values(text: str) -> list:
    """Caliper lengths ('CervixL= 32.1 mm', 'CervixL 3.2 cm') as floats in millimetres."""
    values = []
    for value, unit in re.findall(r"CervixL\.?=?\s*([\d.]+)\s*(mm|cm)", text):
        number = parse_float(value)
        if number is None:
            continue
        values.append(number * 10 if unit == "cm" else number)
    return values


def extract_frequency(text: str) -> Optional[str]:
    """Probe frequency setting: 'HI H PI' or 'Augment'."""
    # docTR often merges or splits these words and reads stray 'I's,
    # e.g. 'HIHPI', 'HI HPI', 'HIH PI', 'HI HI PI'
    if re.search(r"HI[\sI]*H[\sI]*PI", text):
        return "HI H PI"
    if re.search(r"Augment", text, re.IGNORECASE):
        return "Augment"
    return None


def extract_sector_width_and_zoom(text: str) -> tuple:
    """Sector width and zoom from '<width>°/<zoom>', or (None, None)."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*°\s*/\s*(\d+(?:\.\d+)?)", text)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def extract_acquisition_protocol(text: str) -> Optional[str]:
    """Cervix acquisition protocol label ('Cervix', 'Cervix dybde 1-3'). Study-specific."""
    match = re.search(r"Cervix dybde [123]|Cervix", text)
    return match.group(0) if match else None


def extract_depth(text: str) -> Optional[float]:
    """Image depth in cm."""
    match = re.search(r"([\d.]+)\s*cm", text)
    return parse_float(match.group(1)) if match else None


def extract_gain(text: str) -> Optional[float]:
    """Gain: the number following 'Gn'."""
    match = re.search(r"Gn\s*(-?)\s*([\d.]+)", text)
    if not match:
        return None
    sign, value = match.groups()
    return parse_float(sign + value)


def parse_text(text: str, fields: dict) -> dict:
    """Run the enabled extractors on one image's OCR text."""
    sector_width, zoom = extract_sector_width_and_zoom(text)
    row = {"sector_width": sector_width}
    if fields.get("lengths"):
        lengths = extract_d_mm_values(text)
        row["lengths_mm"] = ";".join(str(v) for v in lengths)
        row["CL_sum"] = float(sum(lengths))
        row["CL_max"] = max(lengths) if lengths else 0.0
    if fields.get("acquisition_protocol"):
        row["protocol"] = extract_acquisition_protocol(text)
    if fields.get("frequency"):
        row["frequency"] = extract_frequency(text)
    if fields.get("gain"):
        row["gain"] = extract_gain(text)
    if fields.get("zoom"):
        row["zoom"] = zoom
    if fields.get("depth"):
        row["depth"] = extract_depth(text)
    return row
