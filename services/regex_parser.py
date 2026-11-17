"""
regex_parser.py
Fast-path Python Regex Parser for Kirana voice orders.
Extracts items, quantities, units, prices, and spoken pronunciations instantly (<5ms).
Handles:
- "Sakhar 1kg 60 sath" -> Name: साखर, Qty: 1, Unit: kg, Price: 60, Pronunciation: sath
- "Sugar 1kg 60 sixty" -> Name: साखर, Qty: 1, Unit: kg, Price: 60, Pronunciation: sixty
- "Masoor 1kg 95 panchyannav" -> Name: मसूर डाळ, Qty: 1, Unit: kg, Price: 95, Pronunciation: panchyannav
- "Patanjali biscuit box 10/- 710" -> Name: Patanjali biscuit box, Qty: 1, Unit: box, Price: 710
- "Sakhar 120" -> Name: साखर, Qty: 1, Unit: piece, Price: 120
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
    "gm": "gm", "g": "gm", "gram": "gm", "ग्रॅम": "gm",
    "litre": "litre", "liter": "litre", "l": "litre", "लिटर": "litre",
    "ml": "ml", "मिली": "ml",
    "packet": "packet", "pkt": "packet", "pack": "packet", "पाकीट": "packet",
    "box": "box", "खोके": "box", "बॉक्स": "box",
    "piece": "piece", "pc": "piece", "pcs": "piece", "नग": "piece",
    "bottle": "bottle", "बाटली": "bottle",
    "pau": "gm", "pav": "gm",
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

    if unit_key in ("pau", "pav"):
        qty = 250.0
        unit = "gm"

    return qty, unit


def clean_item_name(raw_name: str, language: str = "mr-IN") -> str:
    """Returns mapped Devanagari or clean capitalized title."""
    clean = raw_name.strip()
    lower = clean.lower()
    if lower in KIRANA_ITEMS_MAP:
        return KIRANA_ITEMS_MAP[lower]
    return clean.capitalize()


def parse_bill_with_regex(transcript: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parses speech lines into structured Kirana items.
    """
    if not transcript or not transcript.strip():
        return []

    options = options or {}
    price_mode = options.get("priceMode", "per_unit")

    normalized = normalize_voice_transcript(transcript)
    lines = [l.strip() for l in re.split(r"[\n,;]+", normalized) if l.strip()]

    items = []

    for line in lines:
        matched = False

        # Pattern 1: MRP line (e.g. "Patanjali biscuit box 10/- 710")
        m_mrp = re.search(r"^(.+?)\s+(\d+)\s*/-\s*(?:rupaye|rs|inr)?\s*(\d+(?:\.\d+)?)\s*$", line, re.IGNORECASE)
        if m_mrp:
            raw_name = m_mrp.group(1).strip()
            mrp_val = float(m_mrp.group(2))
            price_val = float(m_mrp.group(3))
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
                matched = True
                continue

        # Pattern 2: Pronunciation Echo Standard:
        # e.g. "Sakhar 1kg 60 sath" or "Sugar 1kg 60 sixty" or "Masoor 1kg 95 panchyannav"
        # Item + Qty + Unit + Price Digit + Spoken Pronunciation Word
        m_echo = re.search(
            r"^(.+?)\s+(\d+(?:\.\d+)?)\s*(kg|kilo|gm|gram|litre|liter|ml|packet|box|piece|pc|pcs|पाकीट|नग|किलो|ग्रॅम|लिटर)?\s+(\d+(?:\.\d+)?)\s+([a-zA-Z\u0900-\u097F]+(?:\s+[a-zA-Z\u0900-\u097F]+)?)\s*$",
            line,
            re.IGNORECASE
        )
        if m_echo:
            raw_name = m_echo.group(1).strip()
            raw_qty = m_echo.group(2)
            raw_unit = m_echo.group(3) or "piece"
            price_digit = float(m_echo.group(4))
            echo_word = m_echo.group(5).strip()

            if price_digit < 15000:
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
                matched = True
                continue

        # Pattern 3: Standard Item + Qty + Unit + Spoken Number / Digits
        # e.g. "Sakhar 1kg 120" or "Besan 1kg ekshe tees" or "Gahu 10kg chaarshey saath"
        m_std = re.search(
            r"^(.+?)\s+(\d+(?:\.\d+)?)\s*(kg|kilo|gm|gram|litre|liter|ml|packet|box|piece|pc|pcs|पाकीट|नग|किलो|ग्रॅम|लिटर)\s+(.+)$",
            line,
            re.IGNORECASE
        )
        if m_std:
            raw_name = m_std.group(1).strip()
            raw_qty = m_std.group(2)
            raw_unit = m_std.group(3)
            price_part = m_std.group(4).strip()

            price_val, pronunciation = extract_price_and_pronunciation(price_part)
            if price_val and price_val < 15000:
                qty, unit = clean_unit_and_qty(raw_qty, raw_unit)
                name = clean_item_name(raw_name)
                amount = round(qty * price_val, 2) if price_mode == "per_unit" else price_val
                unit_price = price_val if price_mode == "per_unit" else round(price_val / max(qty, 0.001), 2)

                items.append({
                    "name": name,
                    "quantity": qty,
                    "unit": unit,
                    "price": unit_price,
                    "amount": amount,
                    "spoken_pronunciation": pronunciation,
                })
                matched = True
                continue

        # Pattern 4: Bare Item + Price
        # e.g. "Sakhar 120" or "Besan 130" or "Maida 140" or "Chai 230"
        m_bare = re.search(r"^([a-zA-Z\u0900-\u097F\s]+?)\s+(\d+(?:\.\d+)?)\s*$", line)
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
                matched = True
                continue

        # Pattern 5: Bare Item + Word Price (e.g. "Sakhar ekshey vees", "Besan one thirty")
        for phrase, val in sorted(COMPOUND_PRICING_MAP.items(), key=lambda x: len(x[0]), reverse=True):
            if line.lower().endswith(phrase):
                raw_name = line[:len(line) - len(phrase)].strip()
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
                    matched = True
                    break

    return items
