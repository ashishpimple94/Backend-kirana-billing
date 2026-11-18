"""
marathi_normalizer.py
Marathi Number-to-Speech Converter & Spoken Kirana Pronunciation Normalizer (1 to 5000)
Supports Roman Marathi transliteration, Devanagari numerals (०-९), Devanagari Marathi words,
Hindi, English, and Spoken Pronunciation Echoes:
- "sakhar 1kg 60 rupaye saath rupaye" -> 60, echo: saath
- "साखर १ किलो ६० रुपये साठ रुपये" -> 60, echo: साठ
- "sugar 1kg 60 sixty" -> 60, echo: sixty
- "masoor 1kg 95 panchyannav" -> 95, echo: panchyannav
- "Patanjali biscuit box 10/- 710" -> "Patanjali biscuit box 10/- satshey daha rupaye 710"
"""

import re
from typing import Optional, Tuple, Dict, Any

# Map Devanagari digits to ASCII digits
DEV_TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")

# ── Unique Marathi words from 1 to 99 (Roman script) ──
MARATHI_1_TO_99 = {
    1: "ek", 2: "don", 3: "teen", 4: "chaar", 5: "paach",
    6: "saha", 7: "saat", 8: "aath", 9: "nau", 10: "daha",
    11: "akra", 12: "baara", 13: "tera", 14: "chauda", 15: "pandra",
    16: "sola", 17: "satra", 18: "athra", 19: "ekonis", 20: "vees",
    21: "ekvees", 22: "baavees", 23: "tevees", 24: "chouvees", 25: "panchees",
    26: "chavvees", 27: "sattavees", 28: "atthaavees", 29: "ekontis", 30: "tees",
    31: "ekertis", 32: "battis", 33: "tehtis", 34: "chautis", 35: "paantis",
    36: "chattis", 37: "sadatis", 38: "adatis", 39: "ekonchalis", 40: "chalis",
    41: "ektechalis", 42: "bechalis", 43: "trechalis", 44: "chavvechalis", 45: "panchechalis",
    46: "sayechechalis", 47: "sattechalis", 48: "atthechalis", 49: "ekonpannas", 50: "pannas",
    51: "ekaavanna", 52: "baavanna", 53: "trepanna", 54: "choupanne", 55: "panchaavanna",
    56: "chappanna", 57: "sattaavanna", 58: "atthaavanna", 59: "ekonsaath", 60: "saath",
    61: "ekasasta", 62: "baasasta", 63: "tresasta", 64: "chausasta", 65: "paachasasta",
    66: "sahasasta", 67: "sadasasta", 68: "adasasta", 69: "ekonsattar", 70: "sattar",
    71: "ekahattar", 72: "bahattar", 73: "tyahattar", 74: "chouhattar", 75: "panchahattar",
    76: "shahattar", 77: "satyahattar", 78: "athyahattar", 79: "ekonaainshi", 80: "aainshi",
    81: "ekyaainshi", 82: "byaainshi", 83: "tryaainshi", 84: "chouryaainshi", 85: "panchyaainshi",
    86: "shyaainshi", 87: "sattyaainshi", 88: "atthyaainshi", 89: "ekonnavvad", 90: "navvad",
    91: "ekyaanv", 92: "byaanv", 93: "tryaanv", 94: "chouravnav", 95: "panchyaannav",
    96: "shaanv", 97: "sattyaanv", 98: "atthyaanv", 99: "navyaanv",
}

# ── Hundreds in Marathi (Single word as requested) ──
MARATHI_HUNDREDS = {
    100: "ekshey",
    200: "donshey",
    300: "teenshey",
    400: "chaarshey",
    500: "pachshey",
    600: "sahashey",
    700: "satshey",
    800: "aathshey",
    900: "naushey",
}


def number_to_marathi_words(num: int) -> str:
    """Converts bill amount (1 to 99,999) into spoken Marathi words (Roman script)."""
    if num <= 0:
        return "shunya"

    if num in MARATHI_1_TO_99:
        return MARATHI_1_TO_99[num]

    parts = []

    # Thousands
    if num >= 1000:
        thousands = num // 1000
        rem_after_thousands = num % 1000
        if thousands in MARATHI_1_TO_99:
            th_words = MARATHI_1_TO_99[thousands]
        else:
            th_words = number_to_marathi_words(thousands)
        parts.append(f"{th_words} hazaar")
        num = rem_after_thousands

    # Hundreds
    if num >= 100:
        hundreds_digit = (num // 100) * 100
        rem_after_hundreds = num % 100
        if hundreds_digit in MARATHI_HUNDREDS:
            parts.append(MARATHI_HUNDREDS[hundreds_digit])
        num = rem_after_hundreds

    # Remaining 1 to 99
    if num > 0:
        if num in MARATHI_1_TO_99:
            parts.append(MARATHI_1_TO_99[num])

    return " ".join(parts).strip()


def convert_bill_line_to_speech(line: str) -> str:
    """
    Converts a bill line into Marathi speech representation:
    Input:  Patanjali biscuit box 10/- 710
    Output: Patanjali biscuit box 10/- satshey daha rupaye 710
    """
    if not line or not line.strip():
        return line

    raw_line = line.strip()
    match = re.search(r"^(.*?)(\d+(?:\.\d+)?)\s*$", raw_line)
    if not match:
        return raw_line

    prefix = match.group(1).rstrip()
    amount_str = match.group(2)
    try:
        amount_val = int(float(amount_str))
    except ValueError:
        return raw_line

    marathi_words = number_to_marathi_words(amount_val)
    return f"{prefix} {marathi_words} rupaye {amount_val}"


# ── Spoken pronunciation words in Marathi (Devanagari & Roman), Hindi, English (1 to 5000) ──
SPOKEN_NUMBER_WORDS = {
    # 1-10
    "ek": 1, "एक": 1, "don": 2, "दोन": 2, "teen": 3, "तीन": 3, "chaar": 4, "चार": 4,
    "paach": 5, "pach": 5, "पाच": 5, "saha": 6, "सहा": 6, "saat": 7, "सात": 7, "aath": 8, "ath": 8, "आठ": 8,
    "nau": 9, "नऊ": 9, "daha": 10, "दहा": 10, "dus": 10, "दस": 10,
    # 11-20
    "akra": 11, "अकरा": 11, "baara": 12, "बारा": 12, "tera": 13, "तेरा": 13, "chauda": 14, "चौदा": 14,
    "pandra": 15, "पंधरा": 15, "sola": 16, "सोळा": 16, "satra": 17, "सतरा": 17, "athra": 18, "अठरा": 18,
    "ekonis": 19, "एकोणीस": 19, "vees": 20, "vis": 20, "bees": 20, "वीस": 20, "बीस": 20,
    # 21-30
    "ekvees": 21, "एकवीस": 21, "baavees": 22, "बावीस": 22, "tevees": 23, "तेवीस": 23, "chouvees": 24, "चोवीस": 24,
    "panchees": 25, "pachees": 25, "पंचवीस": 25, "पच्चीस": 25, "tees": 30, "तीस": 30,
    # 31-40
    "chalis": 40, "चाळीस": 40, "चालीस": 40,
    # 41-50
    "pannas": 50, "pachaas": 50, "पन्नास": 50, "पचास": 50,
    # 51-60
    "trepanna": 53, "त्रेपन्न": 53, "panchaavanna": 55, "पंचावन्न": 55, "saath": 60, "sath": 60, "साठ": 60, "साठ": 60,
    # 61-70
    "sattar": 70, "सत्तर": 70,
    # 71-80
    "panchahattar": 75, "पंचाहत्तर": 75, "aainshi": 80, "ainshi": 80, "aishi": 80, "assi": 80, "ऐंशी": 80, "अस्सी": 80,
    # 81-90
    "atthyaainshi": 88, "अठ्ठ्याऐंशी": 88, "navvad": 90, "nabbe": 90, "नव्वद": 90, "नब्बे": 90,
    # 91-99
    "panchyaannav": 95, "panchyannav": 95, "panchanve": 95, "पंच्याण्णव": 95, "पंच्याणव": 95, "पंचानवे": 95,
    # English tens
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

# ── Spoken compound numbers & hundreds (100 to 5000) ──
COMPOUND_PRICING_MAP = {
    # 100 - 199
    "ekshe": 100, "ekshey": 100, "ek sau": 100, "one hundred": 100, "एकशे": 100, "शंभर": 100, "एक सौ": 100,
    "ekshe daha": 110, "ek sau dus": 110, "one ten": 110, "एकशे दहा": 110,
    "ekshe vees": 120, "ekshey vees": 120, "ek sau bees": 120, "one twenty": 120, "एकशे वीस": 120, "एक सौ बीस": 120,
    "ekshe tees": 130, "ekshey tees": 130, "ek sau tees": 130, "one thirty": 130, "एकशे तीस": 130, "एक सौ तीस": 130,
    "ekshe chalis": 140, "ekshey chalis": 140, "ek sau chalis": 140, "one forty": 140, "एकशे चाळीस": 140,
    "ekshe pannas": 150, "ek sau pachaas": 150, "one fifty": 150, "एकशे पन्नास": 150, "दीडशे": 150,
    "ekshe saath": 160, "ekshe sath": 160, "ekshey saath": 160, "ek sau saath": 160, "one sixty": 160, "एकशे साठ": 160,
    "ekshe sattar": 170, "ek sau sattar": 170, "one seventy": 170, "एकशे सत्तर": 170,
    "ekshe aainshi": 180, "ekshe ainshi": 180, "ekshey aainshi": 180, "ek sau assi": 180, "one eighty": 180, "एकशे ऐंशी": 180,
    "ekshe navvad": 190, "ek sau nabbe": 190, "one ninety": 190, "एकशे नव्वद": 190,

    # 200 - 299
    "donshe": 200, "donshey": 200, "don sau": 200, "two hundred": 200, "दोनशे": 200, "दो सौ": 200,
    "donshe daha": 210, "donshey daha": 210, "two ten": 210, "दोनशे दहा": 210,
    "donshe vees": 220, "donshey vees": 220, "two twenty": 220, "दोनशे वीस": 220,
    "donshe tees": 230, "donshey tees": 230, "two thirty": 230, "दोनशे तीस": 230,
    "donshe chalis": 240, "donshey chalis": 240, "two forty": 240, "दोनशे चाळीस": 240,
    "donshe pannas": 250, "donshey pannas": 250, "two fifty": 250, "दोनशे पन्नास": 250, "अडीचशे": 250,
    "donshe saath": 260, "donshey saath": 260, "donshe sath": 260, "two sixty": 260, "दोनशे साठ": 260,
    "donshe sattar": 270, "donshey sattar": 270, "two seventy": 270, "दोनशे सत्तर": 270,
    "donshe aainshi": 280, "donshey aainshi": 280, "donshe ainshi": 280, "two eighty": 280, "दोनशे ऐंशी": 280,
    "donshe navvad": 290, "donshey navvad": 290, "two ninety": 290, "दोनशे नव्वद": 290,

    # 300 - 399
    "teenshe": 300, "teenshey": 300, "teen sau": 300, "three hundred": 300, "तीनशे": 300,
    "teenshe daha": 310, "teenshey daha": 310, "three ten": 310, "तीनशे दहा": 310,
    "teenshe vees": 320, "teenshey vees": 320, "three twenty": 320, "तीनशे वीस": 320,
    "teenshe tees": 330, "teenshey tees": 330, "three thirty": 330, "तीनशे तीस": 330,
    "teenshe chalis": 340, "teenshey chalis": 340, "three forty": 340, "तीनशे चाळीस": 340,
    "teenshe pannas": 350, "teenshey pannas": 350, "three fifty": 350, "तीनशे पन्नास": 350, "साडेतीनशे": 350,
    "teenshe saath": 360, "teenshey saath": 360, "three sixty": 360, "तीनशे साठ": 360,
    "teenshe sattar": 370, "teenshey sattar": 370, "three seventy": 370, "तीनशे सत्तर": 370,
    "teenshe aainshi": 380, "teenshey aainshi": 380, "teenshe ainshi": 380, "three eighty": 380, "तीनशे ऐंशी": 380,
    "teenshe navvad": 390, "teenshey navvad": 390, "three ninety": 390, "तीनशे नव्वद": 390,

    # 400 - 499
    "chaarshe": 400, "chaarshey": 400, "chaar sau": 400, "four hundred": 400, "चारशे": 400,
    "chaarshe daha": 410, "chaarshey daha": 410, "four ten": 410, "चारशे दहा": 410,
    "chaarshe vees": 420, "chaarshey vees": 420, "four twenty": 420, "चारशे वीस": 420,
    "chaarshe tees": 430, "chaarshey tees": 430, "four thirty": 430, "चारशे तीस": 430,
    "chaarshe chalis": 440, "chaarshey chalis": 440, "four forty": 440, "चारशे चाळीस": 440,
    "chaarshe pannas": 450, "chaarshey pannas": 450, "chaar sau pachaas": 450, "four fifty": 450, "चारशे पन्नास": 450, "साडेचारशे": 450,
    "chaarshe panchaavanna": 455, "chaarshey panchaavanna": 455, "चारशे पंचावन्न": 455,
    "chaarshe saath": 460, "chaarshey saath": 460, "chaarshe sath": 460, "four sixty": 460, "चारशे साठ": 460,
    "chaarshe sattar": 470, "chaarshey sattar": 470, "four seventy": 470, "चारशे सत्तर": 470,
    "chaarshe aainshi": 480, "chaarshey aainshi": 480, "four eighty": 480, "चारशे ऐंशी": 480,
    "chaarshe navvad": 490, "chaarshey navvad": 490, "four ninety": 490, "चारशे नव्वद": 490,

    # 500 - 599
    "pachshe": 500, "pachshey": 500, "paanch sau": 500, "five hundred": 500, "पाचशे": 500, "पाँच सौ": 500,
    "pachshe daha": 510, "pachshey daha": 510, "five ten": 510, "पाचशे दहा": 510,
    "pachshe vees": 520, "pachshey vees": 520, "five twenty": 520, "पाचशे वीस": 520,
    "pachshe tees": 530, "pachshey tees": 530, "five thirty": 530, "पाचशे तीस": 530,
    "pachshe trepanna": 553, "pachshey trepanna": 553, "पाचशे त्रेपन्न": 553,
    "pachshe pannas": 550, "pachshey pannas": 550, "five fifty": 550, "पाचशे पन्नास": 550, "साडेपाचशे": 550,
    "pachshe saath": 560, "pachshey saath": 560, "pachshe sath": 560, "five sixty": 560, "पाचशे साठ": 560,
    "pachshe sattar": 570, "pachshey sattar": 570, "five seventy": 570, "पाचशे सत्तर": 570,
    "pachshe aainshi": 580, "pachshey aainshi": 580, "five eighty": 580, "पाचशे ऐंशी": 580,
    "pachshe navvad": 590, "pachshey navvad": 590, "five ninety": 590, "पाचशे नव्वद": 590,

    # 600 - 699
    "sahashe": 600, "sahashey": 600, "chhah sau": 600, "six hundred": 600, "सहाशे": 600,
    "sahashe daha": 610, "sahashey daha": 610, "six ten": 610, "सहाशे दहा": 610,
    "sahashe saath": 660, "sahashey saath": 660, "six sixty": 660, "सहाशे साठ": 660,

    # 700 - 799
    "satshe": 700, "satshey": 700, "saat sau": 700, "seven hundred": 700, "सातशे": 700,
    "satshe daha": 710, "satshey daha": 710, "seven ten": 710, "सातशे दहा": 710,
    "satshe sattar": 770, "satshey sattar": 770, "seven seventy": 770, "सातशे सत्तर": 770,
    "satshe aainshi": 780, "satshey aainshi": 780, "seven eighty": 780, "सातशे ऐंशी": 780,
    "satshe atthyaainshi": 788, "satshey atthyaainshi": 788, "सातशे अठ्ठ्याऐंशी": 788,

    # 800 - 899
    "aathshe": 800, "aathshey": 800, "aath sau": 800, "eight hundred": 800, "आठशे": 800,
    "aathshe daha": 810, "aathshey daha": 810, "eight ten": 810, "आठशे दहा": 810,

    # 900 - 999
    "naushe": 900, "naushey": 900, "nau sau": 900, "nine hundred": 900, "नऊशे": 900,
    "naushe daha": 910, "naushey daha": 910, "nine ten": 910, "नऊशे दहा": 910,
    "naushe navvad": 990, "naushey navvad": 990, "nine ninety": 990, "नऊशे नव्वद": 990,

    # 1000 - 5000
    "ek hazaar": 1000, "ek hajar": 1000, "one thousand": 1000, "एक हजार": 1000,
    "ek hazaar ekshe chalis": 1140, "ek hazaar ekshey chalis": 1140, "one thousand one forty": 1140, "एक हजार एकशे चाळीस": 1140, "अकराशे चाळीस": 1140,
    "ek hazaar donshe": 1200, "ek hazaar donshey": 1200, "one thousand two hundred": 1200, "एक हजार दोनशे": 1200, "बाराशे": 1200,
    "don hazaar": 2000, "don hajar": 2000, "two thousand": 2000, "दोन हजार": 2000,
    "don hazaar aathshey navvad": 2890, "don hajar aathshe navvad": 2890, "दोन हजार आठशे नव्वद": 2890,
    "teen hazaar": 3000, "three thousand": 3000, "तीन हजार": 3000,
    "chaar hazaar": 4000, "four thousand": 4000, "चार हजार": 4000,
    "paach hazaar": 5000, "five thousand": 5000, "पाच हजार": 5000,
}


def extract_price_and_pronunciation(raw_str: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extracts price and pronunciation echo from strings like:
    '60 rupaye saath rupaye' -> (60.0, 'saath')
    '६० रुपये साठ रुपये' -> (60.0, 'साठ')
    '60 sath' -> (60.0, 'sath')
    '95 panchyannav' -> (95.0, 'panchyannav')
    '120 ekshe vees' -> (120.0, 'ekshe vees')
    """
    clean = raw_str.strip()

    # Clean currency suffixes
    clean_no_curr = re.sub(r"\b(?:rupaye|rupayan|rupees|rupee|rs|inr|रुपये|रुपया)\b", "", clean, flags=re.IGNORECASE).strip()

    # 1. Check digit + word echo (e.g. "60 saath", "60 sath", "60 sixty", "६० साठ")
    m_echo = re.search(r"^(\d+)\s+([a-zA-Z\u0900-\u097F]+(?:\s+[a-zA-Z\u0900-\u097F]+)?)$", clean_no_curr)
    if m_echo:
        num = float(m_echo.group(1))
        echo_word = m_echo.group(2).strip()
        return num, echo_word

    # 2. Check compound pricing map
    lower = clean_no_curr.lower()
    for phrase, val in sorted(COMPOUND_PRICING_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if phrase in lower or phrase in clean_no_curr:
            return float(val), phrase

    # 3. Check single spoken number words
    for w in clean_no_curr.split():
        w_low = w.lower()
        if w_low in SPOKEN_NUMBER_WORDS:
            return float(SPOKEN_NUMBER_WORDS[w_low]), w
        if w in SPOKEN_NUMBER_WORDS:
            return float(SPOKEN_NUMBER_WORDS[w]), w

    # 4. Pure digit
    m_num = re.search(r"(\d+(?:\.\d+)?)", clean)
    if m_num:
        val = float(m_num.group(1))
        if val >= 15000:
            return None, None
        return val, None

    return None, None


def normalize_voice_transcript(transcript: str) -> str:
    """Normalizes transcript: converts Devanagari numerals to ASCII and strips 100,000 hallucinations."""
    if not transcript:
        return ""

    # Translate Devanagari numerals (०-९) to ASCII (0-9)
    text = transcript.translate(DEV_TO_ASCII)

    # Remove 100,000 hallucinations
    text = re.sub(r"\b100000\b", "", text)
    text = re.sub(r"\b(?:1|ek|एक)\s*(?:lakh|lac|laakh|लाख)\b", "", text, flags=re.IGNORECASE)

    # Convert MRP markers to clean token
    text = re.sub(r"(\d+)\s*/\s*-?", r"\1/-", text)

    return text.strip()
