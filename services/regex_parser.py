"""
regex_parser.py
Fast-path Python Regex Parser for Kirana voice orders.
Extracts items, quantities, units, prices, and spoken pronunciations instantly (<5ms).
Handles single lines, multiple lines, and continuous speech:
- "sakhar 1 kg /kilo 60 rupay maida 1kg/kilo 50 rupay" -> 2 items: साखर (1kg @ ₹60) + मैदा (1kg @ ₹50)
- "sakhar 1kg 60 rupaye saath rupaye maida 1kg 50 rupaye" -> 2 items with echo
- "Patanjali biscuit box 10/- 710" -> Patanjali biscuit box (MRP 10/- @ ₹710)
"""

import re
from typing import List, Dict, Any, Optional
from services.marathi_normalizer import (
    extract_price_and_pronunciation,
    normalize_voice_transcript,
    COMPOUND_PRICING_MAP,
    SPOKEN_NUMBER_WORDS,
)

# Common Marathi Kirana Item Translations
KIRANA_ITEMS_MAP = {
    "sakhar": "साखर", "sugar": "साखर", "shakkar": "साखर",
    "besan": "बेसन", "chana flour": "बेसन",
    "maida": "मैदा",
    "shengdane": "शेंगदाणे", "shengdana": "शेंगदाणे", "peanut": "शेंगदाणे", "peanuts": "शेंगदाणे", "mungfali": "शेंगदाणे",
    "moong dal": "मूग डाळ", "mung dal": "मूग डाळ", "moong": "मूग डाळ",
    "toor dal": "तूर डाळ", "tur dal": "तूर डाळ", "arhar dal": "तूर डाळ",
    "masoor": "मसूर डाळ", "masoor dal": "मसूर डाळ",
    "urad dal": "उडीद डाळ", "udid dal": "उडीद डाळ",
    "chana dal": "चना डाळ",
    "gahu": "गहू", "gehu": "गहू", "wheat": "गहू",
    "tandul": "तांदूळ", "chawal": "तांदूळ", "rice": "तांदूळ",
    "tel": "तेल", "oil": "तेल",
    "kaju": "काजू", "cashew": "काजू",
    "badam": "बदाम", "almond": "बदाम",
    "poha": "पोहे", "pohe": "पोहे",
    "mirchi": "मिरची", "chilli": "मिरची", "mirchi powder": "मिरची पावडर",
    "halad": "हळद", "haldi": "हळद", "turmeric": "हळद",
    "jeera": "जीरे", "jira": "जीरे", "cumin": "जीरे",
    "rai": "मोहरी", "mohari": "मोहरी", "mustard": "मोहरी",
    "dhania": "धने", "dhana": "धने", "coriander": "धने",
    "chai": "चहा पावडर", "chai patti": "चहा पावडर", "tea": "चहा पावडर", "chaha": "चहा पावडर",
    "doodh": "दूध", "milk": "दूध",
    "ghee": "तूप", "toop": "तूप",
    "sabun": "साबण", "soap": "साबण",
    "surf": "सर्फ / डिटर्जंट", "detergent": "डिटर्जंट",
    "biscuit": "बिस्कीट", "biscuits": "बिस्कीट",
    "atta": "गव्हाचे पीठ", "gahu pith": "गव्हाचे पीठ", "flour": "पीठ",
    "rawa": "रवा", "sooji": "रवा",
    "mith": "मीठ", "namak": "मीठ", "salt": "मीठ",
    "matki": "मटकी", "chana": "हरभरा / चणा",
    "patanjali biscuit box": "पतंजली बिस्कीट बॉक्स",
    "celary": "सेलरी (Celery)", "celery": "सेलरी (Celery)",
}

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
    qty = 1.0
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


def clean_item_name(raw_name: str) -> str:
    """Returns mapped Devanagari or clean capitalized title."""
    clean = raw_name.strip()
    # Remove leading junk like separators or connectors
    clean = re.sub(r"^(?:ani|aur|and|va|next|then|\+|,|-)\s+", "", clean, flags=re.IGNORECASE).strip()
    lower = clean.lower()
    if lower in KIRANA_ITEMS_MAP:
        return KIRANA_ITEMS_MAP[lower]
    return clean.capitalize()


def clean_echo_word(raw_echo: Optional[str]) -> Optional[str]:
    """Cleans pronunciation confirmation word, ensuring it is a recognized number/pronunciation."""
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

    normalized = normalize_voice_transcript(transcript)

    # 1. Normalize unit slashes like "kg/kilo", "1 kg / kilo", "1kg/kilo"
    normalized = re.sub(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo)\s*/\s*(?:kilo|kg|किलो)", r"\1 kg", normalized, flags=re.IGNORECASE)

    # 2. Extract MRP lines first (e.g. "Patanjali biscuit box 10/- 710")
    items = []
    matched_ranges = []

    mrp_pattern = re.compile(
        r"([a-zA-Z\u0900-\u097F\s-]{2,30}?)\s+(\d+)\s*/-\s*(?:rupaye|rupay|rs|inr|रुपये)?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE
    )
    for m in mrp_pattern.finditer(normalized):
        raw_name = m.group(1).strip()
        mrp_val = float(m.group(2))
        price_val = float(m.group(3))
        if price_val < 15000:
            name = clean_item_name(raw_name)
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

    # Mask out MRP matches so they don't get double parsed
    text_remaining = list(normalized)
    for start, end in matched_ranges:
        for idx in range(start, end):
            text_remaining[idx] = " "
    active_text = "".join(text_remaining)

    # 3. Stream-based multi-item matching for continuous speech:
    # Matches: [Name] [Qty] [Unit] [Price] [Optional currency/echo]
    stream_pattern = re.compile(
        r"(?:^|[\n,;+]|\s+)"
        r"([a-zA-Z\u0900-\u097F\s-]{2,30}?)\s+"
        r"(\d+(?:\.\d+)?)\s*"
        r"(kg|kilo|gm|gram|litre|liter|ml|packet|box|piece|pc|pcs|पाकीट|नग|किलो|ग्रॅम|ग्राम|लिटर|लीटर)(?:\s*/\s*(?:kilo|kg|किलो))?\s+"
        r"(\d+(?:\.\d+)?)\s*"
        r"(?:rupaye|rupay|rupees|rupee|rs|inr|रुपये|रुपया|रू)?\s*"
        r"([a-zA-Z\u0900-\u097F]+(?:\s+[a-zA-Z\u0900-\u097F]+)?)?\s*"
        r"(?:rupaye|rupay|rupees|rupee|rs|inr|रुपये|rupay|रुपया|रू)?"
        r"(?=[,;\n+]|\s+[a-zA-Z\u0900-\u097F]{2,}|$)",
        re.IGNORECASE
    )

    for m in stream_pattern.finditer(active_text):
        raw_name = m.group(1).strip()
        raw_qty = m.group(2)
        raw_unit = m.group(3)
        price_digit = float(m.group(4))
        raw_echo = (m.group(5) or "").strip()
        echo_word = clean_echo_word(raw_echo)

        if price_digit < 15000 and len(raw_name) > 1:
            qty, unit = clean_unit_and_qty(raw_qty, raw_unit)
            name = clean_item_name(raw_name)
            amount = round(qty * price_digit, 2) if price_mode == "per_unit" else price_digit
            unit_price = price_digit if price_mode == "per_unit" else round(price_digit / max(qty, 0.001), 2)

            items.append({
                "name": name,
                "quantity": qty,
                "unit": unit,
                "price": unit_price,
                "amount": amount,
                "spoken_pronunciation": echo_word,
            })
            matched_ranges.append((m.start(), m.end()))

    if items:
        return items

    # 4. Fallback line-by-line parser for bare prices or words (e.g. "Sakhar 120", "Besan ekshey tees")
    lines = [l.strip() for l in re.split(r"[\n,;]+", normalized) if l.strip()]
    for line in lines:
        # Bare Item + Price (e.g. "Sakhar 120", "Besan 130")
        m_bare = re.search(r"^([a-zA-Z\u0900-\u097F\s]+?)\s+(\d+(?:\.\d+)?)\s*(?:rupaye|rupay|rupees|rs|रुपये)?\s*$", line)
        if m_bare:
            raw_name = m_bare.group(1).strip()
            price_val = float(m_bare.group(2))
            if price_val < 15000 and len(raw_name) > 1:
                name = clean_item_name(raw_name)
                items.append({
                    "name": name,
                    "quantity": 1.0,
                    "unit": "piece",
                    "price": price_val,
                    "amount": price_val,
                    "spoken_pronunciation": None,
                })
                continue

        # Bare Item + Word Price (e.g. "Sakhar ekshey vees")
        line_clean = re.sub(r"\b(?:rupaye|rupay|rupees|rs|रुपये)\b", "", line, flags=re.IGNORECASE).strip()
        for phrase, val in sorted(COMPOUND_PRICING_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if line_clean.lower().endswith(phrase) or line_clean.endswith(phrase):
                raw_name = line_clean[:len(line_clean) - len(phrase)].strip()
                if raw_name:
                    name = clean_item_name(raw_name)
                    items.append({
                        "name": name,
                        "quantity": 1.0,
                        "unit": "piece",
                        "price": float(val),
                        "amount": float(val),
                        "spoken_pronunciation": phrase,
                    })
                    break

    return items
