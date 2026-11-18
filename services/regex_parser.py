"""
regex_parser.py
PERMISSIVE Kirana voice bill parser — adds EVERYTHING spoken to the bill.
Philosophy: Never return 0 items if there is ANY word + number in the transcript.
Supports:
- "मुरमुरे एक किलो ऐंशी रुपये"       -> मुरमुरे 1kg @ ₹80
- "sakhar 1 kg 60 rs maida 1kg 50 rs"  -> साखर 1kg @ ₹60 + मैदा 1kg @ ₹50
- "एक किलो ऐंशी रुपये"                 -> Item 1kg @ ₹80  (no name = "Item")
- "साखर साठ"                            -> साखर 1pc @ ₹60
- "मुरमुरा, एक किलो, आईशी रुपये"       -> मुरमुरे 1kg @ ₹80
"""

import re
from typing import List, Dict, Any, Optional

from services.marathi_normalizer import (
    normalize_marathi_transcript,
    canonicalize_marathi_item_name,
    COMPOUND_PRICING_MAP,
    SPOKEN_NUMBER_WORDS,
)

# ── Unit aliases ────────────────────────────────────────────────────────────────
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

# Regex string for unit words
UNIT_RE = (
    r"kg|kilo|gm|gram|litre|liter|ml|packet|pkt|box|piece|pc|pcs|bottle"
    r"|किलो|केजी|ग्रॅम|ग्राम|लिटर|लीटर|मिली|पाकीट|पुडा|खोके|बॉक्स|नग|बाटली"
)

# Noise words to strip from item name candidates
NOISE_WORDS = re.compile(
    r"^(?:ani|aur|and|va|next|then|rs|rupaye|rupay|rupees|रुपये|रुपया|रू|\+|,|-)$",
    re.IGNORECASE,
)
PRICE_SUFFIX = re.compile(r"\s*(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू|₹)\s*$", re.IGNORECASE)
CONNECTOR_PREFIX = re.compile(r"^(?:rs|rupaye|rupay|rupees|inr|रुपये|रुपया|रू|₹|\+|,|-)\s+", re.IGNORECASE)


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
    # Remove leading digits / currency
    s = re.sub(r"^\d+\s*", "", s).strip()
    if not s:
        return ""
    return canonicalize_marathi_item_name(s, language, output_lang)


def _make_item(name, qty, unit, price, price_mode):
    if price_mode == "line_total":
        amount = price
        unit_price = round(price / max(qty, 0.001), 2)
    elif unit == "gm" and qty >= 20:
        # Grams: price is line total
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


def parse_bill_with_regex(transcript: str, options: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Ultra-permissive parser. ALWAYS returns items if ANY number appears in transcript.
    Priority order:
      1. MRP lines  (name  MRP/-  price)
      2. Pattern A  (name  qty  unit  price)
      3. Pattern B  (qty  unit  name  price)
      4. No-name    (qty  unit  price)  → item named "Item"
      5. Bare-price (name  price)       → 1 pc
      6. Last resort: any word + any number → item at that price
    """
    if not transcript or not transcript.strip():
        return []

    options = options or {}
    price_mode = options.get("priceMode", "per_unit")
    language = options.get("language", "mr-IN")
    output_lang = options.get("outputLang", None)

    # ── Full normalisation (number words → digits, units standardised, phonetic fixes) ──
    normalized = normalize_marathi_transcript(transcript)

    items: List[Dict[str, Any]] = []
    matched_spans: List[tuple] = []        # (start, end) to avoid double-matching

    def already_matched(start, end):
        for s, e in matched_spans:
            if start < e and end > s:
                return True
        return False

    # ────────────────────────────────────────────────────────────────────────────
    # 1. MRP lines: "Patanjali biscuit box 10/- 710"
    # ────────────────────────────────────────────────────────────────────────────
    mrp_pat = re.compile(
        r"([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,40}?)\s+(\d+)\s*/-\s*(?:rs|rupaye|rupay|rupees|inr|रुपये)?\s*(\d+(?:\.\d+)?)",
        re.IGNORECASE,
    )
    for m in mrp_pat.finditer(normalized):
        price_val = float(m.group(3))
        if price_val > 15000:
            continue
        name = clean_item_name(m.group(1), language, output_lang)
        unit_type = "box" if "box" in m.group(1).lower() else "piece"
        items.append({
            "name": name or "Item",
            "quantity": 1.0,
            "unit": unit_type,
            "price": price_val,
            "amount": price_val,
            "mrp": float(m.group(2)),
            "spoken_pronunciation": None,
        })
        matched_spans.append((m.start(), m.end()))

    # Mask matched text
    active = list(normalized)
    for s, e in matched_spans:
        for i in range(s, e):
            active[i] = " "
    active_text = "".join(active)

    # ────────────────────────────────────────────────────────────────────────────
    # 2. Pattern A: [Name]  [Qty]  [Unit]  [Price]
    #    "साखर 1 kg 60 rs", "मुरमुरे 1 kg 80", "tandul 2 kilo 100 rs"
    # ────────────────────────────────────────────────────────────────────────────
    pat_a = re.compile(
        r"(?:^|[\s,;+])"
        r"([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{0,35}?)\s+"   # name (1+ chars)
        r"(\d+(?:\.\d+)?)\s*"                                         # qty
        r"(" + UNIT_RE + r")(?:\s*/\s*(?:kilo|kg|किलो))?\s+"          # unit
        r"(\d+(?:\.\d+)?)\s*"                                         # price
        r"(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू)?"
        r"(?=[\s,;+]|$)",
        re.IGNORECASE,
    )
    for m in pat_a.finditer(active_text):
        if already_matched(m.start(), m.end()):
            continue
        raw_name = m.group(1).strip()
        price_val = float(m.group(4))
        if price_val > 15000 or len(raw_name) < 1:
            continue
        qty, unit = clean_unit_and_qty(m.group(2), m.group(3))
        name = clean_item_name(raw_name, language, output_lang)
        items.append(_make_item(name or "Item", qty, unit, price_val, price_mode))
        matched_spans.append((m.start(), m.end()))

    # Remask
    for s, e in matched_spans:
        for i in range(s, min(e, len(active))):
            active[i] = " "
    active_text = "".join(active)

    # ────────────────────────────────────────────────────────────────────────────
    # 3. Pattern B: [Qty] [Unit] [Name?] [Price]
    #    "1 kg sakhar 60 rs", "1 किलो मुरमुरे 80 रुपये", "1 किलो 80 रुपये"
    # ────────────────────────────────────────────────────────────────────────────
    pat_b = re.compile(
        r"(?:^|[\s,;+])"
        r"(\d+(?:\.\d+)?)\s*"                                        # qty
        r"(" + UNIT_RE + r")\s+"                                      # unit
        r"([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{0,35}?)?\s*"   # optional name
        r"(\d+(?:\.\d+)?)\s*"                                        # price
        r"(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू)?"
        r"(?=[\s,;+]|$)",
        re.IGNORECASE,
    )
    for m in pat_b.finditer(active_text):
        if already_matched(m.start(), m.end()):
            continue
        price_val = float(m.group(4))
        if price_val > 15000:
            continue
        qty, unit = clean_unit_and_qty(m.group(1), m.group(2))
        raw_name = (m.group(3) or "").strip()
        name = clean_item_name(raw_name, language, output_lang) if raw_name else "Item"
        items.append(_make_item(name or "Item", qty, unit, price_val, price_mode))
        matched_spans.append((m.start(), m.end()))

    # Remask
    for s, e in matched_spans:
        for i in range(s, min(e, len(active))):
            active[i] = " "
    active_text = "".join(active)

    if items:
        return items

    # ────────────────────────────────────────────────────────────────────────────
    # 4. Bare-price fallback: "Sakhar 60", "बेसन 50 रुपये" (no unit)
    # ────────────────────────────────────────────────────────────────────────────
    lines = [l.strip() for l in re.split(r"[\n,;]+", normalized) if l.strip()]
    for line in lines:
        m = re.search(
            r"^([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{0,35}?)\s+(\d+(?:\.\d+)?)\s*(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू)?$",
            line,
        )
        if m:
            raw_name = m.group(1).strip()
            price_val = float(m.group(2))
            if 1 <= price_val <= 15000 and len(raw_name) >= 1:
                name = clean_item_name(raw_name, language, output_lang)
                items.append({
                    "name": name or "Item",
                    "quantity": 1.0,
                    "unit": "piece",
                    "price": price_val,
                    "amount": price_val,
                    "spoken_pronunciation": None,
                })

    if items:
        return items

    # ────────────────────────────────────────────────────────────────────────────
    # 5. No-name qty+unit+price: "1 किलो 80 रुपये" after stripping filler words
    # ────────────────────────────────────────────────────────────────────────────
    no_name_pat = re.compile(
        r"(\d+(?:\.\d+)?)\s*(" + UNIT_RE + r")\s+(\d+(?:\.\d+)?)\s*(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू)?",
        re.IGNORECASE,
    )
    for m in no_name_pat.finditer(normalized):
        price_val = float(m.group(3))
        if 1 <= price_val <= 15000:
            qty, unit = clean_unit_and_qty(m.group(1), m.group(2))
            items.append(_make_item("Item", qty, unit, price_val, price_mode))

    if items:
        return items

    # ────────────────────────────────────────────────────────────────────────────
    # 6. ABSOLUTE LAST RESORT: grab any word(s) + any number  → 1pc at that price
    #    Ensures we NEVER return empty when something was heard.
    # ────────────────────────────────────────────────────────────────────────────
    last_resort_pat = re.compile(
        r"([a-zA-Z\u0900-\u097F][\w\u0900-\u097F\s-]{1,40}?)\s+(\d+(?:\.\d+)?)\s*(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू)?(?=\s|$)",
        re.IGNORECASE,
    )
    seen_prices = set()
    for m in last_resort_pat.finditer(normalized):
        raw_name = m.group(1).strip()
        price_val = float(m.group(2))
        if price_val < 1 or price_val > 15000:
            continue
        if price_val in seen_prices:
            continue
        seen_prices.add(price_val)
        # Skip pure number words / unit tokens that slipped through
        if re.match(r"^(?:rs|rupaye|rupay|rupees|inr|kg|kilo|gm|gram|litre|liter|ml|packet|box|piece|pc|pcs|bottle|किलो|ग्रॅम|लिटर|मिली|पाकीट|नग|बाटली)$", raw_name, re.IGNORECASE):
            continue
        name = clean_item_name(raw_name, language, output_lang)
        items.append({
            "name": name or "Item",
            "quantity": 1.0,
            "unit": "piece",
            "price": price_val,
            "amount": price_val,
            "spoken_pronunciation": None,
        })

    return items
