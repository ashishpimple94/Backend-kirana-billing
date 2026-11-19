"""
regex_parser.py
Fine-tuned Kirana Voice Bill Parser.
Philosophy: Accurately captures quantity, unit, product name, and price across all Kirana voice patterns.
Supports:
- "मुरमुरे एक किलो ऐंशी रुपये"            -> मुरमुरे 1kg @ ₹80
- "२ किलो साखर ६० रुपये १ किलो मैदा ४० रुपये" -> साखर 2kg @ ₹60 + मैदा 1kg @ ₹40
- "२ पार्ले बॉक्स १२० रुपये"             -> पार्ले 2 box @ ₹120
- "साखर २ किलो, मैदा १ किलो, पोहे ५०० ग्रॅम" -> साखर 2kg + मैदा 1kg + पोहे 500gm (price: 0)
- "१ किलो साखर, २ किलो पोहे, १ लिटर तेल"     -> साखर 1kg + पोहे 2kg + तेल 1L (price: 0)
- "५ मॅगी पन्नास रुपये"                   -> मॅगी 5 pcs @ ₹50
- "२ साबण ४० रुपये"                      -> साबण 2 pcs @ ₹40
- "१ लक्स, २ संतूर, ३ मॅगी"              -> साबण 1pc + साबण 2pcs + मॅगी 3pcs
- "साखर ४० रुपये, मैदा ३० रुपये"          -> साखर 1pc @ ₹40 + मैदा 1pc @ ₹30
- "पाव किलो साखर तीस रुपये"              -> साखर 250gm @ ₹120/kg (amount: ₹30)
- "अर्धा किलो शेंगदाणे साठ रुपये"          -> शेंगदाणे 500gm @ ₹120/kg (amount: ₹60)
- "दीड किलो तांदूळ पंचाहत्तर रुपये"         -> तांदूळ 1.5kg @ ₹75
- "एक किलो, आइंशी रुपये."                -> Item 1kg @ ₹80
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
    "dozen": "dozen", "डझन": "dozen",
    "pau": "gm", "pav": "gm", "पाव": "gm",
}

UNIT_RE = (
    r"kg|kilo|gm|gram|litre|liter|ml|packet|pkt|box|piece|pc|pcs|bottle|dozen"
    r"|किलो|केजी|ग्रॅम|ग्राम|लिटर|लीटर|मिली|पाकीट|पुडा|खोके|बॉक्स|नग|बाटली|डझन"
)

CURR_RE = r"(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू|₹|\/-)"
NO_UNIT_LOOKAHEAD = rf"(?!\s*(?:{UNIT_RE}))"

PRICE_SUFFIX = re.compile(rf"\s*{CURR_RE}\s*$", re.IGNORECASE)
CONNECTOR_PREFIX = re.compile(rf"^(?:ani|aur|and|va|next|then|{CURR_RE}|\+|,|-)\s+", re.IGNORECASE)


def clean_unit_and_qty(raw_qty: str, raw_unit: str):
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


def clean_item_name(raw: str, language: str = "mr-IN", output_lang: Optional[str] = None) -> str:
    s = CONNECTOR_PREFIX.sub("", raw).strip()
    s = PRICE_SUFFIX.sub("", s).strip()
    s = re.sub(r"^\d+\s*", "", s).strip()
    s = re.sub(r"^[\s,;+\-.]+|[\s,;+\-.]+$", "", s).strip()
    if not s:
        return ""
    return canonicalize_marathi_item_name(s, language, output_lang)


def _make_item(name, qty, unit, price, price_mode="per_unit"):
    if price_mode == "line_total":
        amount = price
        unit_price = round(price / max(qty, 0.001), 2)
    elif unit in ("gm", "ml") and qty >= 20 and price > 0:
        amount = price
        unit_price = round((price / qty) * 1000, 2)
    else:
        amount = round(qty * price, 2)
        unit_price = price
    return {
        "name": name or "Item",
        "quantity": qty,
        "unit": unit,
        "price": unit_price,
        "amount": amount,
        "spoken_pronunciation": None,
    }


def parse_segment(seg: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    s = seg.strip()
    if not s:
        return []

    options = options or {}
    price_mode = options.get("priceMode", "per_unit")
    language = options.get("language", "mr-IN")
    output_lang = options.get("outputLang", None)

    # 1. MRP (e.g. "Patanjali biscuit box 10/- 710")
    m = re.search(
        r"^([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,35}?)\s+(\d+)\s*/-\s*(?:rs|rupaye|rupay|rupees|inr|रुपये)?\s*(\d+(?:\.\d+)?)$",
        s,
        re.IGNORECASE
    )
    if m:
        name = clean_item_name(m.group(1), language, output_lang)
        unit_type = "box" if "box" in m.group(1).lower() else "piece"
        return [{
            "name": name or "Item",
            "quantity": 1.0,
            "unit": unit_type,
            "price": float(m.group(3)),
            "amount": float(m.group(3)),
            "mrp": float(m.group(2)),
            "spoken_pronunciation": None,
        }]

    # 2. Pattern A: [Name] [Qty] [Unit] [Price] (e.g. "साखर 2 kg 60 rs", "मुरमुरे 1 kg 80 rs")
    m = re.search(
        r"^([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{0,35}?)\s+(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")\s+(\d+(?:\.\d+)?)" + NO_UNIT_LOOKAHEAD + r"(?:\s*" + CURR_RE + r")?$",
        s,
        re.IGNORECASE
    )
    if m:
        qty, unit = clean_unit_and_qty(m.group(2), m.group(3))
        name = clean_item_name(m.group(1), language, output_lang)
        return [_make_item(name or "Item", qty, unit, float(m.group(4)), price_mode)]

    # 3. Pattern B: [Qty] [Unit] [Name] [Price] (e.g. "2 kg साखर 60 rs", "1 kg मैदा 40 rs")
    m = re.search(
        r"^(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")\s+([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,35}?)\s+(\d+(?:\.\d+)?)" + NO_UNIT_LOOKAHEAD + r"(?:\s*" + CURR_RE + r")?$",
        s,
        re.IGNORECASE
    )
    if m:
        qty, unit = clean_unit_and_qty(m.group(1), m.group(2))
        name = clean_item_name(m.group(3), language, output_lang)
        return [_make_item(name or "Item", qty, unit, float(m.group(4)), price_mode)]

    # 3b. Pattern: [Qty] [Unit] [Price] [Name] (e.g. "1 kg 60 rs sakhar")
    m = re.search(
        r"^(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")\s+(\d+(?:\.\d+)?)" + NO_UNIT_LOOKAHEAD + r"(?:\s*" + CURR_RE + r")?\s+([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,35}?)$",
        s,
        re.IGNORECASE
    )
    if m:
        qty, unit = clean_unit_and_qty(m.group(1), m.group(2))
        name = clean_item_name(m.group(4), language, output_lang)
        return [_make_item(name or "Item", qty, unit, float(m.group(3)), price_mode)]

    # 4. Pattern E: [Qty] [Name] [Unit] [Price] (e.g. "2 पार्ले box 120 rs")
    m = re.search(
        r"^(\d+(?:\.\d+)?)\s+([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,30}?)\s+(" + UNIT_RE + r")\s+(\d+(?:\.\d+)?)" + NO_UNIT_LOOKAHEAD + r"(?:\s*" + CURR_RE + r")?$",
        s,
        re.IGNORECASE
    )
    if m:
        qty, unit = clean_unit_and_qty(m.group(1), m.group(3))
        name = clean_item_name(m.group(2), language, output_lang)
        return [_make_item(name or "Item", qty, unit, float(m.group(4)), price_mode)]

    # 5. Pattern QNP: [Qty] [Name] [Price] with explicit currency (e.g. "5 मॅगी 50 rs", "2 साबण 40 rs")
    m = re.search(
        r"^(\d+(?:\.\d+)?)\s+([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,30}?)\s+(\d+(?:\.\d+)?)" + NO_UNIT_LOOKAHEAD + r"\s*" + CURR_RE + r"$",
        s,
        re.IGNORECASE
    )
    if m:
        raw_name = m.group(2).strip()
        if not re.match(r"^(" + UNIT_RE + r"|" + CURR_RE + r")$", raw_name, re.IGNORECASE):
            name = clean_item_name(raw_name, language, output_lang)
            return [_make_item(name or "Item", float(m.group(1)), "piece", float(m.group(3)), price_mode)]

    # 6. Pattern: [Name] [Price] with currency (e.g. "साखर 40 rs", "बेसन 50 rs")
    m = re.search(
        r"^([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,35}?)\s+(\d+(?:\.\d+)?)\s*" + CURR_RE + r"$",
        s,
        re.IGNORECASE
    )
    if m:
        raw_name = m.group(1).strip()
        if not re.match(r"^(" + UNIT_RE + r"|" + CURR_RE + r")$", raw_name, re.IGNORECASE):
            name = clean_item_name(raw_name, language, output_lang)
            return [_make_item(name or "Item", 1.0, "piece", float(m.group(2)), price_mode)]

    # 7. Pattern: [Qty] [Unit] [Name] (no price, e.g. "2 kg साखर", "1 kg मैदा", "1 litre तेल")
    m = re.search(
        r"^(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")\s+([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,35}?)$",
        s,
        re.IGNORECASE
    )
    if m:
        qty, unit = clean_unit_and_qty(m.group(1), m.group(2))
        name = clean_item_name(m.group(3), language, output_lang)
        return [_make_item(name or "Item", qty, unit, 0.0, price_mode)]

    # 8. Pattern: [Name] [Qty] [Unit] (no price, e.g. "साखर 2 kg", "मैदा 1 kg", "पोहे 500 gm")
    m = re.search(
        r"^([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,35}?)\s+(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")$",
        s,
        re.IGNORECASE
    )
    if m:
        qty, unit = clean_unit_and_qty(m.group(2), m.group(3))
        name = clean_item_name(m.group(1), language, output_lang)
        return [_make_item(name or "Item", qty, unit, 0.0, price_mode)]

    # 9. Pattern: [Qty] [Unit] [Price] (no name, e.g. "1 kg 80 rs")
    m = re.search(
        r"^(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")\s+(\d+(?:\.\d+)?)" + NO_UNIT_LOOKAHEAD + r"(?:\s*" + CURR_RE + r")?$",
        s,
        re.IGNORECASE
    )
    if m:
        qty, unit = clean_unit_and_qty(m.group(1), m.group(2))
        return [_make_item("Item", qty, unit, float(m.group(3)), price_mode)]

    # 10. Pattern: [Qty] [Name] (no unit, no price, e.g. "1 lux", "2 santoor", "3 maggi")
    m = re.search(
        r"^(\d+(?:\.\d+)?)\s+([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,30}?)$",
        s,
        re.IGNORECASE
    )
    if m:
        raw_name = m.group(2).strip()
        if not re.match(r"^(" + UNIT_RE + r"|" + CURR_RE + r")$", raw_name, re.IGNORECASE):
            name = clean_item_name(raw_name, language, output_lang)
            if name:
                return [_make_item(name, float(m.group(1)), "piece", 0.0, price_mode)]

    # 11. Pattern: Bare Name Price (e.g. "साखर 60", "मैदा 50")
    m = re.search(
        r"^([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,35}?)\s+(\d+(?:\.\d+)?)$",
        s,
        re.IGNORECASE
    )
    if m:
        raw_name = m.group(1).strip()
        price_val = float(m.group(2))
        if not re.match(r"^(" + UNIT_RE + r"|" + CURR_RE + r")$", raw_name, re.IGNORECASE) and 1 <= price_val <= 15000:
            name = clean_item_name(raw_name, language, output_lang)
            if name:
                return [_make_item(name, 1.0, "piece", price_val, price_mode)]

    return []


def merge_orphan_clauses(clauses: List[str]) -> List[str]:
    """Merges fragmented clauses where Whisper inserted commas between words of the same item."""
    merged = []
    i = 0
    while i < len(clauses):
        c = clauses[i].strip()
        has_qty_or_unit = bool(re.search(rf"\b\d+\b|{UNIT_RE}", c, re.IGNORECASE))
        has_price = bool(re.search(rf"{CURR_RE}", c, re.IGNORECASE))

        # If clause is just an item name (no numbers, no unit, no price), merge with next if available
        if not has_qty_or_unit and not has_price and i + 1 < len(clauses):
            c = c + " " + clauses[i + 1].strip()
            i += 1
            # Check if next is also an orphan price piece (e.g. '80 rs')
            if i + 1 < len(clauses):
                next_c = clauses[i + 1].strip()
                if not re.search(rf"{UNIT_RE}", next_c, re.IGNORECASE) and re.search(rf"\d|{CURR_RE}", next_c, re.IGNORECASE):
                    c = c + " " + next_c
                    i += 1
        # If clause has qty+unit but next clause is just bare price (e.g. '1 kg' and '80 rs')
        elif i + 1 < len(clauses):
            next_c = clauses[i + 1].strip()
            if re.match(rf"^\d+(?:\.\d+)?\s*(?:{CURR_RE})?$", next_c, re.IGNORECASE):
                c = c + " " + next_c
                i += 1
            elif not re.search(rf"\b\d+\b|{UNIT_RE}|{CURR_RE}", next_c, re.IGNORECASE):
                c = c + " " + next_c
                i += 1
        merged.append(c)
        i += 1
    return merged


def parse_bill_with_regex(transcript: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Parses speech lines or continuous stream into structured Kirana items with exact quantities and items.
    """
    if not transcript or not transcript.strip():
        return []

    norm = normalize_marathi_transcript(transcript)

    # Convert multi-item connectors into commas: "आणि", "तसेच", "व", "त्यानंतर", "and", "aur"
    norm_split = re.sub(r"\s+(?:आणि|तसेच|व|त्यानंतर|त्याच्यानंतर|and|aur|next|then)\s+", " , ", norm, flags=re.IGNORECASE)

    # Insert comma after currency word if followed by another word/number (for continuous stream)
    norm_split = re.sub(rf"({CURR_RE})\s+(?=[a-zA-Z\u0900-\u097F\d])", r"\1 , ", norm_split, flags=re.IGNORECASE)

    # Split into raw segments
    raw_segments = [seg.strip() for seg in re.split(r"[,;\n+|]+", norm_split) if seg.strip()]

    # Merge orphan fragments (e.g. 'मुरमुरे' + '1 kg' + '80 rs' -> 'मुरमुरे 1 kg 80 rs')
    segments = merge_orphan_clauses(raw_segments)

    items = []
    for seg in segments:
        parsed = parse_segment(seg, options)
        if parsed:
            items.extend(parsed)

    return items
