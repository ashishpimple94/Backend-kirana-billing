"""
llm_service.py
Python equivalent of services/llmService.js
Unified LLM Audio & Transcript Parser Service for Bilzy Kirana Billing.
Supports:
- GroqProvider (Whisper-large-v3-turbo with full Marathi Kirana vocabulary prompt + FastPath regex)
- GeminiProvider (gemini-2.0-flash, gemini-1.5-flash inline audio & transcript parsing)
- OpenAIProvider (Whisper-1 + gpt-4o-mini)
- Full sanitize_items, canonicalize_unit, and normalize_item_name logic
"""

import os
import re
import json
import base64
import httpx
from typing import List, Dict, Any, Optional

from services.marathi_normalizer import (
    DEV_TO_ASCII,
    normalize_voice_transcript,
)
from services.regex_parser import parse_bill_with_regex, clean_item_name, clean_unit_and_qty

SYSTEM_PROMPT = """You are an expert bilingual Kirana Billing Assistant specialized in Indian dialects (Marathi, Hindi, English, and Hinglish).
Listen to the shopkeeper speaking fast counter billing items (often 2 to 50 items spoken continuously).
Extract EVERY single item mentioned with high accuracy. Never stop early.

CRITICAL RULES:
1. SPOKEN LANGUAGE PRESERVATION & CLEAN SCRIPT (MANDATORY):
- Return the item name in the EXACT language spoken by the customer/shopkeeper!
- In MARATHI mode (default mr-IN): ALWAYS output pure Devanagari Marathi script:
  "साखर" (NEVER output "sakhar" or "sakhar-sakhar"),
  "पोहे" (NEVER output "pohe" or "poha"),
  "तूर डाळ" (NEVER output "toor dal" or "tur"),
  "गोडेतेल" or "तेल" (NEVER output "tel" or "godetel"),
  "गूळ", "रवा", "चहा", "दूध", "साबण", "कांदे", "बटाटे", "शेंगदाणे", "लसूण", "मीठ".
- In HINDI mode: ALWAYS output pure Devanagari Hindi script: "चीनी", "अरहर दाल", "चावल", "तेल", "नमक".
- In ENGLISH mode: ALWAYS output clean English names: "Sugar", "Rice", "Tea", "Soap".
- NEVER output hyphenated duplicates or acoustic stutter (e.g. "sakhar-sakhar" -> "साखर", "साखर-साखर" -> "साखर", "चहा-चहा" -> "चहा"). Always deduplicate into a single clean product name!
- In Marathi or Hindi, NEVER output Roman/English alphabet transliterations (no "sakhar", no "tel", no "tandul").

2. MARATHI FRACTIONS & WEIGHTS:
- "पाव" (paav / pav) = 0.25 (e.g. "पाव किलो साखर" -> 0.25 kg साखर, or 250 g)
- "अर्धा" / "अर्धी" (ardha / ardhi) = 0.5 (e.g. "अर्धा किलो तेल" -> 0.5 litre तेल, or 500 ml)
- "पाऊण" (paun) = 0.75
- "सव्वा" (savva) = 1.25
- "दीड" (deed / dedh) = 1.5
- "अडीच" (adeech / dhai) = 2.5
- "साडेतीन" = 3.5, "साडेचार" = 4.5, "साडेपाच" = 5.5
- "पावशेर" = 0.25 kg, "अर्धा शेर" = 0.5 kg, "शेर" = 1 kg
- "डझन" (dozen) = 12 piece, "नग" = piece, "पुडा" / "पाकीट" = packet

3. MARATHI NUMBERS, HUNDREDS & COMPOUNDS (CRITICAL):
- Single numbers: एक=1, दोन=2, तीन=3, चार=4, पाच=5, सहा=6, सात=7, आठ=8, नऊ=9, दहा=10, अकरा=11, बारा=12, तेरा=13, चौदा=14, पंधरा=15, सोळा=16, सतरा=17, अठरा=18, एकोणीस=19, वीस=20, पंचवीस=25, तीस=30, पस्तीस=35, चाळीस=40, पन्नास=50, साठ=60, सत्तर=70, ऐंशी=80, नव्वद=90.
- Hundreds & Fractions: शंभर/एकशे/एकसे/shambhar=100, दीडशे/didhshe/deedshe=150, सव्वाशे/savvashe=125, दोनशे/donshe=200, अडीचशे/adeechshe/dhai sau=250, तीनशे/teenshe=300, साडेतीनशे/sadeteenshe=350, चारशे/charshe=400, साडेचारशे/sadecharshe=450, पाचशे/pachshe=500, साडेपाचशे/sadepachshe=550, सहाशे/sahashe=600, सातशे/satshe=700, आठशे/aathshe=800, नऊशे/naushe=900, एक हजार=1000.
- Bilingual Number Echoes (MANDATORY): "100 shambhar" = 100, "shambhar 100" = 100, "didhshe 150" / "150 didhshe" = 150, "50 pannas" = 50, "60 saath" = 60, "250 adeechshe" = 250, "80 aainshi" = 80. Extract the single numeric rate (e.g. 100, 150, 50, 60), NEVER mistake the Marathi word for a product name!
- Thousands (Scalable Compound Numbers 1 to 5000):
  - "पाच हजार" / "pach hajar" / "panch hazar" / "5 hajar" / "five thousand" = 5000
  - "दोन हजार पाचशे" / "अडीच हजार" / "two thousand five hundred" = 2500
  - "दोन हजार" / "two thousand" = 2000
  - "एक हजार पाचशे" / "दीड हजार" / "fifteen hundred" = 1500
  - "एक हजार दोनशे" / "बाराशे" / "twelve hundred" = 1200
  - "एक हजार एकशे चाळीस" / "अकराशे चाळीस" / "eleven forty" = 1140
  - "एक हजार" / "one thousand" = 1000
  - STRICT GUARD: Kirana retail billing prices are strictly between 1 to 5000 rupees. NEVER hallucinate 100000 (one lakh) or large numbers! Words like "लाव", "टाक", "द्या", "लागतील" or brands like "लक्स" (Lux) must NEVER be mistaken for "लाख" or 100000.
- Compound hundreds & prices across Marathi, Hindi & English (1 to 5000):
  - 120: "एकशे वीस" / "ekshe vees" / "ek sau bees" / "one twenty" = 120
  - 130: "एकशे तीस" / "ekshe tees" / "ek sau tees" / "one thirty" = 130
  - 140: "एकशे चाळीस" / "ekshe chalis" / "ek sau chalis" / "one forty" = 140
  - 160: "एकशे साठ" / "ekshe saath" / "ek sau saath" / "one sixty" = 160
  - 230: "दोनशे तीस" / "donshey tees" / "do sau tees" / "two thirty" = 230
  - 260: "दोनशे साठ" / "donshey saath" / "do sau saath" / "two sixty" = 260
  - 280: "दोनशे ऐंशी" / "donshey aainshi" / "do sau assi" / "two eighty" = 280
  - 380: "तीनशे ऐंशी" / "teenshey aainshi" / "teen sau assi" / "three eighty" = 380
  - 450: "चारशे पन्नास" / "साडेचारशे" / "char sau pachas" / "four fifty" = 450
  - 460: "चारशे साठ" / "chaarshey saath" / "char sau saath" / "four sixty" = 460
  - 560: "पाचशे साठ" / "pachshey saath" / "paanch sau saath" / "five sixty" = 560
  - 660: "सहाशे साठ" / "sahashey saath" / "chhe sau saath" / "six sixty" = 660
  - 700: "सातशे" / "satshey" / "saat sau" / "seven hundred" = 700
  - 770: "सातशे सत्तर" / "satshey sattar" / "saat sau sattar" / "seven seventy" = 770
  - 1140: "अकराशे चाळीस" / "akrashe chalis" / "eleven forty" = 1140
  - 1200: "बाराशे" / "barashe" / "barah sau" / "twelve hundred" = 1200
  - 1250: "बाराशे पन्नास" / "barashe pannas" = 1250
  - 1500: "पंधराशे" / "दीड हजार" = 1500
  - "एकशे पस्तीस" = 135
  - "एकशे नव्वद" = 190
  - "एकशे दहा" = 110
  - "पाचशे अडुसष्ट" = 568
  - "सातशे एकोणनव्वद" = 789
  - "पाचशे पन्नास" / "साडेपाचशे" = 550
  - "नऊशे ऐंशी" = 980
  - "साठ" = 60, "पन्नास" = 50, "नव्वद" = 90, "ऐंशी" = 80, "चाळीस" = 40, "तीस" = 30, "वीस" = 20, "दहा" = 10, "पाच" = 5.

4. EXACT NUMBER & PRICING ALIGNMENT:
- Extract the exact numbers spoken.
- "दोन किलो साखर एकशे चाळीस रुपये" -> name: "साखर", quantity: 2, unit: "kg", price: 140
- "एक किलो साखर पाचशे अडुसष्ट रुपये" -> name: "साखर", quantity: 1, unit: "kg", price: 568
- "दोन किलो साखर सातशे एकोणनव्वद रुपये" -> name: "साखर", quantity: 2, unit: "kg", price: 789
- "दोन किलो साखर पाचशे पन्नास रुपये" -> name: "साखर", quantity: 2, unit: "kg", price: 550
- "एकशे दहा रुपयांचे तेल" -> name: "तेल", quantity: 1, unit: "litre", price: 110
- "एकशे आठ रुपयांची साखर" -> name: "साखर", quantity: 1, unit: "packet", price: 108
- "एक किलो सरगम पत्ती चहा ५५० साडेपाचशे रुपये" -> name: "सरगम पत्ती चहा", quantity: 1, unit: "kg", price: 550
- "पाव किलो २५० ग्रॅम सुपर डस्ट ७० सत्तर रुपये" -> name: "सुपर डस्ट चहा", quantity: 250, unit: "gm", price: 70
- "shengdana 85 rupaye" / "शेंगदाणे ८५ रुपये" -> name: "शेंगदाणे", quantity: 1, unit: "packet", price: 85
- "maida 45 rupaye" / "मैदा ४५ रुपये" -> name: "मैदा", quantity: 1, unit: "packet", price: 45
- "rawa 55 rupaye" / "रवा ५५ रुपये" -> name: "रवा", quantity: 1, unit: "packet", price: 55
- "shengdana 95 rupaye" -> name: "शेंगदाणे", quantity: 1, unit: "packet", price: 95
- "maida 25 rupaye" -> name: "मैदा", quantity: 1, unit: "packet", price: 25
- "chaha 98 rupaye" -> name: "चहा", quantity: 1, unit: "packet", price: 98
- "super dust 99 rupaye" -> name: "सुपर डस्ट चहा", quantity: 1, unit: "packet", price: 99
- "sargam 70 rupaye" -> name: "सरगम पत्ती चहा", quantity: 1, unit: "packet", price: 70
- "shengdana 75 rupaye" -> name: "शेंगदाणे", quantity: 1, unit: "packet", price: 75
- "chaha 65 rupaye" -> name: "चहा", quantity: 1, unit: "packet", price: 65
- "rawa 25 rupaye" -> name: "रवा", quantity: 1, unit: "packet", price: 25
- "maida 15 rupaye" -> name: "मैदा", quantity: 1, unit: "packet", price: 15
- "चहा ५५० रुपये" / "चहा five fifty" / "पाचशे पन्नास रुपये चहा" -> name: "चहा", quantity: 1, unit: "packet", price: 550
- "साखर ६५० रुपये" / "sugar six fifty" -> name: "साखर", quantity: 1, unit: "packet", price: 650
- "तेल ७५० रुपये" / "oil seven fifty" -> name: "तेल", quantity: 1, unit: "packet", price: 750
- "तेल ९५० रुपये" / "oil nine fifty" -> name: "तेल", quantity: 1, unit: "packet", price: 950
- "चहा ११० रुपये" / "tea one ten" -> name: "चहा", quantity: 1, unit: "packet", price: 110
- "तेल २५० रुपये" / "dhai sau tel" / "two fifty oil" -> name: "तेल", quantity: 1, unit: "packet", price: 250
- "तेल ३५० रुपये" / "three fifty oil" -> name: "तेल", quantity: 1, unit: "packet", price: 350
- "साखर ४५० रुपये" / "four fifty sugar" -> name: "साखर", quantity: 1, unit: "packet", price: 450
- "अर्धा किलो पोहे तीस रुपये" -> name: "पोहे", quantity: 0.5, unit: "kg", price: 30
- "पाव किलो चहा पन्नास रुपये" -> name: "चहा", quantity: 0.25, unit: "kg", price: 50
- "दीड लिटर तेल दोनशे रुपये" -> name: "तेल", quantity: 1.5, unit: "litre", price: 200
- If quantity is missing use 1 and unit "packet" (or "bottle" for oil). If price is missing use 0.

4b. GRAMS SPECIFICATION (250gm, 500gm, 100gm, grams):
- When user speaks grams (e.g. "250gm", "250 ग्राम", "500gm", "500 ग्राम", "100gm"):
  - Set unit as "gm" and quantity as the spoken gram amount (e.g. 250, 500, 100).
  - NEVER convert 250gm to 0.25 kg, and NEVER convert 500gm to 0.5 kg. Keep unit: "gm".
  - The spoken price is ALWAYS the total price for that packet/quantity!
  - "250gm चहा 110 रुपये" -> name: "चहा", quantity: 250, unit: "gm", price: 110
  - "500gm साखर 30 रुपये" -> name: "साखर", quantity: 500, unit: "gm", price: 30
  - "100gm काजू 85 रुपये" -> name: "काजू", quantity: 100, unit: "gm", price: 85

5. COLLOQUIAL PHONETIC ERROR RECOVERY (MANDATORY):
Fast spoken Marathi Kirana speech often has colloquial accents & STT acoustic mishearings:
- "साकर", "शुकर", "शुगर", "सुकर" -> साखर (Sakhar)
- "माईदा", "मैधा", "माईधा", "मायदा" -> मैदा (Maida)
- "शेंग दानी", "शेंगदानी", "शेंग दाने", "शेंगदाने" -> शेंगदाणे (Shengdane)
- "रवा", "सुजी", "बारीक रवा", "जाडा रवा" -> रवा (Rawa)
- "सर्गं पत्ती", "सर्गप चहा", "सर्कं पत्ती", "चहा पत्ती", "चाय पत्ती" -> चहा (Chaha)
- "सरकी पेंड", "सरकी पेंढ" -> सरकी पेंड (Sarki Pend)
- "मूंगडाल", "मुंग दाल", "मुंगदाल" -> मूग डाळ (Moong Dal)
- "साट" -> 60
- "पणनसरुपई", "पण्नास", "पन्नास रुब्बाई", "पणनस" -> 50
- "एकशिचाईस", "एकशिचारीफ", "एकशेचाईस" -> 140
- "पस्चे पन्नस", "पश्य पन्नास", "फायू हंडरेट फिर्प्टे", "फायू हाढरेट फिर्फिति" -> 550
- "पात्स" -> 5
- "रोपेज", "रुपेज", "रुब्बाई", "रोपई", "रोबइ" -> रुपये
Always reconstruct and extract the genuine kirana item name, quantity, and price!

Return ONLY JSON:
{"transcript": string,
 "items": [{"name": string, "quantity": number, "unit": string, "price": number}]}
One object per item, in the order spoken."""

JSON_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "transcript": {"type": "STRING"},
        "items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "name": {"type": "STRING"},
                    "quantity": {"type": "NUMBER"},
                    "unit": {"type": "STRING"},
                    "price": {"type": "NUMBER"},
                },
                "required": ["name", "quantity", "unit", "price"],
            },
        },
    },
    "required": ["transcript", "items"],
}

# Rich Marathi vocabulary prompt for Whisper speech-to-text accuracy (must be <= 896 chars for Groq)
MARATHI_WHISPER_PROMPT = (
    "मराठी किराणा बिल: साखर, रवा, मैदा, पोहे, गहू, तांदूळ, बासमती, कोलम, शारदातांडूळ, चांदतारा, इंद्रायणी, "
    "तूर डाळ, मूग डाळ, हरभरा डाळ, उडीद डाळ, मसूर डाळ, छोले, राजमा, मटकी, चवळी, गोडेतेल, शेंगदाणा तेल, "
    "सूर्यफूल तेल, फॉर्च्यून, जेमिनी, सोयाबीन, तूप, अमुल, गूळ, मीठ, हळद, जिरे, मोहरी, धने, हिंग, गरम मसाला, "
    "गोडा मसाला, कांदा लसूण मसाला, एव्हरेस्ट, सुहाना, साबण, लक्स, संतूर, डेटॉल, लाईफबॉय, विम बार, रिन, "
    "डिटर्जंट पावडर, सर्फ एक्सेल, टायड, व्हील, घडी, कोलगेट, पॅराशूट, पारले-जी, गुड डे, खारी, टोस्ट, "
    "१ किलो, २ किलो, ५०० ग्रॅम, १ लिटर, १० रुपये, २०, ५०, ६०, ८०, १००, ५००, basmati, colgate, surf excel, tide."
)


def canonicalize_unit(unit: Optional[str]) -> str:
    """Standardizes units to canonical abbreviations."""
    if not unit:
        return "piece"
    u = str(unit).strip().lower()
    if u in ["kg", "kgs", "kilo", "kilos", "kilogram", "kilograms", "किलो", "किग्र", "कि.ग्रा", "शेर"]:
        return "kg"
    if u in ["g", "gm", "gms", "gram", "grams", "ग्रॅम", "ग्राम", "ग्रा", "पावशेर"]:
        return "gm"
    if u in ["l", "ltr", "ltrs", "litre", "litres", "liter", "liters", "लिटर", "लीटर"]:
        return "litre"
    if u in ["ml", "mls", "millilitre", "मिली", "मिलीलिटर"]:
        return "ml"
    if u in ["packet", "packets", "pkt", "pkts", "puda", "pude", "pudi", "पुडा", "पुडे", "पुडी", "पाकीट", "पाकिटे"]:
        return "packet"
    if u in ["box", "boxes", "carton", "cartons", "बॉक्स", "खोके", "खोका", "डबा", "डबे"]:
        return "box"
    if u in ["dozen", "dozens", "डझन", "दर्जन"]:
        return "dozen"
    if u in ["bottle", "bottles", "btl", "बाटली", "बाटल्या"]:
        return "bottle"
    if u in ["tola", "tole", "तोळा", "तोळे"]:
        return "tola"
    if u in ["piece", "pieces", "pcs", "pc", "item", "items", "nag", "पीस", "नग"]:
        return "piece"
    return u


def sanitize_items(raw_items: List[Dict[str, Any]], price_mode: str = "per_unit", language: str = "mr-IN", output_lang: Optional[str] = None) -> List[Dict[str, Any]]:
    """Validates parsed items: name not empty, quantity > 0, price >= 0."""
    if not isinstance(raw_items, list):
        return []

    valid = []
    for item in raw_items:
        if not item or not isinstance(item, dict):
            continue

        raw_name = str(item.get("name") or item.get("item") or "").strip()
        # Strip stray currency/rate/unit tokens that occasionally leak into name
        raw_name = re.sub(
            r"\b(?:\d+(?:\.\d+)?\s*(?:kg|kilo|gm|g|gram|litre|l|ml|packet|box|dozen|pcs|rs|रुपये|रु|रू))\b",
            "",
            raw_name,
            flags=re.IGNORECASE,
        ).strip()

        name = clean_item_name(raw_name) if raw_name else ""
        if not name or re.match(r"^[\d\s.,;+!?-]+$", name):
            name = "Item"

        # Quantity validation
        try:
            quantity = float(item.get("quantity") or item.get("qty") or 1.0)
            if quantity <= 0:
                quantity = 1.0
            elif quantity > 10000:
                quantity = 10000.0
        except (ValueError, TypeError):
            quantity = 1.0

        # Price validation (reject 15000+ or negative)
        try:
            price = float(item.get("price") or item.get("rate") or 0.0)
            if price < 0 or price >= 15000:
                price = 0.0
        except (ValueError, TypeError):
            price = 0.0

        unit = canonicalize_unit(item.get("unit"))
        amount = round(quantity * price, 2)

        # Handle grams (250gm, 500gm, 100gm, etc.)
        if unit in ("g", "gm") and quantity >= 20:
            amount = price
            price = round((price / quantity) * 1000, 2)
        elif price_mode == "line_total" and quantity > 0:
            price = round(price / quantity, 2)
            amount = round(price * quantity, 2)

        valid.append({
            "name": name,
            "quantity": quantity,
            "unit": unit,
            "price": price,
            "amount": amount,
            "spoken_pronunciation": item.get("spoken_pronunciation"),
        })

    return valid


class GeminiProvider:
    """Direct HTTP client for Google Gemini REST API (gemini-2.0-flash / gemini-1.5-flash)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")

    async def parse_audio(self, audio_bytes: bytes, mime_type: str = "audio/mp4", language: str = "mr-IN", price_mode: str = "per_unit", output_lang: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("GEMINI_API_KEY is not set in environment variables")

        normalized_mime = mime_type
        if normalized_mime in ("audio/x-m4a", "audio/m4a", "application/octet-stream"):
            normalized_mime = "audio/mp4"

        base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
        models = ["gemini-2.0-flash", "gemini-1.5-flash"]

        is_english_output = str(output_lang or "").lower().startswith("en")
        lang_prompt = (
            f"{SYSTEM_PROMPT}\nNOTE: User spoke in {language}, BUT wants the final bill items written in simple "
            "PHONETIC ENGLISH matching their exact Marathi spoken words (e.g., 'Sakhar', 'Maida', 'Rawa', 'Shengdane').\nAudio follows."
            if is_english_output
            else f"{SYSTEM_PROMPT}\nUser preferred language hint: {language}. Audio input follows."
        )

        last_error = None
        async with httpx.AsyncClient(timeout=28.0) as client:
            for model in models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"text": lang_prompt},
                                    {
                                        "inlineData": {
                                            "mimeType": normalized_mime,
                                            "data": base64_audio,
                                        }
                                    },
                                ]
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.0,
                            "responseMimeType": "application/json",
                            "responseSchema": JSON_SCHEMA,
                        },
                    }

                    res = await client.post(url, json=payload)
                    if res.status_code != 200:
                        last_error = Exception(f"Gemini API error ({res.status_code}): {res.text}")
                        continue

                    data = res.json()
                    text_response = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
                    if not text_response:
                        continue

                    clean_json = re.sub(r"```(?:json)?|```", "", text_response).strip()
                    parsed = json.loads(clean_json)
                    raw_items = parsed.get("items") or (parsed if isinstance(parsed, list) else [])
                    items = sanitize_items(raw_items, price_mode, language, output_lang)

                    return {
                        "transcript": parsed.get("transcript", ""),
                        "items": items,
                        "provider": "gemini",
                        "model": model,
                    }
                except Exception as e:
                    last_error = e

        raise last_error or Exception("Failed to parse audio with Gemini models")

    async def parse_transcript(self, transcript: str, language: str = "mr-IN", price_mode: str = "per_unit", output_lang: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("GEMINI_API_KEY is not set in environment variables")

        models = ["gemini-2.0-flash", "gemini-1.5-flash"]
        prompt = f"{SYSTEM_PROMPT}\n\nSpoken Transcript: \"{transcript}\"\nLanguage: {language}\nPrice Mode: {price_mode}"

        last_error = None
        async with httpx.AsyncClient(timeout=15.0) as client:
            for model in models:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.api_key}"
                    payload = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.0,
                            "responseMimeType": "application/json",
                        },
                    }

                    res = await client.post(url, json=payload)
                    if res.status_code != 200:
                        last_error = Exception(f"Gemini API error ({res.status_code}): {res.text}")
                        continue

                    data = res.json()
                    text_response = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text")
                    if not text_response:
                        continue

                    clean_json = re.sub(r"```(?:json)?|```", "", text_response).strip()
                    parsed = json.loads(clean_json)
                    raw_items = parsed.get("items") or (parsed if isinstance(parsed, list) else [])
                    items = sanitize_items(raw_items, price_mode, language, output_lang)

                    return {
                        "transcript": transcript,
                        "items": items,
                        "provider": "gemini",
                        "model": model,
                    }
                except Exception as e:
                    last_error = e

        raise last_error or Exception("Failed to parse transcript with Gemini models")


class GroqProvider:
    """Direct HTTP client for Groq Whisper Large v3 Turbo & LLaMA chat completions."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.whisper_url = "https://api.groq.com/openai/v1/audio/transcriptions"
        self.chat_url = "https://api.groq.com/openai/v1/chat/completions"

    async def parse_audio(self, audio_bytes: bytes, mime_type: str = "audio/mp4", language: str = "mr-IN", price_mode: str = "per_unit", output_lang: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("GROQ_API_KEY is not set in environment variables")

        # 1. Transcribe audio with Whisper Large v3 Turbo using rich Marathi Kirana vocabulary prompt
        files = {
            "file": ("audio.m4a", audio_bytes, mime_type),
        }
        data = {
            "model": "whisper-large-v3-turbo",
            "prompt": MARATHI_WHISPER_PROMPT,
            "temperature": "0.0",
        }
        if language:
            data["language"] = language.split("-")[0]

        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=25.0) as client:
            whisper_res = await client.post(self.whisper_url, headers=headers, files=files, data=data)
            if whisper_res.status_code != 200:
                raise Exception(f"Groq Whisper error ({whisper_res.status_code}): {whisper_res.text}")

            whisper_data = whisper_res.json()
            raw_transcript = (whisper_data.get("text") or "").strip()
            if not raw_transcript:
                return {"transcript": "", "items": [], "provider": "groq"}

            # Fast-Path: Instantly run stream-based regex parser (<2ms)
            regex_items = parse_bill_with_regex(raw_transcript, {"priceMode": price_mode, "language": language})
            if regex_items and len(regex_items) > 0:
                print(f"[Groq Fast-Path HIT] Extracted {len(regex_items)} items in 2ms from: \"{raw_transcript}\"")
                return {
                    "transcript": raw_transcript,
                    "items": sanitize_items(regex_items, price_mode, language, output_lang),
                    "provider": "groq-fastpath",
                    "model": "whisper-large-v3-turbo + fastpath",
                }

            # Fallback to Groq Chat LLM
            return await self.parse_transcript(raw_transcript, language, price_mode, output_lang)

    async def parse_transcript(self, transcript: str, language: str = "mr-IN", price_mode: str = "per_unit", output_lang: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("GROQ_API_KEY is not set")

        # Fast-Path check
        regex_items = parse_bill_with_regex(transcript, {"priceMode": price_mode, "language": language})
        if regex_items and len(regex_items) > 0:
            return {
                "transcript": transcript,
                "items": sanitize_items(regex_items, price_mode, language, output_lang),
                "provider": "groq-fastpath",
                "model": "fastpath",
            }

        chat_models = ["llama-3.1-8b-instant", "llama3-70b-8192", "mixtral-8x7b-32768"]
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            for model in chat_models:
                try:
                    payload = {
                        "model": model,
                        "temperature": 0.0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": SYSTEM_PROMPT},
                            {"role": "user", "content": f"Language: {language}. Parse this Kirana order transcript: \"{transcript}\""},
                        ],
                    }

                    res = await client.post(self.chat_url, headers=headers, json=payload)
                    if res.status_code != 200:
                        continue

                    chat_data = res.json()
                    content = chat_data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                    parsed = json.loads(content)
                    raw_list = parsed.get("items") or (parsed if isinstance(parsed, list) else [])
                    items = sanitize_items(raw_list, price_mode, language, output_lang)

                    return {
                        "transcript": parsed.get("transcript") or transcript,
                        "items": items,
                        "provider": "groq",
                        "model": model,
                    }
                except Exception:
                    pass

        # Final fallback to regex items
        return {
            "transcript": transcript,
            "items": regex_items or [],
            "provider": "groq-fallback",
        }


class OpenAIProvider:
    """OpenAI Whisper & GPT-4o-mini provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.whisper_url = "https://api.openai.com/v1/audio/transcriptions"
        self.chat_url = "https://api.openai.com/v1/chat/completions"

    async def parse_audio(self, audio_bytes: bytes, mime_type: str = "audio/mp4", language: str = "mr-IN", price_mode: str = "per_unit", output_lang: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("OPENAI_API_KEY is not set in environment variables")

        files = {"file": ("audio.m4a", audio_bytes, mime_type)}
        data = {
            "model": "whisper-1",
            "prompt": MARATHI_WHISPER_PROMPT,
        }
        if language:
            data["language"] = language.split("-")[0]

        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(self.whisper_url, headers=headers, files=files, data=data)
            if res.status_code != 200:
                raise Exception(f"OpenAI Whisper error: {res.text}")

            transcript = (res.json().get("text") or "").strip()
            regex_items = parse_bill_with_regex(transcript, {"priceMode": price_mode, "language": language})
            if regex_items:
                return {
                    "transcript": transcript,
                    "items": sanitize_items(regex_items, price_mode, language, output_lang),
                    "provider": "openai-fastpath",
                }

            return await self.parse_transcript(transcript, language, price_mode, output_lang)

    async def parse_transcript(self, transcript: str, language: str = "mr-IN", price_mode: str = "per_unit", output_lang: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("OPENAI_API_KEY is not set")

        regex_items = parse_bill_with_regex(transcript, {"priceMode": price_mode, "language": language})
        if regex_items:
            return {
                "transcript": transcript,
                "items": sanitize_items(regex_items, price_mode, language, output_lang),
                "provider": "openai-fastpath",
            }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": "gpt-4o-mini",
            "temperature": 0.0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Parse: \"{transcript}\""},
            ],
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(self.chat_url, headers=headers, json=payload)
            if res.status_code != 200:
                return {"transcript": transcript, "items": regex_items or [], "provider": "openai-fallback"}

            data = res.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            parsed = json.loads(content)
            items = sanitize_items(parsed.get("items") or [], price_mode, language, output_lang)
            return {
                "transcript": transcript,
                "items": items,
                "provider": "openai",
            }


class SarvamProvider:
    """Direct HTTP client for Sarvam AI Saaras STT engine (mr-IN)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SARVAM_API_KEY", "")
        self.stt_url = "https://api.sarvam.ai/speech-to-text"

    async def parse_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/mp4",
        language: str = "mr-IN",
        price_mode: str = "per_unit",
        output_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("SARVAM_API_KEY is not set in environment variables")

        lang_code = "mr-IN"
        if language and "hi" in language.lower():
            lang_code = "hi-IN"
        elif language and "en" in language.lower():
            lang_code = "en-IN"

        files = {
            "file": ("audio.m4a", audio_bytes, mime_type),
        }
        data = {
            "model": "saaras:v4",
            "language_code": lang_code,
            "mode": "codemix",
            "with_diacritics": "false",
        }
        headers = {
            "api-subscription-key": self.api_key,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(self.stt_url, headers=headers, files=files, data=data)
            if res.status_code != 200:
                # Fallback to saaras:v3 if v4 unavailable
                data["model"] = "saaras:v3"
                res = await client.post(self.stt_url, headers=headers, files=files, data=data)
                if res.status_code != 200:
                    raise Exception(f"Sarvam AI error ({res.status_code}): {res.text}")

            result = res.json()
            raw_transcript = (result.get("transcript") or "").strip()
            if not raw_transcript:
                return {"transcript": "", "items": [], "provider": "sarvam"}

            # Fast-path regex parser with Marathi normalizer
            normalized = normalize_voice_transcript(raw_transcript)
            out_l = output_lang or "mr"
            regex_items = parse_bill_with_regex(normalized, {"priceMode": price_mode, "language": language, "outputLang": out_l})
            if regex_items and len(regex_items) > 0:
                print(f"[Sarvam Fast-Path HIT] Extracted {len(regex_items)} items from: \"{raw_transcript}\"")
                return {
                    "transcript": raw_transcript,
                    "items": sanitize_items(regex_items, price_mode, language, out_l),
                    "provider": "sarvam-saaras",
                    "model": "saaras:v4 + fastpath",
                }

            # If fastpath did not get everything, use downstream LLM
            llm_prov = get_llm_provider("anthropic" if os.getenv("ANTHROPIC_API_KEY") else ("groq" if os.getenv("GROQ_API_KEY") else "gemini"))
            llm_res = await llm_prov.parse_transcript(normalized, language, price_mode, out_l)
            llm_res["transcript"] = raw_transcript
            llm_res["provider"] = f"sarvam + {llm_res.get('provider', 'llm')}"
            return llm_res

    async def parse_transcript(
        self,
        transcript: str,
        language: str = "mr-IN",
        price_mode: str = "per_unit",
        output_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        out_l = output_lang or "mr"
        normalized = normalize_voice_transcript(transcript)
        regex_items = parse_bill_with_regex(normalized, {"priceMode": price_mode, "language": language, "outputLang": out_l})
        if regex_items and len(regex_items) > 0:
            return {
                "transcript": transcript,
                "items": sanitize_items(regex_items, price_mode, language, out_l),
                "provider": "sarvam-fastpath",
                "model": "fastpath",
            }
        llm_prov = get_llm_provider("anthropic" if os.getenv("ANTHROPIC_API_KEY") else ("groq" if os.getenv("GROQ_API_KEY") else "gemini"))
        return await llm_prov.parse_transcript(normalized, language, price_mode, out_l)


class AnthropicProvider:
    """Direct HTTP client for Anthropic Claude (Claude 3.5 Haiku / Sonnet)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.messages_url = "https://api.anthropic.com/v1/messages"

    async def parse_audio(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/mp4",
        language: str = "mr-IN",
        price_mode: str = "per_unit",
        output_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Claude is text-only; transcribe first using Sarvam/Groq/Gemini
        stt = None
        if os.getenv("SARVAM_API_KEY"):
            stt = SarvamProvider()
        elif os.getenv("GROQ_API_KEY"):
            stt = GroqProvider()
        else:
            stt = GeminiProvider()
        stt_res = await stt.parse_audio(audio_bytes, mime_type, language, price_mode, output_lang)
        transcript = stt_res.get("transcript", "")
        if not transcript:
            return {"transcript": "", "items": [], "provider": "anthropic"}
        claude_res = await self.parse_transcript(transcript, language, price_mode, output_lang)
        claude_res["transcript"] = transcript
        return claude_res

    async def parse_transcript(
        self,
        transcript: str,
        language: str = "mr-IN",
        price_mode: str = "per_unit",
        output_lang: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            raise Exception("ANTHROPIC_API_KEY is not set")

        out_l = output_lang or "mr"
        normalized = normalize_voice_transcript(transcript)
        regex_items = parse_bill_with_regex(normalized, {"priceMode": price_mode, "language": language, "outputLang": out_l})
        if regex_items and len(regex_items) > 0:
            return {
                "transcript": transcript,
                "items": sanitize_items(regex_items, price_mode, language, out_l),
                "provider": "anthropic-fastpath",
                "model": "fastpath",
            }

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 1500,
            "temperature": 0.0,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": f"Language: {language}. Output Language: {out_l}. Parse this Kirana transcript into JSON items: \"{normalized}\"",
                }
            ],
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(self.messages_url, headers=headers, json=payload)
            if res.status_code != 200:
                raise Exception(f"Anthropic error ({res.status_code}): {res.text}")

            data = res.json()
            content = data.get("content", [{}])[0].get("text", "{}").strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("\n", 1)[0].strip()

            parsed = json.loads(content)
            raw_list = parsed.get("items") or (parsed if isinstance(parsed, list) else [])
            items = sanitize_items(raw_list, price_mode, language, out_l)
            return {
                "transcript": transcript,
                "items": items,
                "provider": "anthropic",
                "model": "claude-3-5-haiku",
            }


async def gemini_transcribe(audio_bytes: bytes, mime_type: str = "audio/mp4", language: str = "mr-IN") -> str:
    """Gemini speech-to-text only (audio -> transcript text)."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    if not api_key:
        raise Exception("GEMINI_API_KEY is not set")

    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")
    models = ["gemini-2.0-flash", "gemini-1.5-flash"]

    async with httpx.AsyncClient(timeout=25.0) as client:
        for model in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{
                        "parts": [
                            {"text": f"Transcribe the following audio exactly as spoken. Language hint: {language}. Output ONLY the transcribed text — no JSON, no formatting, no explanation."},
                            {"inlineData": {"mimeType": mime_type, "data": base64_audio}},
                        ]
                    }],
                    "generationConfig": {"temperature": 0.0},
                }
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    return text.strip()
            except Exception:
                pass
    return ""


def get_llm_provider(provider_name: Optional[str] = None):
    """
    Service Factory matching getLLMProvider:
    Prioritizes Sarvam -> Anthropic -> Groq -> OpenAI -> Gemini.
    """
    p = (provider_name or os.getenv("LLM_PROVIDER") or ("sarvam" if os.getenv("SARVAM_API_KEY") else ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else ("groq" if os.getenv("GROQ_API_KEY") else ("openai" if os.getenv("OPENAI_API_KEY") else "gemini"))))).lower()
    if p == "sarvam":
        return SarvamProvider()
    if p == "anthropic":
        return AnthropicProvider()
    if p == "groq":
        return GroqProvider()
    if p == "openai":
        return OpenAIProvider()
    if p == "gemini":
        return GeminiProvider()
    if os.getenv("SARVAM_API_KEY"):
        return SarvamProvider()
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicProvider()
    if os.getenv("GROQ_API_KEY"):
        return GroqProvider()
    return OpenAIProvider() if os.getenv("OPENAI_API_KEY") else GeminiProvider()

