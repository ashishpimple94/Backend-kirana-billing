"""
regex_parser.py
Fast-path Python Regex Parser for Kirana voice orders (<5ms).
Supports single lines, continuous speech streams, unit slashes, and spoken echo words:
- "sakhar 1 kg /kilo 60 rupay maida 1kg/kilo 50 rupay" -> साखर (1kg @ ₹60) + मैदा (1kg @ ₹50)
- "साखर १ किलो साठ रुपये मैदा १ किलो पन्नास रुपये" -> साखर (1kg @ ₹60) + मैदा (1kg @ ₹50)
- "sakhar 1kg 60 rupaye saath rupaye" -> साखर (1kg @ ₹60, echo: saath)
- "Patanjali biscuit box 10/- 710" -> पतंजली बिस्कीट बॉक्स (MRP 10/- @ ₹710)
"""

import re
from typing import List, Dict, Any, Optional

from services.marathi_normalizer import (
    normalize_marathi_transcript,
    canonicalize_marathi_item_name,
    COMPOUND_PRICING_MAP,
    SPOKEN_NUMBER_WORDS,
)

UNIT_MAP = {
    "kg": "kg", "kilo": "kg", "kilogram": "kg", "किलो": "kg", "केजी": "kg",
    "gm": "gm", "g": "gm", "gram": "gm", "ग्रॅम": "gm", "ग्राम": "gm",
    "litre": "litre", "liter": "litre", "l": "litre", "लिटर": "litre", "लीटर": "litre",
    "ml": "ml", "मिली": "ml",
    "packet": "packet", "pkt": "packet", "pack": "packet", "पाकीट": "packet", "पुडा": "packet",
    "box": "box", "खोके": "box", "बॉक्स": "box",
    "piece": "piece", "pc": "piece", "pcs": "piece", "नग": "piece",
    "bottle": "bottle", "बाटली": "bottle",
    "pau": "gm", "pav": "gm", "पाव": "gm",
}


def clean_unit_and_qty(raw_qty: str, raw_unit: str) -> (float, str):
    """Normalize quantity and unit."""
    try:
        qty = float(raw_qty)
    except (ValueError, TypeError):
        qty = 1.0

    unit_key = (raw_unit or "").strip().lower()
    unit = UNIT_MAP.get(unit_key, "piece")

    if unit_key in ("pau", "pav", "पाव"):
        qty = 250.0
        unit = "gm"

    return qty, unit


def clean_item_name(raw_name: str, language: str = "mr-IN", output_lang: Optional[str] = None) -> str:
    """Returns mapped Devanagari or clean capitalized title."""
    clean = raw_name.strip()
    # Strip stray leading or trailing currency tokens, connectors, and numbers
    clean = re.sub(r"^(?:ani|aur|and|va|next|then|rs|rupaye|rupay|rupees|रुपये|\d+|\+|,|-)\s+", "", clean, flags=re.IGNORECASE).strip()
    clean = re.sub(r"\s+(?:rs|rupaye|rupay|rupees|रुपये)$", "", clean, flags=re.IGNORECASE).strip()
    return canonicalize_marathi_item_name(clean, language, output_lang)


def clean_echo_word(raw_echo: Optional[str]) -> Optional[str]:
    """Cleans pronunciation confirmation word."""
    if not raw_echo:
        return None
    cleaned = re.sub(r"(?:\s*(?:rupaye|rupay|rupees|rs|रुपये|रुपया))+$", "", raw_echo, flags=re.IGNORECASE).strip()
    low = cleaned.lower()
    if low in SPOKEN_NUMBER_WORDS or low in COMPOUND_PRICING_MAP or cleaned in SPOKEN_NUMBER_WORDS:
        return cleaned
    return None


def parse_bill_with_regex(transcript: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parses speech lines or continuous stream into structured Kirana items one by one.
    """
    if not transcript or not transcript.strip():
        return []

    options = options or {}
    price_mode = options.get("priceMode", "per_unit")
    language = options.get("language", "mr-IN")
    output_lang = options.get("outputLang", None)

    # 1. Full Marathi & numeral normalization
    normalized = normalize_marathi_transcript(transcript)

    items = []
    matched_ranges = []

    # 2. Extract MRP lines first (e.g. "Patanjali biscuit box 10/- 710")
    mrp_pattern = re.compile(
        r"([a-zA-Z\u0900-\u097F\s-]{2,30}?)\s+(\d+)\s*/-\s*(?:rupaye|rupay|rs|inr|रुपये)?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE
    )
    for m in mrp_pattern.finditer(normalized):
        raw_name = m.group(1).strip()
        mrp_val = float(m.group(2))
        price_val = float(m.group(3))
        if price_val < 15000:
            name = clean_item_name(raw_name, language, output_lang)
            items.append({
                "name": name,
                "quantity": 1.0,
                "unit": "box" if "box" in raw_name.lower() else "piece",
                "price": price_val,
                "amount": price_val,
                "mrp": mrp_val,
                "spoken_pronunciation": None,
            })
            matched_ranges.append((m.start(), m.end()))

    # Mask out MRP matches
    text_remaining = list(normalized)
    for start, end in matched_ranges:
        for idx in range(start, end):
            text_remaining[idx] = " "
    active_text = "".join(text_remaining)

    # 3. Stream-based multi-item matching for continuous speech:
    # Pattern A: [Name] [Qty] [Unit] [Price] [Optional Echo]
    # e.g. "sakhar 1 kg 60 rs", "साखर 1 kg 60 rs मैदा 1 kg 50 rs"
    stream_pattern_a = re.compile(
        r"(?:^|[\n,;+]|\s+)"
        r"([a-zA-Z\u0900-\u097F\s-]{2,30}?)\s+"
        r"(\d+(?:\.\d+)?)\s*"
        r"(kg|kilo|gm|g|gram|litre|liter|l|ml|packet|box|piece|pc|pcs|पाकीट|नग|किलो|ग्रॅम|ग्राम|लिटर|लीटर)(?:\s*/\s*(?:kilo|kg|किलो))?\s+"
        r"(\d+(?:\.\d+)?)\s*"
        r"(?:rupaye|rupay|rupees|rupee|rs|inr|रुपये|रुपया|रू)?\s*"
        r"([a-zA-Z\u0900-\u097F]+(?:\s+[a-zA-Z\u0900-\u097F]+)?)?\s*"
        r"(?:rupaye|rupay|rupees|rupee|rs|inr|रुपये|rupay|रुपया|रू)?"
        r"(?=[,;\n+]|\s+[a-zA-Z\u0900-\u097F]{2,}|$)",
        re.IGNORECASE
    )

    for m in stream_pattern_a.finditer(active_text):
        raw_name = m.group(1).strip()
        raw_qty = m.group(2)
        raw_unit = m.group(3)
        price_digit = float(m.group(4))
        raw_echo = (m.group(5) or "").strip()
        echo_word = clean_echo_word(raw_echo)

        if price_digit < 15000 and len(raw_name) > 1:
            qty, unit = clean_unit_and_qty(raw_qty, raw_unit)
            name = clean_item_name(raw_name, language, output_lang)

            # Handle Grams rate calculation
            if unit in ("g", "gm") and qty >= 20:
                amount = price_digit
                unit_price = round((price_digit / qty) * 1000, 2)
            elif price_mode == "line_total":
                amount = price_digit
                unit_price = round(price_digit / max(qty, 0.001), 2)
            else:
                amount = round(qty * price_digit, 2)
                unit_price = price_digit

            items.append({
                "name": name,
                "quantity": qty,
                "unit": unit,
                "price": unit_price,
                "amount": amount,
                "spoken_pronunciation": echo_word,
            })
            matched_ranges.append((m.start(), m.end()))

    # Pattern B: [Qty] [Unit] [Name] [Price]
    # e.g. "1 kg sugar 60 rs", "1 kg sakhar 60 rs 2 kg maida 50 rs"
    if not items:
        stream_pattern_b = re.compile(
            r"(?:^|[\n,;+]|\s+)"
            r"(\d+(?:\.\d+)?)\s*"
            r"(kg|kilo|gm|g|gram|litre|liter|l|ml|packet|box|piece|pc|pcs|पाकीट|नग|किलो|ग्रॅम|ग्राम|लिटर|लीटर)\s+"
            r"([a-zA-Z\u0900-\u097F\s-]{2,30}?)\s+"
            r"(\d+(?:\.\d+)?)\s*"
            r"(?:rupaye|rupay|rupees|rupee|rs|inr|रुपये|रुपया|रू)?",
            re.IGNORECASE
        )
        for m in stream_pattern_b.finditer(active_text):
            raw_qty = m.group(1)
            raw_unit = m.group(2)
            raw_name = m.group(3).strip()
            price_digit = float(m.group(4))

            if price_digit < 15000 and len(raw_name) > 1:
                qty, unit = clean_unit_and_qty(raw_qty, raw_unit)
                name = clean_item_name(raw_name, language, output_lang)
                amount = round(qty * price_digit, 2) if price_mode == "per_unit" else price_digit
                unit_price = price_digit if price_mode == "per_unit" else round(price_digit / max(qty, 0.001), 2)

                items.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                    "price": unit_price,
                    "amount": amount,
                    "spoken_pronunciation": None,
                })

    if items:
        return items

    # 4. Fallback line-by-line parser for bare items or prices (e.g. "Sakhar 60", "Besan 50")
    lines = [l.strip() for l in re.split(r"[\n,;]+", normalized) if l.strip()]
    for line in lines:
        m_bare = re.search(r"^([a-zA-Z\u0900-\u097F\s]+?)\s+(\d+(?:\.\d+)?)\s*(?:rupaye|rupay|rupees|rs|रुपये)?\s*$", line)
        if m_bare:
            raw_name = m_bare.group(1).strip()
            price_val = float(m_bare.group(2))
            if price_val < 15000 and len(raw_name) > 1:
                name = clean_item_name(raw_name, language, output_lang)
                items.append({
                    "name": name,
                    "quantity": 1.0,
                    "unit": "piece",
                    "price": price_val,
                    "amount": price_val,
                    "spoken_pronunciation": None,
                })
                continue

    return items
