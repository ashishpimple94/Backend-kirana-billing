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


FILLER_WORDS = set([
    "टाका", "द्या", "पाहिजे", "घ्या", "करा", "आणखी", "आहे", "नाही", "दे", "दो", "लाओ",
    "baba", "dya", "taka", "de", "do", "bolo", "chala", "please", "bhai", "ani", "and", "aur", "va", "next", "then"
])


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

    price = 0.0
    qty = 1.0
    unit = "piece"
    has_explicit_qty = False
    has_explicit_price = False

    working = s

    # 1. Extract Price with currency: '60 rs', '50 रुपये', '80 , rs'
    price_m = re.search(rf"(\d+(?:\.\d+)?)\s*(?:,\s*)?{CURR_RE}", working, re.IGNORECASE)
    if price_m:
        price = float(price_m.group(1))
        has_explicit_price = True
        working = working[:price_m.start()] + " " + working[price_m.end():]

    # 2. Extract Quantity & Unit: '2 kg', '1 किलो', '500 gm', '1 , kg'
    qty_unit_m = re.search(rf"(\d+(?:\.\d+)?)\s*(?:,\s*)?({UNIT_RE})\b", working, re.IGNORECASE)
    if qty_unit_m:
        qty, unit = clean_unit_and_qty(qty_unit_m.group(1), qty_unit_m.group(2))
        has_explicit_qty = True
        working = working[:qty_unit_m.start()] + " " + working[qty_unit_m.end():]

    # 3. If price still 0, check trailing bare number: e.g. 'sakhar 2 kg 60', 'काहीतरी 2 kg 100'
    if not has_explicit_price:
        trailing_num_m = re.search(r"\b(\d+(?:\.\d+)?)\s*$", working)
        if trailing_num_m:
            num_val = float(trailing_num_m.group(1))
            price = num_val
            has_explicit_price = True
            working = working[:trailing_num_m.start()].strip()

    # 4. If qty still not found, check leading bare number: e.g. '2 colgate 40 rs' -> qty=2
    if not has_explicit_qty:
        leading_qty_m = re.search(r"^\s*(\d+(?:\.\d+)?)\s+", working)
        if leading_qty_m:
            qty = float(leading_qty_m.group(1))
            has_explicit_qty = True
            working = working[leading_qty_m.end():].strip()

    # 5. Extract item name from remaining words
    tokens = [w for w in re.split(r"[\s,;.+\-]+", working) if w]
    cleaned_tokens = [w for w in tokens if w.lower() not in FILLER_WORDS and not re.match(rf"^({CURR_RE}|{UNIT_RE})$", w, re.IGNORECASE)]

    raw_name = " ".join(cleaned_tokens).strip()

    # If quantity was not explicit and raw_name has a bare number (e.g. 'pant 1'):
    if not has_explicit_qty and raw_name:
        bare_num_m = re.search(r"\b(\d+(?:\.\d+)?)\b", raw_name)
        if bare_num_m:
            qty = float(bare_num_m.group(1))
            raw_name = (raw_name[:bare_num_m.start()] + " " + raw_name[bare_num_m.end():]).strip()

    if raw_name:
        name = clean_item_name(raw_name, language, output_lang)
        if not name:
            name = raw_name.title() if raw_name.isascii() else raw_name
    else:
        name = "Item"

    return [_make_item(name, qty, unit, price, price_mode)]


def merge_orphan_clauses(clauses: List[str]) -> List[str]:
    """Merges fragmented clauses where Whisper inserted commas between words of the same item."""
    merged = []
    i = 0
    while i < len(clauses):
        c = clauses[i].strip()
        while i + 1 < len(clauses):
            next_c = clauses[i + 1].strip()
            # If next clause is just a currency symbol/word (e.g. 'rs', 'रुपये')
            if re.match(rf"^({CURR_RE})$", next_c, re.IGNORECASE):
                c = c + " " + next_c
                i += 1
                continue
            # If current clause has no qty and no price, it's just a name or filler: merge next
            has_qty_or_unit = bool(re.search(rf"\b\d+\b|{UNIT_RE}", c, re.IGNORECASE))
            has_price = bool(re.search(rf"{CURR_RE}", c, re.IGNORECASE))
            if not has_qty_or_unit and not has_price:
                c = c + " " + next_c
                i += 1
                continue
            # If current has qty/unit, but next is just a number or price (e.g. '80' or '80 rs')
            if has_qty_or_unit and not has_price and re.match(rf"^\d+(?:\.\d+)?\s*(?:{CURR_RE})?$", next_c, re.IGNORECASE):
                c = c + " " + next_c
                i += 1
                continue
            # If current has price but NO qty/unit, and next has qty/unit but NO price (e.g. 'sakhar 60 rs' + '1 kg')
            c_without_price = re.sub(rf"(\d+(?:\.\d+)?)\s*(?:,\s*)?{CURR_RE}", "", c, flags=re.IGNORECASE)
            c_has_qty = bool(re.search(rf"\b\d+\b|{UNIT_RE}", c_without_price, re.IGNORECASE))
            next_without_price = re.sub(rf"(\d+(?:\.\d+)?)\s*(?:,\s*)?{CURR_RE}", "", next_c, flags=re.IGNORECASE)
            next_has_qty = bool(re.search(rf"\b\d+\b|{UNIT_RE}", next_without_price, re.IGNORECASE))
            next_has_price = bool(re.search(rf"{CURR_RE}", next_c, re.IGNORECASE))
            if has_price and not c_has_qty and next_has_qty and not next_has_price:
                c = c + " " + next_c
                i += 1
                continue
            # If current has qty and price, but NO name (e.g. '2 kg 50 rs' + 'xyz')
            c_without_qty = re.sub(rf"(\d+(?:\.\d+)?)\s*(?:,\s*)?({UNIT_RE})\b", "", c_without_price, flags=re.IGNORECASE)
            c_has_name = bool(re.search(r"[a-zA-Z\u0900-\u097F]", c_without_qty))
            next_has_name = bool(re.search(r"[a-zA-Z\u0900-\u097F]", next_without_price))
            if not c_has_name and next_has_name and not next_has_qty and not next_has_price:
                c = c + " " + next_c
                i += 1
                continue
            break
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
