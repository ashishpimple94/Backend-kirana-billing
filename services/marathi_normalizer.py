"""
marathi_normalizer.py
Comprehensive Marathi Kirana Normalizer & Multilingual Dictionary.
Direct 1-to-1 Python conversion of services/marathiNormalizer.js.
Supports:
- Spoken number conversion (1 to 5000) across Marathi, Hindi, English
- Compound hundreds (एकशे चाळीस -> 140, साडेपाचशे -> 550, two fifty -> 250)
- Pronunciation echo handling (60 rupaye saath rupaye -> 60, echo: saath)
- Roman Marathi number-to-words for counter voice
- Unit canonicalization and ungluing (एककिलो -> 1 kg, पावकिलो -> 250 gm)
- Item canonicalization (Sakhar -> साखर, Shengdane -> शेंगदाणे)
- Hallucination rejection (strictly 1 to 5000, rejects 100000)
"""

import re
import difflib
from typing import Optional, Tuple, Dict, Any, List

# 0. Deduplicate repeated speech tokens or acoustic stutters (e.g. sakhar-sakhar -> sakhar, साखर-साखर -> साखर)
def deduplicate_spoken_tokens(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()
    s = re.sub(
        r"(?:^|(?<=[^\u0900-\u097Fa-zA-Z]))([\u0900-\u097Fa-zA-Z]+)(?:[-\s]+\1)+(?=[^\u0900-\u097Fa-zA-Z]|$)",
        r"\1",
        s,
        flags=re.IGNORECASE,
    )
    return s.strip()


# Convert Gujarati or other misidentified Indic scripts to Devanagari Marathi script.
def convert_indic_script_to_devanagari(text: str) -> str:
    if not text or not isinstance(text, str):
        return ""
    res = []
    for ch in text:
        code = ord(ch)
        if 0x0A80 <= code <= 0x0AFF:
            dev_code = code - 0x180
            if 0x0900 <= dev_code <= 0x097F:
                res.append(chr(dev_code))
                continue
        res.append(ch)
    return "".join(res)


# Devanagari Digits
DEV_TO_ASCII = str.maketrans("०१२३४५६७८९", "0123456789")
DEVANAGARI_DIGITS = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}


def make_unicode_regex(pattern_str: str, flags=re.IGNORECASE):
    return re.compile(
        rf"(?:^|(?<=[^\u0900-\u097Fa-zA-Z0-9]))(?:{pattern_str})(?=[^\u0900-\u097Fa-zA-Z0-9]|$)",
        flags,
    )


# Multipliers for Thousands (हजार / hajar / hazar)
THOUSAND_MULTIPLIERS = {
    # Devanagari
    "एक": 1, "दोन": 2, "दो": 2, "तीन": 3, "चार": 4, "पाच": 5, "पाँच": 5, "पांच": 5,
    "सहा": 6, "सात": 7, "आठ": 8, "नऊ": 9, "नौ": 9, "दहा": 10, "दस": 10,
    "अकरा": 11, "बारा": 12, "तेरा": 13, "चौदा": 14, "पंधरा": 15, "सोळा": 16, "सतरा": 17, "अठरा": 18, "एकोणीस": 19,
    "वीस": 20, "बीस": 20, "पंचवीस": 25, "तीस": 30, "पस्तीस": 35, "चाळीस": 40, "चालीस": 40, "पन्नास": 50, "पचास": 50,
    "साठ": 60, "सत्तर": 70, "ऐंशी": 80, "नव्वद": 90, "शंभर": 100,
    "दीड": 1.5, "अडीच": 2.5, "साडेतीन": 3.5, "साडेचार": 4.5, "साडेपाच": 5.5,
    "सव्वा": 1.25, "पाऊण": 0.75,

    # English & Transliterated
    "ek": 1, "don": 2, "do": 2, "teen": 3, "tin": 3, "char": 4, "chaar": 4,
    "panch": 5, "paach": 5, "pach": 5, "saha": 6, "chha": 6, "chheh": 6,
    "sat": 7, "saat": 7, "ath": 8, "aath": 8, "nau": 9, "nav": 9, "daha": 10, "das": 10,
    "akara": 11, "bara": 12, "tera": 13, "chauda": 14, "pandhra": 15, "sola": 16, "satra": 17, "athra": 18, "ekonis": 19,
    "vees": 20, "bees": 20, "panchvis": 25, "tees": 30, "tis": 30, "pastis": 35, "paintis": 35,
    "chalis": 40, "chaalis": 40, "pannas": 50, "pachas": 50, "saath": 60, "sath": 60, "sattar": 70,
    "aishi": 80, "ayshi": 80, "assi": 80, "ainshi": 80, "aenshi": 80, "navvad": 90, "nabbe": 90,
    "deed": 1.5, "dedh": 1.5, "adeech": 2.5, "dhai": 2.5,
    "sade teen": 3.5, "sade char": 4.5, "sade paach": 5.5, "sade pach": 5.5,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30, "forty": 40, "fifty": 50,
}

MARATHI_UNITS_1_TO_99 = {
    1: "ek", 2: "don", 3: "teen", 4: "chaar", 5: "paach", 6: "saha", 7: "saat", 8: "aath", 9: "nau", 10: "daha",
    11: "akara", 12: "baara", 13: "tera", 14: "chauda", 15: "pandhra", 16: "sola", 17: "satra", 18: "athra", 19: "ekonis",
    20: "vees", 21: "ekvees", 22: "baavees", 23: "tevees", 24: "chovees", 25: "panchvees", 26: "savvees", 27: "sattavees", 28: "atthaavees", 29: "ekontees",
    30: "tees", 31: "ektees", 32: "battees", 33: "tehtees", 34: "chautees", 35: "pastees", 36: "chhattees", 37: "sadtees", 38: "adtees", 39: "ekonchalis",
    40: "chalis", 41: "ekechalis", 42: "bechalis", 43: "trechalis", 44: "chavvechalis", 45: "panchechalis", 46: "shehechalis", 47: "sattechalis", 48: "atthechalis", 49: "ekonpannas",
    50: "pannas", 51: "ekaavanna", 52: "baavanna", 53: "trepanna", 54: "chopanna", 55: "panchaavanna", 56: "chhappanna", 57: "sattaavanna", 58: "atthaavanna", 59: "ekonsaath",
    60: "saath", 61: "eksashta", 62: "baasashta", 63: "tresashta", 64: "chausashta", 65: "paasashta", 66: "shaasashta", 67: "sadsashta", 68: "adushta", 69: "ekonsattar",
    70: "sattar", 71: "ekaahattar", 72: "bahaattar", 73: "tryaahattar", 74: "chauryaahattar", 75: "panchaahattar", 76: "shahaattar", 77: "satyaahattar", 78: "atthaahattar", 79: "ekonaainshi",
    80: "aainshi", 81: "ekyaainshi", 82: "byaainshi", 83: "tryaainshi", 84: "chauryaainshi", 85: "panchyaainshi", 86: "shahaainshi", 87: "satyaainshi", 88: "atthyaainshi", 89: "ekonnavvad",
    90: "navvad", 91: "ekyaannav", 92: "byaannav", 93: "tryaannav", 94: "chauryaannav", 95: "panchyaannav", 96: "shahaannav", 97: "satyaannav", 98: "atthyaannav", 99: "navvyaannav"
}

MARATHI_HUNDREDS_WORDS = {
    100: "ekshey", 200: "donshey", 300: "teenshey", 400: "chaarshey", 500: "pachshey",
    600: "sahashey", 700: "satshey", 800: "aathshey", 900: "naushey"
}


def number_to_marathi_words(n: int) -> str:
    """Converts a number into Roman Marathi words (e.g. 710 -> satshey daha)."""
    if n <= 0:
        return "shunya"
    if n <= 99:
        return MARATHI_UNITS_1_TO_99.get(n, str(n))

    parts = []
    rem = n

    if rem >= 1000:
        thou = rem // 1000
        rem = rem % 1000
        thou_word = MARATHI_UNITS_1_TO_99.get(thou, str(thou))
        parts.append(f"{thou_word} hazaar")

    if rem >= 100:
        hund = (rem // 100) * 100
        rem = rem % 100
        if hund in MARATHI_HUNDREDS_WORDS:
            parts.append(MARATHI_HUNDREDS_WORDS[hund])

    if rem > 0:
        if rem in MARATHI_UNITS_1_TO_99:
            parts.append(MARATHI_UNITS_1_TO_99[rem])

    return " ".join(parts)


def convert_bill_line_to_speech(line: str) -> str:
    """
    Converts a bill line into Marathi speech representation:
    Input:  Patanjali biscuit box 10/- 710
    Output: Patanjali biscuit box 10/- satshey daha rupaye 710
    """
    if not line or not isinstance(line, str):
        return ""
    trimmed = line.strip()
    match = re.search(r"^(.*?)(?:(\d+\s*/-)\s+)?(\d+)$", trimmed)
    if not match:
        return trimmed
    prefix = (match.group(1) or "").strip()
    mrp = match.group(2).strip() if match.group(2) else ""
    amount = int(match.group(3))
    words = number_to_marathi_words(amount)
    parts = []
    if prefix:
        parts.append(prefix)
    if mrp:
        parts.append(mrp)
    parts.append(f"{words} rupaye {amount}")
    return " ".join(parts)


# 2. Comprehensive Marathi & Indian Number Words
HUNDREDS_MAP = {
    # English Colloquial Hundreds
    "one twenty": 120, "one-twenty": 120, "one hundred twenty": 120,
    "one thirty": 130, "one-thirty": 130, "one hundred thirty": 130,
    "one forty": 140, "one-forty": 140, "one hundred forty": 140,
    "one fifty": 150, "one-fifty": 150, "one hundred fifty": 150,
    "one sixty": 160, "one-sixty": 160, "one hundred sixty": 160,
    "one seventy": 170, "one-seventy": 170,
    "one eighty": 180, "one-eighty": 180,
    "one ninety": 190, "one-ninety": 190,

    "two twenty": 220, "two thirty": 230, "two forty": 240, "two fifty": 250,
    "two sixty": 260, "two seventy": 270, "two eighty": 280, "two ninety": 290,

    "three twenty": 320, "three thirty": 330, "three forty": 340, "three fifty": 350,
    "three sixty": 360, "three seventy": 370, "three eighty": 380, "three ninety": 390,

    "four twenty": 420, "four thirty": 430, "four forty": 440, "four fifty": 450,
    "four sixty": 460, "four seventy": 470, "four eighty": 480, "four ninety": 490,

    "five twenty": 520, "five thirty": 530, "five forty": 540, "five fifty": 550,
    "five sixty": 560, "five seventy": 570, "five eighty": 580, "five ninety": 590,

    "six sixty": 660, "seven seventy": 770, "eight eighty": 880, "nine ninety": 990,
    "eleven forty": 1140, "twelve hundred": 1200, "fifteen hundred": 1500,

    # 135 Compounds
    "एकशे पस्तीस": 135, "एकशेपस्तीस": 135, "एकसे पस्तीस": 135, "ekshe pastis": 135, "ekse pastis": 135, "one thirty five": 135,

    # 140 Compounds
    "एकशे चाळीस": 140, "एकशेचाळीस": 140, "एकशे चालीस": 140, "एकसे चाळीस": 140, "ekshe chalis": 140, "ekse chalis": 140, "one forty": 140,

    # 190 Compounds
    "एकशे नव्वद": 190, "एकशेनव्वद": 190, "एकशे नब्बे": 190, "एकसे नव्वद": 190, "ekshe navvad": 190, "ekse navvad": 190, "one ninety": 190,

    # 550 Compounds
    "साडेपाचशे": 550, "साडे पाचशे": 550, "पाचशे पन्नास": 550, "पाचशेपन्नास": 550, "साडेपाचसे": 550,
    "five fifty": 550, "five-fifty": 550, "sade pachshe": 550, "sade paachshe": 550, "pachshe pannas": 550,

    # 650, 750, 850, 950, 980
    "साडेसहाशे": 650, "सहाशे पन्नास": 650, "six fifty": 650,
    "साडेसातशे": 750, "सातशे पन्नास": 750, "seven fifty": 750,
    "साडेआठशे": 850, "आठशे पन्नास": 850, "eight fifty": 850,
    "साडेनऊशे": 950, "नऊशे पन्नास": 950, "nine fifty": 950,
    "नऊशे ऐंशी": 980, "नऊशे ऐशी": 980, "naushe ayshi": 980, "naushe aishi": 980, "nine eighty": 980,

    # 110, 250, 350, 450, 150, 125
    "एकशे दहा": 110, "one ten": 110, "ekshe daha": 110,
    "अडीचशे": 250, "दोनशे पन्नास": 250, "two fifty": 250, "dhai sau": 250, "donshe pannas": 250,
    "साडेतीनशे": 350, "तीनशे पन्नास": 350, "three fifty": 350,
    "साडेचारशे": 450, "चारशे पन्नास": 450, "four fifty": 450,
    "दीडशे": 150, "एक सौ पचास": 150, "one fifty": 150, "deedshe": 150, "सव्वाशे": 125,

    # Spaced Hundreds
    "एक शे": 100, "ek she": 100, "ek shey": 100,
    "दोन शे": 200, "don she": 200, "don shey": 200, "दो सौ": 200,
    "तीन शे": 300, "teen she": 300, "teen shey": 300, "तीन सौ": 300,
    "चार शे": 400, "char she": 400, "chaar she": 400, "चार सौ": 400,
    "पाच शे": 500, "pach she": 500, "paach she": 500, "पाँच सौ": 500,
    "सहा शे": 600, "saha she": 600, "छह सौ": 600,
    "सात शे": 700, "sat she": 700, "saat she": 700, "सात सौ": 700,
    "आठ शे": 800, "aath she": 800, "ath she": 800, "आठ सौ": 800,
    "नऊ शे": 900, "nau she": 900, "nav she": 900, "नौ सौ": 900,
    "दीड शे": 150, "deed she": 150, "did she": 150, "dedh sau": 150, "dedh so": 150,
    "अडीच शे": 250, "adeech she": 250, "dhai sau": 250,
    "साडेतीन शे": 350, "sade teen she": 350,
    "साडेचार शे": 450, "sade char she": 450,
    "साडेपाच शे": 550, "sade pach she": 550,

    # Marathi, Hindi & English Hundreds
    "एकशे": 100, "ekshe": 100, "ekshey": 100, "एकसे": 100, "ekse": 100, "एक सौ": 100, "one hundred": 100, "शंभर": 100, "shambhar": 100,
    "दोनशे": 200, "donshe": 200, "donshey": 200, "दोनसे": 200, "दो सौ": 200, "two hundred": 200,
    "तीनशे": 300, "teenshe": 300, "teenshey": 300, "तीनसे": 300, "teen sau": 300, "three hundred": 300,
    "चारशे": 400, "charshe": 400, "chaarshey": 400, "चारसे": 400, "char sau": 400, "four hundred": 400,
    "पाचशे": 500, "pachshe": 500, "pachshey": 500, "पाचसे": 500, "paanch sau": 500, "five hundred": 500,
    "सहाशे": 600, "sahashe": 600, "sahashey": 600, "छह सौ": 600, "six hundred": 600,
    "सातशे": 700, "satshe": 700, "satshey": 700, "saat sau": 700, "seven hundred": 700,
    "आठशे": 800, "aathshe": 800, "aathshey": 800, "aath sau": 800, "eight hundred": 800,
    "नऊशे": 900, "नवशे": 900, "naushe": 900, "naushey": 900, "नौ सौ": 900, "nine hundred": 900,
    "हजार": 1000, "हज़ार": 1000, "hajar": 1000, "hazar": 1000, "एक हजार": 1000, "one thousand": 1000,
    "अकराशे": 1100, "akrashe": 1100, "बाराशे": 1200, "barashe": 1200, "पंधराशे": 1500, "pandhrashe": 1500,
}

UNITS_AND_TENS_MAP = {
    # 90s
    "नव्व्याण्णव": 99, "अठ्ठ्याण्णव": 98, "सत्याण्णव": 97, "शहाण्णव": 96,
    "पंच्याण्णव": 95, "panchyaannav": 95, "panchyannav": 95, "पंचानवे": 95,
    "चौऱ्याण्णव": 94, "त्र्याण्णव": 93, "ब्याण्णव": 92, "एक्याण्णव": 91,
    "navvad": 90, "नव्वद": 90, "नब्बे": 90, "ninety": 90,

    # 80s
    "एक्याऐंशी": 81, "ब्याऐंशी": 82, "त्र्याऐंशी": 83, "चौऱ्याऐंशी": 84,
    "पंच्याऐंशी": 85, "panchaishi": 85, "पचासी": 85,
    "शहाऐंशी": 86, "सत्याऐंशी": 87, "अठ्ठ्याऐंशी": 88, "atthyaainshi": 88,
    "एकोणनव्वद": 89, "aainshi": 80, "ainshi": 80, "aishi": 80, "assi": 80, "ऐंशी": 80, "अस्सी": 80, "eighty": 80,
    "आईशी": 80, "आइंशी": 80, "ऐशी": 80, "अऐंशी": 80, "आयशी": 80,

    # 70s
    "एकाहत्तर": 71, "बहात्तर": 72, "त्र्याहत्तर": 73, "चौऱ्याहत्तर": 74,
    "पंचाहत्तर": 75, "panchahattar": 75, "शहात्तर": 76, "सत्याहत्तर": 77, "अठ्ठ्याहत्तर": 78, "एकोणऐंशी": 79,
    "sattar": 70, "सत्तर": 70, "seventy": 70,

    # 60s
    "एकसष्ट": 61, "बासष्ट": 62, "त्रेसष्ट": 63, "चौसष्ट": 64, "पासष्ट": 65,
    "शासष्ट": 66, "सदसष्ट": 67, "अडुसष्ट": 68, "एकोणसत्तर": 69,
    "saath": 60, "sath": 60, "साठ": 60, "sixty": 60,

    # 50s
    "एकावन्न": 51, "बावन्न": 52, "त्रेपन्न": 53, "trepanna": 53, "चोपन्न": 54,
    "पंचावन्न": 55, "panchaavanna": 55, "छप्पन्न": 56, "सत्तावन्न": 57, "अठ्ठावन्न": 58, "एकोणसाठ": 59,
    "pannas": 50, "pachas": 50, "पन्नास": 50, "पचास": 50, "fifty": 50,

    # 40s
    "एकेचाळीस": 41, "बेचाळीस": 42, "त्रेचाळीस": 43, "चव्वेचाळीस": 44, "पंचेचाळीस": 45,
    "शेहेचाळीस": 46, "सत्तेचाळीस": 47, "अट्ठेचाळीस": 48, "एकोणपन्नास": 49,
    "chalis": 40, "chaalis": 40, "चाळीस": 40, "चालीस": 40, "forty": 40,

    # 30s
    "एकतीस": 31, "बत्तीस": 32, "तेहतीस": 33, "चौतीस": 34, "पस्तीस": 35, "pastis": 35, "paintis": 35, "पैंतीस": 35, "thirty five": 35,
    "छत्तीस": 36, "सदतीस": 37, "अडतीस": 38, "एकोणचाळीस": 39,
    "tees": 30, "tis": 30, "तीस": 30, "thirty": 30,

    # 20s
    "एकवीस": 21, "बावीस": 22, "तेवीस": 23, "चोवीस": 24, "पंचवीस": 25, "panchvis": 25, "pachis": 25, "twenty five": 25,
    "सव्वीस": 26, "सत्तावीस": 27, "अठ्ठावीस": 28, "एकोणतीस": 29,
    "vees": 20, "bees": 20, "वीस": 20, "बीस": 20, "twenty": 20,

    # 1-19
    "एकोणीस": 19, "ekonis": 19, "अठरा": 18, "athra": 18, "सतरा": 17, "satra": 17, "सोळा": 16, "sola": 16,
    "पंधरा": 15, "pandhra": 15, "चौदा": 14, "chauda": 14, "तेरा": 13, "tera": 13, "बारा": 12, "bara": 12,
    "अकरा": 11, "akara": 11, "दहा": 10, "daha": 10, "das": 10, "ten": 10,
    "नऊ": 9, "nau": 9, "nav": 9, "nine": 9,
    "आठ": 8, "aath": 8, "ath": 8, "eight": 8,
    "सात": 7, "saat": 7, "sat": 7, "seven": 7,
    "सहा": 6, "saha": 6, "six": 6,
    "पाच": 5, "paach": 5, "panch": 5, "pach": 5, "five": 5,
    "चार": 4, "chaar": 4, "char": 4, "four": 4,
    "तीन": 3, "teen": 3, "tin": 3, "three": 3,
    "दोन": 2, "don": 2, "do": 2, "two": 2,
    "एक": 1, "ek": 1, "one": 1, "शून्य": 0, "zero": 0,

    # Fractions
    "साडेतीन": 3.5, "साडेचार": 4.5, "साडेपाच": 5.5,
    "सव्वा": 1.25, "savva": 1.25, "दीड": 1.5, "deed": 1.5, "dedh": 1.5,
    "अडीच": 2.5, "adeech": 2.5, "dhai": 2.5, "पाऊण": 0.75, "paun": 0.75,
    "अर्धा": 0.5, "अर्धी": 0.5, "ardha": 0.5, "aadha": 0.5, "half": 0.5,
    "पावशेर": 0.25, "पाव": 0.25, "paav": 0.25, "pav": 0.25, "quarter": 0.25,
}

# Compatibility aliases
COMPOUND_PRICING_MAP = HUNDREDS_MAP
SPOKEN_NUMBER_WORDS = UNITS_AND_TENS_MAP

# Precompile regexes
SORTED_THOU_KEYS = sorted(THOUSAND_MULTIPLIERS.keys(), key=len, reverse=True)
THOU_PATTERN = "|".join(map(re.escape, SORTED_THOU_KEYS))
PRECOMPILED_THOU_REGEX = re.compile(
    rf"(?:^|(?<=[^\u0900-\u097Fa-zA-Z0-9]))(\d+(?:\.\d+)?|{THOU_PATTERN})\s*(?:हजार|हज़ार|हज़ारों|hajar|hazar|hazaar|thousand|thousands)(?=[^\u0900-\u097Fa-zA-Z0-9]|$)",
    re.IGNORECASE,
)
PRECOMPILED_STANDALONE_THOU_REGEX = re.compile(
    r"(?:^|(?<=[^\u0900-\u097Fa-zA-Z0-9]))(?:हजार|हज़ार|hajar|hazar|hazaar|thousand)(?=[^\u0900-\u097Fa-zA-Z0-9]|$)",
    re.IGNORECASE,
)

SORTED_HUNDREDS_KEYS = sorted(HUNDREDS_MAP.keys(), key=len, reverse=True)
SORTED_UNITS_TENS_KEYS = sorted(UNITS_AND_TENS_MAP.keys(), key=len, reverse=True)
HUNDRED_PATTERN = "|".join(map(re.escape, SORTED_HUNDREDS_KEYS))
UNIT_TENS_PATTERN = "|".join(map(re.escape, SORTED_UNITS_TENS_KEYS))

PRECOMPILED_COMPOUND_HUNDREDS_REGEX = re.compile(
    rf"(?:^|(?<=[^\u0900-\u097Fa-zA-Z0-9]))({HUNDRED_PATTERN})(?:\s+({UNIT_TENS_PATTERN}|\d{{1,2}}))?(?=[^\u0900-\u097Fa-zA-Z0-9]|$)",
    re.IGNORECASE,
)
PRECOMPILED_UNITS_TENS_REGEX = re.compile(
    rf"(?:^|(?<=[^\u0900-\u097Fa-zA-Z0-9]))({UNIT_TENS_PATTERN})(?=[^\u0900-\u097Fa-zA-Z0-9]|$)",
    re.IGNORECASE,
)

PRECOMPILED_MERGE_THOUSANDS_REGEX = re.compile(
    r"\b([1-9]\d*000)\s+(?:(?:आणि|and)\s+)?(\d{1,3})\b(?=\s*(?:रुपये|रुपयांची|रुपयांचे|रुपयांचा|रुपया|रु\.|रु|रूपय|रूपये|रू|rs|rupees|rupaye|rupay|ruapaye|रुपीज|ropey|rupai|\/|per|\b|$))",
    re.IGNORECASE,
)
PRECOMPILED_FILLER_REGEX = make_unicode_regex("आणि|तसेच|त्यानंतर|त्याच्यानंतर|बरं|पुढे|द्या|घ्या|पाहिजे|लाव|टाक|आणखी|आण")
PRECOMPILED_PRICE_REGEX = make_unicode_regex(
    r"रुपये|रुपयांची|रुपयांचे|रुपयांचा|रुपयाने|रुपयाला|रुपयाची|रुपयाचे|रुपयाचा|रुपया|रु\.|रु|रूपय|रूपये|रू|"
    r"भावाने|भावाची|भावाचा|भावाचे|भाव|दराने|दराचा|दराची|दराचे|दर|प्रति|प्रती|"
    r"rs|rupees|rupee|rupaye|rupay|ruapaye|rupiya|rupiye|rupe|inr|₹|\/-"
)

UNICODE_END_PATTERN = r"(?=[^\u0900-\u097Fa-zA-Z0-9]|$)"

def clean_rate_per_unit_clause(clause: str) -> str:
    """Handles per-unit rate clauses: e.g. '60 rs kg' -> '1 kg 60 rs', '2 kg 60 rs kg' -> '2 kg 60 rs'."""
    rate_unit_m = re.search(rf"(?<!\d)(\d+(?:\.\d+)?)\s*rs\s*(kg|litre|packet|box|piece|gm|dozen){UNICODE_END_PATTERN}", clause, flags=re.IGNORECASE)
    if rate_unit_m:
        rate_val = rate_unit_m.group(1)
        rate_unit = rate_unit_m.group(2)
        clause_without_rate_unit = clause[:rate_unit_m.start()] + " " + clause[rate_unit_m.end():]
        has_other_qty = bool(re.search(rf"(?<!\d)(\d+(?:\.\d+)?)\s*(?:kg|litre|packet|box|piece|gm|dozen){UNICODE_END_PATTERN}", clause_without_rate_unit, flags=re.IGNORECASE))
        if has_other_qty:
            clause = clause[:rate_unit_m.start()] + f" {rate_val} rs " + clause[rate_unit_m.end():]
        else:
            clause = clause[:rate_unit_m.start()] + f" 1 {rate_unit} {rate_val} rs " + clause[rate_unit_m.end():]
    return clause


def parse_marathi_spoken_numbers(text: str) -> str:
    """Converts Marathi/Hindi/English number words into numeric digits."""
    if not text or not isinstance(text, str):
        return ""
    s = text.strip()

    # 1. Convert Devanagari digits [०-९]
    s = s.translate(DEV_TO_ASCII)

    # 1b. Thousands
    def replace_thou(m):
        raw_val = m.group(1)
        val = float(raw_val) if re.match(r"^\d+(?:\.\d+)?$", raw_val) else THOUSAND_MULTIPLIERS.get(raw_val.lower(), 1)
        return f" {round(val * 1000)} "

    s = PRECOMPILED_THOU_REGEX.sub(replace_thou, s)
    s = PRECOMPILED_STANDALONE_THOU_REGEX.sub(" 1000 ", s)

    # 2. Compound Hundreds (e.g. एकशे चाळीस -> 140, पाचशे पन्नास -> 550)
    def replace_hundreds(m):
        h_word = m.group(1) or ""
        next_word = m.group(2)
        h_key = h_word.lower()
        h_val = HUNDREDS_MAP.get(h_key) or HUNDREDS_MAP.get(h_word, 0)
        if not next_word:
            return f" {h_val} "
        if next_word.isdigit():
            return f" {h_val + int(next_word)} "
        u_key = next_word.lower()
        u_val = UNITS_AND_TENS_MAP.get(u_key) or UNITS_AND_TENS_MAP.get(next_word, 0)
        if isinstance(u_val, (int, float)) and 0 < u_val < 100:
            return f" {int(h_val + u_val)} "
        return f" {h_val} {next_word} "

    s = PRECOMPILED_COMPOUND_HUNDREDS_REGEX.sub(replace_hundreds, s)

    # 3. Standalone Units & Tens (e.g. 60, 50, 90, 80, 40, 10, 5)
    def replace_units(m):
        u_word = m.group(1) or ""
        u_key = u_word.lower()
        u_val = UNITS_AND_TENS_MAP.get(u_key) or UNITS_AND_TENS_MAP.get(u_word, u_word)
        return f" {u_val} "

    s = PRECOMPILED_UNITS_TENS_REGEX.sub(replace_units, s)

    # 4. Merge thousands with following hundreds/tens
    def replace_merge(m):
        t_val = int(m.group(1))
        r_val = int(m.group(2))
        if r_val < 1000:
            return f" {t_val + r_val} "
        return m.group(0)

    s = PRECOMPILED_MERGE_THOUSANDS_REGEX.sub(replace_merge, s)

    return s


MARATHI_UNITS = [
    (make_unicode_regex(r"किलो|किग्र|कि\.ग्रा|kilo|kilos|kg|kgs|kilogram|किलू|किलु|kilu"), "kg"),
    (make_unicode_regex(r"ग्रॅम|ग्राम|ग्रा|गरयम|गराम|गिराम|ग्रेम|gram|grams|gm|gms|g"), "gm"),
    (make_unicode_regex(r"लिटर|लीटर|litre|litres|liter|liters|ltr|ltrs|l"), "litre"),
    (make_unicode_regex(r"मिली|मिलीलिटर|ml|mls|millilitre"), "ml"),
    (make_unicode_regex(r"पुडा|पुडे|पुडी|पाकीट|पाकिटे|पॅकेट|पॅकेट्स|पैकेट|पॉकेट|packet|packets|pkt|pkts|pouch"), "packet"),
    (make_unicode_regex(r"नग|पीस|piece|pieces|pcs|pc|item|items"), "piece"),
    (make_unicode_regex(r"बाटली|बाटल्या|bottle|bottles|btl"), "bottle"),
    (make_unicode_regex(r"डबा|डबे|खोके|खोका|बॉक्स|box|boxes|carton"), "box"),
    (make_unicode_regex(r"डझन|दर्जन|dozen|dozens"), "dozen"),
    (make_unicode_regex(r"तोळा|तोळे|tola"), "tola"),
]

# Multilingual Kirana Item Catalog
MARATHI_KIRANA_ITEMS = [
    # Grains & Cereals
    {"canonical": "Tandul", "marathi": "तांदूळ", "hindi": "चावल", "terms": ["तांदूळ", "तांदुळ", "तान्दूल", "तान्दुल", "tandul", "tandool", "tandur", "chawal", "rice", "भात", "कोलम तांदूळ", "रेशन तांदूळ"]},
    {"canonical": "Basmati Rice", "marathi": "बासमती तांदूळ", "hindi": "बासमती चावल", "terms": ["बासमती", "बासमती तांदूळ", "basmati", "basmati rice", "इंडिया गेट", "india gate", "indiagate", "दावत", "daawat", "dawat", "कोहिनूर", "kohinoor", "तुकडा बासमती", "दुबार", "तिबार", "मोगरा बासमती", "फॉर्च्यून बासमती"]},
    {"canonical": "Shardatara Rice", "marathi": "शारदा तारा तांदूळ", "hindi": "शारदा तारा चावल", "terms": ["शारदा तारा", "शारदातांडूळ", "शारदा तारा तांदूळ", "shardatara", "sharda tara", "shardatara rice"]},
    {"canonical": "Chandtara Rice", "marathi": "चांद तारा तांदूळ", "hindi": "चांद तारा चावल", "terms": ["चांद तारा", "चांदतारा", "चांद तारा तांदूळ", "chandtara", "chand tara", "chandtara rice"]},
    {"canonical": "Kolam Rice", "marathi": "कोलम तांदूळ", "hindi": "कोलम चावल", "terms": ["कोलम", "कोलम तांदूळ", "लचकारी कोलम", "वाडा कोलम", "गुजरात कोलम", "kolam", "kolam rice", "lachkari", "lachkari kolam", "wada kolam"]},
    {"canonical": "Indrayani Rice", "marathi": "इंद्रायणी तांदूळ", "hindi": "इंद्रायणी चावल", "terms": ["इंद्रायणी", "इंद्रायणी तांदूळ", "जुना इंद्रायणी", "नवीन इंद्रायणी", "indrayani", "indrayani rice"]},
    {"canonical": "Ambemohar Rice", "marathi": "आंबेमोहर तांदूळ", "hindi": "आंबेमोहर चावल", "terms": ["आंबेमोहर", "आंबेमोहर तांदूळ", "ambemohar", "ambemohor"]},
    {"canonical": "Sona Masoori Rice", "marathi": "सोना मसुरी तांदूळ", "hindi": "सोना मसूरी चावल", "terms": ["सोना मसुरी", "सोना मसुरी तांदूळ", "sona masoori", "sona masuri"]},
    {"canonical": "Jiresal Rice", "marathi": "जिरेसाळ तांदूळ", "hindi": "जीरा राइस", "terms": ["जिरेसाळ", "जिरेसाळ तांदूळ", "जिरा राईस", "jiresal", "jeera rice"]},
    {"canonical": "Boiled Rice", "marathi": "उकडा तांदूळ", "hindi": "उबला चावल", "terms": ["उकडा तांदूळ", "इडली तांदूळ", "ukada tandul", "idli rice", "boiled rice"]},
    {"canonical": "Tukda Rice", "marathi": "तुकडा तांदूळ", "hindi": "टुकड़ा चावल", "terms": ["तुकडा तांदूळ", "कणी", "कणी तांदूळ", "tukda rice", "kani"]},
    {"canonical": "Pohe", "marathi": "पोहे", "hindi": "पोहा", "terms": ["पोहे", "पोहा", "pohe", "poha", "जाडे पोहे", "जाड पोहे", "पातळ पोहे", "दगडी पोहे", "नायलॉन पोहे"]},
    {"canonical": "Murmure", "marathi": "मुरमुरे", "hindi": "मुरमुरे", "terms": ["मुरमुरे", "मुरमुरा", "मूर्मूरी", "मूरे", "मुरमुऱ्या", "मुरमूरे", "मुरमूर", "murmura", "murmure", "murmuri", "लाया", "भेळ मुरमुरे"]},
    {"canonical": "Bhadang", "marathi": "भडंग", "hindi": "भडंग", "terms": ["भडंग", "कोल्हापुरी भडंग", "bhadang"]},
    {"canonical": "Lahi", "marathi": "लाही", "hindi": "लाई", "terms": ["लाही", "ज्वारी लाही", "मका लाही", "lahi"]},
    {"canonical": "Bajri", "marathi": "बाजरी", "hindi": "बाजरा", "terms": ["बाजरी", "बाजरा", "bajri", "bajara", "bajra"]},
    {"canonical": "Gahu", "marathi": "गहू", "hindi": "गेहूं", "terms": ["गहू", "गहु", "gahu", "gehu", "wheat", "लोकवन", "लोकवन गहू", "सीहोर", "सीहोर गहू", "तुकडी गहू"]},
    {"canonical": "Jowar", "marathi": "ज्वारी", "hindi": "ज्वार", "terms": ["ज्वारी", "ज्वार", "jwari", "jowar", "jowari", "मालदांडी", "मालदांडी ज्वारी", "गावरान ज्वारी"]},
    {"canonical": "Makka", "marathi": "मका", "hindi": "मक्का", "terms": ["मका", "मक्का", "makka", "corn", "maize"]},
    {"canonical": "Nachni", "marathi": "नाचणी", "hindi": "रागी", "terms": ["नाचणी", "रागी", "nachni", "ragi", "finger millet"]},
    {"canonical": "Rajgira", "marathi": "राजगिरा", "hindi": "राजगिरा", "terms": ["राजगिरा", "राजगिरा दाणे", "rajgira", "amaranth"]},
    {"canonical": "Jau", "marathi": "जव", "hindi": "जौ", "terms": ["जव", "जौ", "सातू", "jau", "sattu", "barley"]},
    {"canonical": "Shabu", "marathi": "शाबू", "hindi": "साबूदाना", "terms": ["शाबू", "साबुदाणा", "साबुदाना", "shabu", "sabudana", "sago", "नायलॉन साबुदाणा"]},
    {"canonical": "Dalia", "marathi": "दलिया", "hindi": "दलहिया", "terms": ["दलिया", "लापशी", "लापशी रवा", "dalia", "lapsi", "broken wheat"]},
    {"canonical": "Oats", "marathi": "ओट्स", "hindi": "ओट्स", "terms": ["ओट्स", "oats", "masala oats"]},

    # Flours & Atta
    {"canonical": "Atta", "marathi": "गव्हाचे पीठ", "hindi": "आटा", "terms": ["गव्हाचे पीठ", "गहू आटा", "गहू पीठ", "कणिक", "आटा", "gahu aata", "gahu pith", "gahu peeth", "gehu atta", "atta", "aata", "wheat flour", "चक्की आटा", "आशीर्वाद आटा", "आशीर्वाद", "aashirvaad", "aashirvaad atta", "फॉर्च्यून आटा", "fortune atta", "पिल्सबरी", "pillsbury", "सम्राट आटा"]},
    {"canonical": "Besan", "marathi": "बेसन", "hindi": "बेसन", "terms": ["बेसन", "चना पीठ", "चणा पीठ", "हरभरा पीठ", "besan", "gram flour", "सम्राट बेसन", "samrat besan", "फॉर्च्यून बेसन"]},
    {"canonical": "Maida", "marathi": "मैदा", "hindi": "मैदा", "terms": ["मैदा", "माईदा", "मैधा", "maida", "all purpose flour"]},
    {"canonical": "Rawa", "marathi": "रवा", "hindi": "सूजी", "terms": ["रवा", "बारीक रवा", "जाडा रवा", "जाड रवा", "सुजी", "सूजी", "बॉम्बे रवा", "rawa", "rava", "sooji", "suji", "semolina"]},
    {"canonical": "Tandul Peeth", "marathi": "तांदळाचे पीठ", "hindi": "चावल का आटा", "terms": ["तांदळाचे पीठ", "तांदूळ पीठ", "tandul peeth", "rice flour"]},
    {"canonical": "Jowar Peeth", "marathi": "ज्वारीचे पीठ", "hindi": "ज्वार का आटा", "terms": ["ज्वारीचे पीठ", "ज्वारी पीठ", "jowar flour", "jwari peeth"]},
    {"canonical": "Bajri Peeth", "marathi": "बाजरीचे पीठ", "hindi": "बाजरे का आटा", "terms": ["बाजरीचे पीठ", "बाजरी पीठ", "bajra flour", "bajri peeth"]},
    {"canonical": "Makka Peeth", "marathi": "मक्याचे पीठ", "hindi": "मक्के का आटा", "terms": ["मक्याचे पीठ", "मका पीठ", "corn flour", "makka atta"]},
    {"canonical": "Nachni Peeth", "marathi": "नाचणीचे पीठ", "hindi": "रागी का आटा", "terms": ["नाचणीचे पीठ", "नाचणी पीठ", "रागी पीठ", "ragi flour", "nachni peeth"]},
    {"canonical": "Bhajani", "marathi": "थालीपीठ भाजणी पीठ", "hindi": "भाजिणी", "terms": ["थालीपीठ भाजणी पीठ", "थालीपीठ पीठ", "भाजणी पीठ", "भाजणी", "उपवास भाजणी", "thalipeeth bhajani"]},
    {"canonical": "Singhara Atta", "marathi": "शिंगाडा पीठ", "hindi": "सिंघाड़ा आटा", "terms": ["शिंगाडा पीठ", "शिंगाड्याचे पीठ", "singhara atta", "singhada peeth"]},
    {"canonical": "Rajgira Peeth", "marathi": "राजगिरा पीठ", "hindi": "राजगिरा आटा", "terms": ["राजगिरा पीठ", "rajgira flour", "rajgira peeth"]},

    # Pulses & Dals
    {"canonical": "Tur Dal", "marathi": "तूर डाळ", "hindi": "अरहर दाल", "terms": ["तूर डाळ", "तुरीची डाळ", "तूरडाळ", "तूर", "tur dal", "toor dal", "arhar dal", "अरहर"]},
    {"canonical": "Moong Dal", "marathi": "मूग डाळ", "hindi": "मूंग दाल", "terms": ["मूग डाळ", "मुगाची डाळ", "मूंग डाळ", "मूंगडाल", "मुंग दाल", "मुंगदाल", "moong dal", "mung dal", "मूग मोगर", "पिवळी मूग डाळ"]},
    {"canonical": "Chana Dal", "marathi": "चना डाळ", "hindi": "चना दाल", "terms": ["चना डाळ", "चणा डाळ", "हरभरा डाळ", "chanadal", "chana dal", "harbhara dal"]},
    {"canonical": "Urad Dal", "marathi": "उडीद डाळ", "hindi": "उड़द दाल", "terms": ["उडीद डाळ", "उडदाची डाळ", "उडीद", "urad dal", "udid dal", "काळी उडीद डाळ", "सफेद उडीद डाळ"]},
    {"canonical": "Masoor Dal", "marathi": "मसूर डाळ", "hindi": "मसूर दाल", "terms": ["मसूर डाळ", "मसूर", "मसुराची डाळ", "masoor dal", "masoor", "लाल मसूर"]},
    {"canonical": "Chole", "marathi": "काबुली चणे", "hindi": "छोले", "terms": ["काबुली चणे", "काबुली चना", "छोले", "chole", "kabuli chana"]},
    {"canonical": "Harbhara", "marathi": "हरभरा", "hindi": "चना", "terms": ["हरभरा", "चणा", "काळा चणा", "काळा हरभरा", "harbhara", "chana", "black chana"]},
    {"canonical": "Matki", "marathi": "मटकी", "hindi": "मटकी", "terms": ["मटकी", "मोड आलेली मटकी", "matki", "moth beans"]},
    {"canonical": "Rajma", "marathi": "राजमा", "hindi": "राजमा", "terms": ["राजमा", "rajma", "चित्र राजमा", "लाल राजमा", "कश्मीरी राजमा"]},
    {"canonical": "Vatana", "marathi": "वाटाणा", "hindi": "मटर", "terms": ["वाटाणा", "सफेद वाटाणा", "हिरवा वाटाणा", "vatana", "matar", "dry peas"]},
    {"canonical": "Chavali", "marathi": "चवळी", "hindi": "लोबिया", "terms": ["चवळी", "चवळी दाणे", "लोबिया", "chavali", "chawli", "lobia"]},
    {"canonical": "Kulith", "marathi": "कुळीथ", "hindi": "कुलथी", "terms": ["कुळीथ", "हुलगा", "kulith", "hulga", "horse gram"]},
    {"canonical": "Akha Moong", "marathi": "अख्खा मूग", "hindi": "साबुत मूंग", "terms": ["अख्खा मूग", "हिरवे मूग", "साबुत मूंग", "akha moong", "whole moong"]},
    {"canonical": "Akha Urad", "marathi": "अख्खा उडीद", "hindi": "साबुत उड़द", "terms": ["अख्खा उडीद", "काळी उडीद", "akha urad", "whole urad"]},
    {"canonical": "Akha Masoor", "marathi": "अख्खा मसूर", "hindi": "साबुत मसूर", "terms": ["अख्खा मसूर", "काळा मसूर", "akha masoor", "whole masoor"]},

    # Cooking Oils & Ghee
    {"canonical": "Fortune Tel", "marathi": "फॉर्च्यून तेल", "hindi": "फॉर्च्यून तेल", "terms": ["फॉर्च्यून तेल", "फॉर्च्यून", "fortune tel", "fortune oil", "fortune sunflower", "फॉर्च्यून सूर्यफूल", "फॉर्च्यून सोयाबीन"]},
    {"canonical": "Godetel", "marathi": "गोडेतेल", "hindi": "तेल", "terms": ["गोडेतेल", "तेल", "तेलाचे", "tel", "oil", "cooking oil"]},
    {"canonical": "Shengdana Tel", "marathi": "शेंगदाणा तेल", "hindi": "मूंगफली तेल", "terms": ["शेंगदाणा तेल", "shengdana tel", "groundnut oil", "peanut oil"]},
    {"canonical": "Sunflower Tel", "marathi": "सूर्यफूल तेल", "hindi": "सूरजमुखी तेल", "terms": ["सूर्यफूल तेल", "सनफ्लॉवर तेल", "sunflower oil", "फॉर्च्यून सूर्यफूल", "धारा सूर्यफूल", "सनरिच", "सनड्रॉप", "प्रिया तेल"]},
    {"canonical": "Gemini Tel", "marathi": "जेमिनी तेल", "hindi": "जेमिनी तेल", "terms": ["जेमिनी तेल", "जेमिनी", "gemini oil", "gemini"]},
    {"canonical": "Soyabean Tel", "marathi": "सोयाबीन तेल", "hindi": "सोयाबीन तेल", "terms": ["सोयाबीन तेल", "सोयाबीन", "soyabean oil", "soyabean tel", "फॉर्च्यून सोयाबीन", "महाकोश", "रुची सोया", "कीर्ती तेल"]},
    {"canonical": "Mustard Tel", "marathi": "मोहरी तेल", "hindi": "सरसों तेल", "terms": ["मोहरी तेल", "सरसो तेल", "सरसों तेल", "mustard oil", "कच्ची घाणी", "इंजिन तेल", "engine oil", "बैल कोल्हू", "हाथी छाप"]},
    {"canonical": "Palmolein Tel", "marathi": "पामोलीन तेल", "hindi": "पामोलिन तेल", "terms": ["पामोलीन तेल", "पाम तेल", "पामोलीन", "palmolein oil", "palm oil"]},
    {"canonical": "Til Tel", "marathi": "तीळ तेल", "hindi": "तिल तेल", "terms": ["तीळ तेल", "तिळाचे तेल", "til oil", "sesame oil"]},
    {"canonical": "Khobrel Tel", "marathi": "खोबरेल तेल", "hindi": "नारियल तेल", "terms": ["खोबरेल तेल", "पॅराशूट", "पॅराशूट तेल", "khobrel tel", "coconut oil", "parachute oil"]},
    {"canonical": "Rice Bran Tel", "marathi": "राईस ब्रान तेल", "hindi": "राइस ब्रान तेल", "terms": ["राईस ब्रान तेल", "rice bran oil", "फॉर्च्यून राईस ब्रान"]},
    {"canonical": "Tup", "marathi": "तूप", "hindi": "घी", "terms": ["तूप", "तूपाचे", "साजूक तूप", "देशी तूप", "tup", "toop", "ghee", "अमुल तूप", "amul ghee", "गोवर्धन तूप", "चितळे तूप", "पतंजली तूप"]},
    {"canonical": "Dalda", "marathi": "डालडा", "hindi": "डालडा", "terms": ["डालडा", "वनस्पती तूप", "dalda", "vanaspati ghee"]},

    # Spices & Condiments
    {"canonical": "Halad", "marathi": "हळद", "hindi": "हल्दी", "terms": ["हळद", "हळदी", "हल्दी", "halad", "haldi", "turmeric", "हळद पावडर", "हळकुंड"]},
    {"canonical": "Jeera", "marathi": "जिरे", "hindi": "जीरा", "terms": ["जिरे", "जिरं", "जीरा", "jeera", "jira", "cumin", "cumin seeds", "जिरे पावडर"]},
    {"canonical": "Shahjeera", "marathi": "शहाजिरे", "hindi": "शाही जीरा", "terms": ["शहाजिरे", "शाही जीरा", "shahjeera", "shahi jeera"]},
    {"canonical": "Mohari", "marathi": "मोहरी", "hindi": "राई", "terms": ["मोहरी", "राई", "mohari", "rai", "mustard seeds", "मोहरी दाणे"]},
    {"canonical": "Dhane", "marathi": "धने", "hindi": "धनिया", "terms": ["धने", "धना", "धनिया", "dhane", "dhana", "dhaniya", "coriander", "coriander seeds", "धने पावडर"]},
    {"canonical": "Methi", "marathi": "मेथी दाणे", "hindi": "मेथी दाना", "terms": ["मेथी दाणे", "मेथी", "methi", "methi dana", "fenugreek"]},
    {"canonical": "Badishep", "marathi": "बडीशेप", "hindi": "सौंफ", "terms": ["बडीशेप", "बडीसोप", "सौंफ", "badishep", "saunf", "fennel seeds"]},
    {"canonical": "Owa", "marathi": "ओवा", "hindi": "अजवाइन", "terms": ["ओवा", "अजवाइन", "owa", "ajwain", "carom seeds"]},
    {"canonical": "Hing", "marathi": "हिंग", "hindi": "हींग", "terms": ["हिंग", "हींग", "hing", "asafoetida", "एलजी हिंग", "एमडीएच हिंग", "एव्हरेस्ट हिंग"]},
    {"canonical": "Lavang", "marathi": "लवंग", "hindi": "लौंग", "terms": ["लवंग", "लावंग", "लौंग", "lawang", "lavang", "laung", "clove", "cloves"]},
    {"canonical": "Kalimiri", "marathi": "काळी मिरी", "hindi": "काली मिर्च", "terms": ["काळी मिरी", "मिरी", "काली मिर्च", "miri", "kalimiri", "black pepper", "pepper"]},
    {"canonical": "Dalchini", "marathi": "दालचिनी", "hindi": "दालचीनी", "terms": ["दालचिनी", "दालचीनी", "dalchini", "cinnamon"]},
    {"canonical": "Velchi", "marathi": "वेलची", "hindi": "इलायची", "terms": ["वेलची", "विलायची", "इलायची", "velchi", "elaichi", "cardamom", "हिरवी वेलची"]},
    {"canonical": "Moti Elaichi", "marathi": "मोठी वेलची", "hindi": "बड़ी इलायची", "terms": ["मोठी वेलची", "काळी वेलची", "बड़ी इलायची", "moti elaichi", "black cardamom"]},
    {"canonical": "Chakriphool", "marathi": "चक्रीफूल", "hindi": "चक्र फूल", "terms": ["चक्रीफूल", "चक्री फूल", "chakriphool", "star anise"]},
    {"canonical": "Tejpan", "marathi": "तमालपत्र", "hindi": "तेजपत्ता", "terms": ["तमालपत्र", "तेजपान", "तेजपत्ता", "tejpan", "tamalpatra", "bay leaf"]},
    {"canonical": "Jaiphal", "marathi": "जायफळ", "hindi": "जयफल", "terms": ["जायफळ", "जयफल", "jaiphal", "nutmeg"]},
    {"canonical": "Javitri", "marathi": "जावेत्री", "hindi": "जावित्री", "terms": ["जावेत्री", "जावित्री", "javitri", "mace"]},
    {"canonical": "Khaskhas", "marathi": "खसखस", "hindi": "खसखस", "terms": ["खसखस", "khaskhas", "poppy seeds"]},
    {"canonical": "Sunth", "marathi": "सुंठ", "hindi": "सोंठ", "terms": ["सुंठ", "सोंठ", "sunth", "sonth", "dry ginger"]},
    {"canonical": "Lal Tikhat", "marathi": "लाल तिखट", "hindi": "लाल मिर्च", "terms": ["लाल तिखट", "मिरची पावडर", "तिखट", "मिरची", "लाल मिरची", "lal tikhat", "mirchi", "mirchi powder", "chilli", "red chilli"]},
    {"canonical": "Kashmiri Mirch", "marathi": "काश्मिरी मिरची", "hindi": "कश्मीरी मिर्च", "terms": ["काश्मिरी मिरची", "काश्मिरी लाल", "kashmiri mirch", "kashmiri lal", "कश्मीरी तिखालाल"]},
    {"canonical": "Bedgi Mirch", "marathi": "बेडगी मिरची", "hindi": "बेडगी मिर्च", "terms": ["बेडगी मिरची", "बेडगी तिखट", "bedgi mirch", "byadgi"]},
    {"canonical": "Kasuri Methi", "marathi": "कसुरी मेथी", "hindi": "कसूरी मेथी", "terms": ["कसुरी मेथी", "कसूरी मेथी", "kasuri methi"]},

    # Readymade Mix Spices & Brands
    {"canonical": "Garam Masala", "marathi": "गरम मसाला", "hindi": "गरम मसाला", "terms": ["गरम मसाला", "garam masala", "masala"]},
    {"canonical": "Goda Masala", "marathi": "गोडा मसाला", "hindi": "गोड़ा मसाला", "terms": ["गोडा मसाला", "काळं तिखट", "काळा मसाला", "goda masala", "kala masala"]},
    {"canonical": "Kanda Lasun Masala", "marathi": "कांदा लसूण मसाला", "hindi": "कांदा लहसुन मसाला", "terms": ["कांदा लसूण मसाला", "कांदा लसूण", "kanda lasun masala", "kanda lasun"]},
    {"canonical": "Chicken Masala", "marathi": "चिकन मसाला", "hindi": "चिकन मसाला", "terms": ["चिकन मसाला", "chicken masala"]},
    {"canonical": "Mutton Masala", "marathi": "मटन मसाला", "hindi": "मटन मसाला", "terms": ["मटन मसाला", "mutton masala"]},
    {"canonical": "Biryani Masala", "marathi": "बिर्याणी मसाला", "hindi": "बिरयानी मसाला", "terms": ["बिर्याणी मसाला", "biryani masala"]},
    {"canonical": "Sambar Masala", "marathi": "सांबार मसाला", "hindi": "सांभर मसाला", "terms": ["सांबार मसाला", "sambar masala"]},
    {"canonical": "Pav Bhaji Masala", "marathi": "पावभाजी मसाला", "hindi": "पाव भाजी मसाला", "terms": ["पावभाजी मसाला", "pav bhaji masala"]},
    {"canonical": "Chole Masala", "marathi": "छोले मसाला", "hindi": "छोले मसाला", "terms": ["छोले मसाला", "chole masala"]},
    {"canonical": "Chaat Masala", "marathi": "चाट मसाला", "hindi": "चाट मसाला", "terms": ["चाट मसाला", "chaat masala"]},
    {"canonical": "Panipuri Masala", "marathi": "पाणीपुरी मसाला", "hindi": "पानीपुरी मसाला", "terms": ["पाणीपुरी मसाला", "panipuri masala"]},
    {"canonical": "Kitchen King", "marathi": "किचन किंग मसाला", "hindi": "किचन किंग", "terms": ["किचन किंग", "kitchen king"]},
    {"canonical": "Everest Masala", "marathi": "एव्हरेस्ट मसाला", "hindi": "एवरेस्ट मसाला", "terms": ["एव्हरेस्ट", "everest", "everest masala", "तिखालाल", "tikhalal"]},
    {"canonical": "Suhana Masala", "marathi": "सुहाना मसाला", "hindi": "सुहाना मसाला", "terms": ["सुहाना", "suhana", "suhana masala"]},
    {"canonical": "MDH Masala", "marathi": "एमडीएच मसाला", "hindi": "एमडीएच मसाला", "terms": ["एमडीएच", "mdh", "mdh masala", "देग्गी मिर्च", "deggi mirch"]},
    {"canonical": "Badshah Masala", "marathi": "बादशाह मसाला", "hindi": "बादशाह मसाला", "terms": ["बादशाह", "badshah", "badshah masala"]},
    {"canonical": "Pravin Masala", "marathi": "प्रवीण मसाला", "hindi": "प्रवीण मसाला", "terms": ["प्रवीण", "pravin", "pravin masala", "प्रवीण लोणचे"]},
    {"canonical": "Rambandhu Masala", "marathi": "रामबंधू मसाला", "hindi": "रामबंधु मसाला", "terms": ["रामबंधू", "rambandhu", "rambandhu masala"]},

    # Soaps & Bars
    {"canonical": "Saban", "marathi": "साबण", "hindi": "साबुन", "terms": ["साबण", "saban", "soap", "saban soap", "soap saban", "साबण सोप", "साबुन", "अंगाचा साबण", "कपड्यांचा साबण", "bath soap", "toilet soap"]},
    {"canonical": "Lux Saban", "marathi": "लक्स साबण", "hindi": "लक्स साबुन", "terms": ["लक्स", "लक्स साबण", "lux", "lux soap"]},
    {"canonical": "Santoor Saban", "marathi": "संतूर साबण", "hindi": "संतूर साबुन", "terms": ["संतूर", "संतूर साबण", "santoor", "santoor soap"]},
    {"canonical": "Lifebuoy Saban", "marathi": "लाईफबॉय साबण", "hindi": "लाइफबॉय साबुन", "terms": ["लाईफबॉय", "लाईफबॉय साबण", "lifebuoy", "lifebuoy soap"]},
    {"canonical": "Dettol Saban", "marathi": "डेटॉल साबण", "hindi": "डेटॉल साबुन", "terms": ["डेटॉल", "डेटॉल साबण", "dettol", "dettol soap"]},
    {"canonical": "Dove Saban", "marathi": "डव्ह साबण", "hindi": "डव साबुन", "terms": ["डव्ह", "डव्ह साबण", "dove", "dove soap"]},
    {"canonical": "Godrej No 1", "marathi": "गोदरेज नंबर १ साबण", "hindi": "गोदरेज नंबर 1", "terms": ["गोदरेज नंबर १", "गोदरेज साबण", "godrej no 1", "godrej no.1"]},
    {"canonical": "Medimix Saban", "marathi": "मेडिमिक्स साबण", "hindi": "मेडिमिक्स साबुन", "terms": ["मेडिमिक्स", "मेडिमिक्स साबण", "medimix"]},
    {"canonical": "Hamam Saban", "marathi": "हमाम साबण", "hindi": "हमाम साबुन", "terms": ["हमाम", "हमाम साबण", "hamam"]},
    {"canonical": "Cinthol Saban", "marathi": "सिंथॉल साबण", "hindi": "सिंथॉल साबुन", "terms": ["सिंथॉल", "सिंथॉल साबण", "cinthol"]},
    {"canonical": "Pears Saban", "marathi": "पियर्स साबण", "hindi": "पियर्स साबुन", "terms": ["पियर्स", "पियर्स साबण", "pears"]},
    {"canonical": "Mysore Sandal", "marathi": "मैसूर सँडल साबण", "hindi": "मैसूर सैंडल साबुन", "terms": ["मैसूर सँडल", "mysore sandal"]},
    {"canonical": "Margo Saban", "marathi": "मार्गो साबण", "hindi": "मार्गो साबुन", "terms": ["मार्गो", "margo"]},
    {"canonical": "Rin Bar", "marathi": "रिन बार", "hindi": "रिन साबुन", "terms": ["रिन", "रिन बार", "रिन साबण", "rin", "rin bar", "rin soap"]},
    {"canonical": "Wheel Bar", "marathi": "व्हील बार", "hindi": "व्हील साबुन", "terms": ["व्हील बार", "व्हील साबण", "wheel bar", "wheel soap"]},
    {"canonical": "Surf Excel Bar", "marathi": "सर्फ एक्सेल बार", "hindi": "सर्फ एक्सेल बार", "terms": ["सर्फ एक्सेल बार", "सर्फ बार", "surf excel bar"]},
    {"canonical": "Tide Bar", "marathi": "टायड बार", "hindi": "टाइड साबुन", "terms": ["टायड बार", "टायड साबण", "tide bar", "tide soap"]},
    {"canonical": "Ghadi Bar", "marathi": "घडी बार", "hindi": "घड़ी साबुन", "terms": ["घडी बार", "घडी साबण", "ghadi bar", "ghadi soap"]},
    {"canonical": "501 Bar", "marathi": "५०१ बार", "hindi": "501 साबुन", "terms": ["५०१ बार", "५०१ साबण", "501 bar", "501 soap"]},
    {"canonical": "Vim Bar", "marathi": "विम बार", "hindi": "विम बार", "terms": ["विम बार", "विम", "विम साबण", "vim", "vim bar", "vim soap"]},
    {"canonical": "Exo Bar", "marathi": "एक्झो बार", "hindi": "एक्सो बार", "terms": ["एक्झो", "एक्झो बार", "exo", "exo bar"]},
    {"canonical": "Pril Bar", "marathi": "प्रिल बार", "hindi": "प्रिल बार", "terms": ["प्रिल", "प्रिल बार", "pril", "pril bar"]},

    # Detergent Powders & Brands
    {"canonical": "Detergent", "marathi": "डिटर्जंट पावडर", "hindi": "सर्फ", "terms": ["डिटर्जंट पावडर", "डिटर्जंट", "डिटर्जेंट", "detergent", "dtergent", "detergent powder", "washing powder", "वॉशिंग पावडर", "powder", "पावडर", "सर्फ", "surf"]},
    {"canonical": "Surf Excel", "marathi": "सर्फ एक्सेल पावडर", "hindi": "सर्फ एक्सेल", "terms": ["सर्फ एक्सेल", "सर्फ एक्सेल पावडर", "surf excel", "surf excel powder", "सर्फ एक्सेल मॅटिक", "surf excel matic", "easy wash"]},
    {"canonical": "Ariel", "marathi": "एरियल पावडर", "hindi": "एरियल", "terms": ["एरियल", "एरियल पावडर", "ariel", "ariel powder", "ariel matic"]},
    {"canonical": "Tide", "marathi": "टायड पावडर", "hindi": "टाइड", "terms": ["टायड", "टायड पावडर", "tide", "tide powder", "tide plus"]},
    {"canonical": "Wheel Powder", "marathi": "व्हील पावडर", "hindi": "व्हील पाउडर", "terms": ["व्हील पावडर", "व्हील", "wheel", "wheel powder", "active wheel"]},
    {"canonical": "Ghadi Powder", "marathi": "घडी पावडर", "hindi": "घड़ी पाउडर", "terms": ["घडी पावडर", "घडी", "ghadi", "ghadi powder", "घडी डिटर्जंट"]},
    {"canonical": "Nirma Powder", "marathi": "निरमा पावडर", "hindi": "निरमा", "terms": ["निरमा", "निरमा पावडर", "nirma", "nirma powder", "वाशिंग पावडर निरमा"]},
    {"canonical": "Fena Powder", "marathi": "फेना पावडर", "hindi": "फेना", "terms": ["फेना", "फेना पावडर", "fena", "fena powder"]},
    {"canonical": "Rin Powder", "marathi": "रिन पावडर", "hindi": "रिन पाउडर", "terms": ["रिन पावडर", "rin powder"]},
    {"canonical": "Ujala", "marathi": "उजाला", "hindi": "उजाला", "terms": ["उजाला", "उजाला सुप्रीम", "उजाला लिक्विड", "ujala", "ujala liquid"]},
    {"canonical": "Comfort", "marathi": "कम्फर्ट", "hindi": "कंफर्ट", "terms": ["कम्फर्ट", "comfort", "fabric conditioner"]},

    # Cosmetics & Personal Care
    {"canonical": "Colgate", "marathi": "कोलगेट पेस्ट", "hindi": "कोलगेट", "terms": ["कोलगेट", "कोलगेट पेस्ट", "colgate", "colgate paste", "मॅक्सफ्रेश", "maxfresh", "colgate strong teeth"]},
    {"canonical": "Closeup", "marathi": "क्लोजअप पेस्ट", "hindi": "क्लोज़अप", "terms": ["क्लोजअप", "close up", "closeup"]},
    {"canonical": "Pepsodent", "marathi": "पेप्सोडेंट पेस्ट", "hindi": "पेप्सोडेंट", "terms": ["पेप्सोडेंट", "pepsodent"]},
    {"canonical": "Dabur Red", "marathi": "डाबर लाल पेस्ट", "hindi": "डाबर लाल", "terms": ["डाबर लाल", "डाबर रेड", "dabur red", "दंतमंजन"]},
    {"canonical": "Dant Kanti", "marathi": "दंतकांती पेस्ट", "hindi": "दंत कांति", "terms": ["दंतकांती", "पतंजली दंतकांती", "dant kanti"]},
    {"canonical": "Sensodyne", "marathi": "सेन्सोडाइन पेस्ट", "hindi": "सेंसोडाइन", "terms": ["सेन्सोडाइन", "सेन्सोडाईन", "sensodyne"]},
    {"canonical": "Fair and Lovely", "marathi": "फेअर अँड लव्हली", "hindi": "फेयर एंड लवली", "terms": ["फेअर अँड लव्हली", "फेअर लव्हली", "ग्लो अँड लव्हली", "fair and lovely", "fair lovely", "glow and lovely", "glow lovely"]},
    {"canonical": "Ponds", "marathi": "पॉन्ड्स क्रीम", "hindi": "पॉन्ड्स", "terms": ["पॉन्ड्स", "पॉन्ड्स क्रीम", "पॉन्ड्स पावडर", "ponds", "ponds powder", "ponds cream"]},
    {"canonical": "Vaseline", "marathi": "व्हॅसलीन", "hindi": "वेसलीन", "terms": ["व्हॅसलीन", "vaseline", "पेट्रोलियम जेली"]},
    {"canonical": "Boroline", "marathi": "बोरोलीन", "hindi": "बोरोलीन", "terms": ["बोरोलीन", "boroline"]},
    {"canonical": "Vicco", "marathi": "विको हळद क्रीम", "hindi": "विको", "terms": ["विको", "विको हळद", "विको वज्रदंती", "vicco"]},
    {"canonical": "Parachute", "marathi": "पॅराशूट खोबरेल तेल", "hindi": "पैराशूट", "terms": ["पॅराशूट", "पॅराशूट तेल", "parachute", "parachute coconut oil"]},
    {"canonical": "Bajaj Almond", "marathi": "बजाज बदाम तेल", "hindi": "बजाज बादाम तेल", "terms": ["बजाज बदाम", "बजाज बदाम तेल", "bajaj almond", "bajaj almond drops"]},
    {"canonical": "Nihar Amla", "marathi": "निहार आवळा तेल", "hindi": "निहार आंवला", "terms": ["निहार", "निहार आवळा", "nihar", "nihar shanti amla"]},
    {"canonical": "Dabur Amla", "marathi": "डाबर आवळा तेल", "hindi": "डाबर आंवला", "terms": ["डाबर आवळा", "dabur amla"]},
    {"canonical": "Navratna Oil", "marathi": "नवरत्न तेल", "hindi": "नवरत्न तेल", "terms": ["नवरत्न", "नवरत्न तेल", "navratna", "navratna oil"]},
    {"canonical": "Clinic Plus", "marathi": "क्लिनिक प्लस शाम्पू", "hindi": "क्लिनिक प्लस", "terms": ["क्लिनिक प्लस", "clinic plus", "clinic plus shampoo"]},
    {"canonical": "Sunsilk", "marathi": "सनसिल्क शाम्पू", "hindi": "सनसिल्क", "terms": ["सनसिल्क", "sunsilk", "sunsilk shampoo"]},
    {"canonical": "Head and Shoulders", "marathi": "हेड अँड शोल्डर्स शाम्पू", "hindi": "हेड एंड शोल्डर्स", "terms": ["हेड अँड शोल्डर्स", "head and shoulders"]},
    {"canonical": "Dove Shampoo", "marathi": "डव्ह शाम्पू", "hindi": "डव शैम्पू", "terms": ["डव्ह शाम्पू", "dove shampoo"]},
    {"canonical": "Dermi Cool", "marathi": "डर्मिकूल पावडर", "hindi": "डर्मी कूल", "terms": ["डर्मिकूल", "dermi cool", "डर्मीकूल"]},
    {"canonical": "Nycil", "marathi": "नायसिल पावडर", "hindi": "नायसिल", "terms": ["नायसिल", "nycil", "nycil powder"]},

    # Bakery Products
    {"canonical": "Parle G", "marathi": "पारले-जी बिस्कीट", "hindi": "पारले जी", "terms": ["पारले जी", "पारले-जी", "parle g", "parle-g", "parle"]},
    {"canonical": "Marie Gold", "marathi": "मेरी गोल्ड बिस्कीट", "hindi": "मैरी गोल्ड", "terms": ["मेरी गोल्ड", "मेरी बिस्कीट", "marie gold", "britannia marie", "marie"]},
    {"canonical": "Good Day", "marathi": "गुड डे बिस्कीट", "hindi": "गुड डे", "terms": ["गुड डे", "गुडडे", "good day"]},
    {"canonical": "20-20 Biscuit", "marathi": "२०-२० बिस्कीट", "hindi": "20-20 बिस्कुट", "terms": ["२०-२०", "twenty twenty", "20-20", "20-20 biscuit"]},
    {"canonical": "Oreo", "marathi": "ओरिओ बिस्कीट", "hindi": "ओरियो", "terms": ["ओरिओ", "oreo"]},
    {"canonical": "Bourbon", "marathi": "बोर्बन बिस्कीट", "hindi": "बोर्बोन", "terms": ["बोर्बन", "बॉर्बन", "bourbon"]},
    {"canonical": "Monaco", "marathi": "मोनांक बिस्कीट", "hindi": "मोनाको", "terms": ["मोनांक", "मोनाको", "monaco"]},
    {"canonical": "Krackjack", "marathi": "क्रॅकजॅक बिस्कीट", "hindi": "क्रैकजैक", "terms": ["क्रॅकजॅक", "krackjack"]},
    {"canonical": "Tiger Biscuit", "marathi": "टायगर बिस्कीट", "hindi": "टाइगर", "terms": ["टायगर", "tiger biscuit"]},
    {"canonical": "Bounce Biscuit", "marathi": "बाउंस बिस्कीट", "hindi": "बाउंस", "terms": ["बाउंस", "bounce"]},
    {"canonical": "Jim Jam", "marathi": "जिम जॅम बिस्कीट", "hindi": "जिम जैम", "terms": ["जिम जॅम", "jim jam"]},
    {"canonical": "Hide and Seek", "marathi": "हाइड अँड सीक बिस्कीट", "hindi": "हाइड एंड सीक", "terms": ["हाइड अँड सीक", "hide and seek"]},
    {"canonical": "Milk Bikis", "marathi": "मिल्क बिकीज बिस्कीट", "hindi": "मिल्क बिकिस", "terms": ["मिल्क बिकीज", "milk bikis"]},
    {"canonical": "Patanjali Biscuit Box", "marathi": "पतंजली बिस्कीट बॉक्स", "hindi": "पतंजली बिस्कुट बॉक्स", "terms": ["पतंजली बिस्कीट बॉक्स", "patanjali biscuit box"]},
    {"canonical": "Toast Rusk", "marathi": "टोस्ट / रस्क", "hindi": "टोस्ट", "terms": ["टोस्ट", "रस्क", "toast", "rusk", "ब्रिटानिया टोस्ट"]},
    {"canonical": "Khari", "marathi": "खारी", "hindi": "खारी", "terms": ["खारी", "बटर खारी", "जिरा खारी", "khari", "butter khari"]},
    {"canonical": "Bread", "marathi": "ब्रेड", "hindi": "ब्रेड", "terms": ["ब्रेड", "पांढरा ब्रेड", "ब्राऊन ब्रेड", "bread"]},
    {"canonical": "Pav", "marathi": "पाव", "hindi": "पाव", "terms": ["पाव", "लादी पाव", "pav", "ladi pav"]},
    {"canonical": "Butter", "marathi": "अमुल बटर", "hindi": "मक्खन", "terms": ["बटर", "अमुल बटर", "butter", "amul butter"]},
    {"canonical": "Cream Roll", "marathi": "क्रीम रोल", "hindi": "क्रीम रोल", "terms": ["क्रीम रोल", "cream roll"]},
    {"canonical": "Cake", "marathi": "केक", "hindi": "केक", "terms": ["केक", "ब्रिटानिया केक", "cake", "britannia cake"]},
    {"canonical": "Shev Farsan", "marathi": "शेव फरसाण", "hindi": "सेव फरसाण", "terms": ["शेव", "फरसाण", "shev", "farsan", "नायलॉन शेव", "कोल्हापुरी फरसाण"]},
    {"canonical": "Chakli", "marathi": "चकली", "hindi": "चकली", "terms": ["चकली", "chakli", "चकली भाजणी"]},

    # Sweeteners, Salt, Nuts & Kirana Essentials
    {"canonical": "Sakhar", "marathi": "साखर", "hindi": "चीनी", "terms": ["साखर", "साखरेची", "साखरेचा", "साकर", "शुकर", "सुकर", "sakhar", "saakhar", "sugar", "चीनी", "शक्कर"]},
    {"canonical": "Gul", "marathi": "गूळ", "hindi": "गुड़", "terms": ["गूळ", "गुळ", "गुळाची", "gul", "gud", "jaggery", "गुड़", "कोल्हापुरी गूळ", "सेंद्रिय गूळ"]},
    {"canonical": "Kakvi", "marathi": "काकवी", "hindi": "काकवी", "terms": ["काकवी", "kakvi", "liquid jaggery"]},
    {"canonical": "Khadisakhar", "marathi": "खडीसाखर", "hindi": "मिश्री", "terms": ["खडीसाखर", "khadisakhar", "mishri"]},
    {"canonical": "Meeth", "marathi": "मीठ", "hindi": "नमक", "terms": ["मीठ", "मिठाचे", "meeth", "mith", "namak", "salt", "टाटा मीठ", "टाटा सॉल्ट", "खडे मीठ"]},
    {"canonical": "Sendhav Meeth", "marathi": "सेंधव मीठ", "hindi": "सेंधा नमक", "terms": ["सेंधव मीठ", "सेंधा नमक", "sendha namak", "rock salt"]},
    {"canonical": "Kala Meeth", "marathi": "काळे मीठ", "hindi": "काला नमक", "terms": ["काळे मीठ", "काला नमक", "black salt"]},
    {"canonical": "Shengdane", "marathi": "शेंगदाणे", "hindi": "मूंगफली", "terms": ["शेंगदाणे", "शेंगदाणा", "shengdane", "shengdana", "peanuts", "mungfali", "दाणे"]},
    {"canonical": "Kaju", "marathi": "काजू", "hindi": "काजू", "terms": ["काजू", "काजू तुकडा", "kaju", "cashew"]},
    {"canonical": "Badam", "marathi": "बदाम", "hindi": "बादाम", "terms": ["बदाम", "badam", "almond"]},
    {"canonical": "Pista", "marathi": "पिस्ता", "hindi": "पिस्ता", "terms": ["पिस्ता", "pista", "pistachio"]},
    {"canonical": "Manuka", "marathi": "मनुका", "hindi": "किशमिश", "terms": ["मनुका", "किशमिश", "बेदाणा", "manuka", "kismis", "kishmish", "raisins"]},
    {"canonical": "Khobra", "marathi": "खोबरं", "hindi": "सूखा नारियल", "terms": ["खोबरं", "सुके खोबरे", "खोबरे", "khobare", "khobra", "dry coconut", "copra"]},
    {"canonical": "Kharik", "marathi": "खारीक", "hindi": "छुहारा", "terms": ["खारीक", "खारिक", "kharik", "dry dates"]},
    {"canonical": "Akhrot", "marathi": "अक्रोड", "hindi": "अखरोट", "terms": ["अक्रोड", "akhrot", "walnut"]},
    {"canonical": "Anjeer", "marathi": "अंजीर", "hindi": "अंजीर", "terms": ["अंजीर", "anjeer", "dry figs"]},
    {"canonical": "Charoli", "marathi": "चारोळी", "hindi": "चिरौंजी", "terms": ["चारोळी", "charoli", "chironji"]},
    {"canonical": "Makhana", "marathi": "मखाना", "hindi": "मखाना", "terms": ["मखाना", "फूल मखाना", "makhana", "fox nuts"]},
    {"canonical": "Supari", "marathi": "सुपारी", "hindi": "सुपारी", "terms": ["सुपारी", "सुपारी तुकडा", "supari", "betel nut", "आखा सुपारी"]},

    # Tea, Coffee & Beverages
    {"canonical": "Chaha", "marathi": "चहा", "hindi": "चाय", "terms": ["चहा", "चाहा", "चहा पावडर", "चहापत्ती", "chaha", "chai", "tea", "चाय"]},
    {"canonical": "Sargam Dust Tea", "marathi": "सरगम पत्ती चहा", "hindi": "सरगम पत्ती चाय", "terms": ["सरगम पत्ती चहा", "सरगम चहा", "सरगम पत्ती", "सरगम", "sargam", "sargam patti chaha"]},
    {"canonical": "Super Dust Tea", "marathi": "सुपर डस्ट चहा", "hindi": "सुपर डस्ट चाय", "terms": ["सुपर डस्ट चहा", "सुपर डस्ट", "super dust", "super dust tea"]},
    {"canonical": "Society Tea", "marathi": "सोसायटी चहा", "hindi": "सोसायटी चाय", "terms": ["सोसायटी चहा", "सोसायटी", "society tea"]},
    {"canonical": "Wagh Bakri Tea", "marathi": "वाघ बकरी चहा", "hindi": "वाघ बकरी चाय", "terms": ["वाघ बकरी चहा", "वाघ बकरी", "wagh bakri"]},
    {"canonical": "Red Label Tea", "marathi": "रेड लेबल चहा", "hindi": "रेड लेबल", "terms": ["रेड लेबल", "red label", "brook bond"]},
    {"canonical": "Taj Mahal Tea", "marathi": "ताजमहाल चहा", "hindi": "ताजमहल चाय", "terms": ["ताजमहाल", "ताजमहाल चहा", "taj mahal tea"]},
    {"canonical": "Tata Tea Gold", "marathi": "टाटा टी गोल्ड", "hindi": "टाटा टी गोल्ड", "terms": ["टाटा टी", "टाटा टी गोल्ड", "tata tea"]},
    {"canonical": "Coffee", "marathi": "कॉफी", "hindi": "कॉफ़ी", "terms": ["कॉफी", "coffee", "nescafe", "bru", "नेस्कॅफे", "ब्रू"]},
    {"canonical": "Dudh", "marathi": "दूध", "hindi": "दूध", "terms": ["दूध", "दुध", "dudh", "doodh", "milk"]},

    # Pooja & Miscellaneous
    {"canonical": "Agarbatti", "marathi": "अगरबत्ती", "hindi": "अगरबत्ती", "terms": ["अगरबत्ती", "मोक्ष अगरबत्ती", "झेड ब्लॅक", "सायकल अगरबत्ती", "मंगलदीप", "agarbatti", "mangaldeep"]},
    {"canonical": "Kapoor", "marathi": "कापूर", "hindi": "कपूर", "terms": ["कापूर", "भीमसेनी कापूर", "कापूर वड्या", "kapoor", "camphor"]},
    {"canonical": "Rangoli", "marathi": "रांगोळी", "hindi": "रंगोली", "terms": ["रांगोळी", "rangoli"]},
    {"canonical": "Dhoop", "marathi": "धूप", "hindi": "धूप", "terms": ["धूप", "dhoop", "धूप कांड्या"]},
    {"canonical": "Kadepeti", "marathi": "काडेपेटी", "hindi": "माचिस", "terms": ["काडेपेटी", "माचिस", "kadepeti", "matchbox"]},
    {"canonical": "Kande", "marathi": "कांदे", "hindi": "प्याज", "terms": ["कांदे", "कांदा", "kande", "kanda", "onion"]},
    {"canonical": "Batate", "marathi": "बटाटे", "hindi": "आलू", "terms": ["बटाटे", "बटाटा", "batate", "batata", "potato"]},
    {"canonical": "Lasun", "marathi": "लसूण", "hindi": "लहसुन", "terms": ["लसूण", "lasun", "garlic"]},
    {"canonical": "Maggi", "marathi": "मॅगी", "hindi": "मैगी", "terms": ["मॅगी", "maggi", "noodles"]},
    {"canonical": "Sarki Pend", "marathi": "सरकी पेंड", "hindi": "सरकी पेंड", "terms": ["सरकी पेंड", "सरकी पेंढ", "sarki pend", "sarkipend"]},
    {"canonical": "Celery", "marathi": "सेलरी (Celery)", "hindi": "सेलरी", "terms": ["celery", "celary", "सेलरी"]},
]

# Fast Pre-indexed Catalog Map for O(1) & difflib fuzzy lookups
CATALOG_TERMS_INDEX: Dict[str, Dict[str, Any]] = {}
ALL_CATALOG_TERMS: List[str] = []
for entry in MARATHI_KIRANA_ITEMS:
    for term in entry["terms"]:
        tl = term.lower().strip()
        if tl not in CATALOG_TERMS_INDEX:
            CATALOG_TERMS_INDEX[tl] = entry
            ALL_CATALOG_TERMS.append(tl)


def canonicalize_marathi_item_name(name: str, language: str = "mr-IN", output_lang: Optional[str] = None) -> str:
    """
    Canonicalizes item name according to dialect & output language.
    Uses exact lookup followed by Python's built-in difflib fuzzy matching
    to catch typos and spoken variants like 'dtergent', 'powder', 'saban soap'.
    """
    if not name or not isinstance(name, str):
        return ""
    converted = convert_indic_script_to_devanagari(name)
    deduped = deduplicate_spoken_tokens(converted)
    clean = deduped.lower().strip()

    is_devanagari = bool(re.search(r"[\u0900-\u097F]", deduped))
    lang_lower = str(language or "mr-IN").lower()
    is_hindi = lang_lower.startswith("hi")
    is_english = lang_lower.startswith("en") or str(output_lang or "").lower().startswith("en")
    is_marathi = not is_english and (lang_lower.startswith("mr") or not is_hindi)

    def _format_entry(entry: Dict[str, Any]) -> str:
        if is_english:
            return entry["canonical"]
        if is_hindi:
            return entry["hindi"]
        if is_marathi:
            return entry["marathi"]
        return entry["canonical"]

    stripped = re.sub(r"(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$", "", clean, flags=re.IGNORECASE).strip()

    # 1. Exact match in catalog terms
    if clean in CATALOG_TERMS_INDEX:
        return _format_entry(CATALOG_TERMS_INDEX[clean])
    if stripped in CATALOG_TERMS_INDEX:
        return _format_entry(CATALOG_TERMS_INDEX[stripped])

    # 2. Sub-term lookup for spoken compound echoes (e.g. "saban soap", "detergent powder", "washing powder")
    for term, entry in CATALOG_TERMS_INDEX.items():
        if len(term) >= 4 and term in clean:
            return _format_entry(entry)

    # 3. Built-in Python difflib fuzzy match (catches typos like 'dtergent' -> 'detergent')
    close_matches = difflib.get_close_matches(clean, ALL_CATALOG_TERMS, n=1, cutoff=0.78)
    if close_matches:
        candidate = close_matches[0]
        if abs(len(clean) - len(candidate)) <= 2:
            return _format_entry(CATALOG_TERMS_INDEX[candidate])

    if is_devanagari:
        stripped_dev = re.sub(r"(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$", "", deduped, flags=re.IGNORECASE).strip()
        return stripped_dev

    return clean.title()


CURR_RE_STR = r"(?:rs|rupaye|rupay|rupees|rupee|inr|रुपये|रुपया|रू|₹|\/-)"


def collapse_unit_echoes(s: str) -> str:
    """Collapses bilingual and repeated unit echoes: e.g. '1kg 1kilo' -> '1 kg', '2kg 2kilo' -> '2 kg'."""
    s = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|किलो|किग्रा|केजी)\s*(?:/|\s+)?(?:\1\s*)?(?:kg|kilo|किलो|किग्रा|केजी)",
        r"\1 kg",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:gm|gram|g|ग्रॅम|ग्राम)\s*(?:/|\s+)?(?:\1\s*)?(?:gm|gram|g|ग्रॅम|ग्राम)",
        r"\1 gm",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:litre|liter|ltr|l|लिटर|लीटर)\s*(?:/|\s+)?(?:\1\s*)?(?:litre|liter|ltr|l|लिटर|लीटर)",
        r"\1 litre",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:packet|pkt|पाकीट|पुडा|पॅकेट)\s*(?:/|\s+)?(?:\1\s*)?(?:packet|pkt|पाकीट|पुडा|पॅकेट)",
        r"\1 packet",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:box|खोके|बॉक्स)\s*(?:/|\s+)?(?:\1\s*)?(?:box|खोके|बॉक्स)",
        r"\1 box",
        s,
        flags=re.IGNORECASE,
    )
    return s


def collapse_price_echoes(s: str) -> str:
    """Collapses bilingual and repeated price echoes: e.g. '50rs 50 rs' -> '50 rs', '120 120 rs' -> '120 rs'."""
    s = re.sub(
        rf"(?<!\d)(\d+(?:\.\d+)?)(?!\d)(?:\s*{CURR_RE_STR})?(?:\s+|\s*{CURR_RE_STR}\s*)(?<!\d)\1(?!\d)(?:\s*{CURR_RE_STR})?",
        r" \1 rs ",
        s,
        flags=re.IGNORECASE,
    )
    return s


def normalize_marathi_transcript(text: str) -> str:
    """
    Complete Marathi transcript normalization before Regex or LLM processing:
    1. Converts misidentified Indic scripts & Devanagari numerals.
    2. Deduplicates speech repetitions and collapses unit echoes (1kg 1kilo -> 1 kg).
    3. Un-glues spoken numeral + unit words (एककिलो -> 1 kg, पावकिलो -> 250 gm).
    4. Normalizes units slashes (1kg/kilo -> 1 kg).
    5. Converts spoken number words to digits (साठ -> 60, पन्नास -> 50).
    6. Collapses repeated price echoes (50rs 50 rs -> 50 rs).
    7. Strips 100,000 hallucinations.
    """
    if not text or not isinstance(text, str):
        return ""

    # 0. Convert Indic script & digits
    s = convert_indic_script_to_devanagari(text)
    s = s.translate(DEV_TO_ASCII)

    # 0a0. Generic un-glue attached digit + unit (e.g. 1kilo -> 1 kg, 50rs -> 50 rs, 2litre -> 2 litre)
    s = re.sub(
        rf"(?<!\d)(\d+(?:\.\d+)?)\s*(kilo|kilu|kg|kgs|किग्रा|किलो|किलू|किलु|gm|gms|gram|grams|ग्रॅम|ग्राम|litre|liter|ltr|l|लिटर|लीटर|packet|pkt|पाकीट|पुडा|पॅकेट|box|खोके|खोका|बॉक्स|nag|नग|pcs|piece|dozen|डझन|दर्जन|tola|तोळा|तोला|rs|रू|रुपये|रुपया){UNICODE_END_PATTERN}",
        r"\1 \2",
        s,
        flags=re.IGNORECASE,
    )

    # 0a. Collapse unit echoes first: "1kg 1kilo" -> "1 kg", "2kg 2kilo" -> "2 kg"
    s = collapse_unit_echoes(s)

    # 0b. Preserve clause boundaries (commas, semicolons, pipes, danda) as spaced commas ' , '
    # Clean sentence-ending exclamation marks, question marks, and standalone periods
    s = re.sub(r"[,;:।|]+", " , ", s)
    s = re.sub(r"[!?.]+(?=\s|$)", " ", s)

    # 1. Deduplicate
    s = deduplicate_spoken_tokens(s)

    # 2. Un-glue numeral + unit compounds and fractional weights (with and without space)
    s = re.sub(r"(?:^|\s)(?:deedshe|deed\s*she|didshe|did\s*she|दीडशे|दीड\s*शे|dedh\s*sau|dedh\s*so)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 150 ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:pavkilo|pavkilu|पावकिलो|पाव\s*किलो|पावशेर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 250 gm ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:ardhakilo|ardhakilu|अर्धाकिलो|अर्धा\s*किलो|आधा\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 500 gm ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:paunkilo|paunkilu|पाऊणकिलो|पाऊण\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 750 gm ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:savvakilo|savvakilu|सव्वाकिलो|सव्वा\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 1.25 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:didshekilo|didkilo|दीडकिलो|दीड\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 1.5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:adichkilo|अडीचकिलो|अडीच\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 2.5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:sadeteenkilo|साडेतीन\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 3.5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:sadecharkilo|साडेचार\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 4.5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:sadepachkilo|साडेपाच\s*किलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 5.5 kg ", s, flags=re.IGNORECASE)

    s = re.sub(r"(?:^|\s)(?:ekkilo|ekkilu|ekilo|एककिलो|एक\s*किलो|एककिलू|एककिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 1 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:donkilo|donkilu|दोनकिलो|दोन\s*किलो|दोनकिलू|दोनकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 2 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:tinkilo|tinkilu|तीनकिलो|तीन\s*किलो|तीनकिलू|तीनकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 3 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:charkilo|charkilu|चारकिलो|चार\s*किलो|चारकिलू|चारकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 4 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:pachkilo|pachkilu|पाचकिलो|पाच\s*किलो|पाचकिलू|पाचकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:dahakilo|dahakilu|दहाकिलो|दहा\s*किलो|दहाकिलू|दहाकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 10 kg ", s, flags=re.IGNORECASE)

    s = re.sub(r"(?:^|\s)(?:pavlater|pavliter|पावलिटर|पाव\s*लिटर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 250 ml ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:ardhaliter|अर्धालिटर|अर्धा\s*लिटर|आधा\s*लिटर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 500 ml ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:ekliter|eklitre|एकलिटर|एक\s*लिटर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 1 litre ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:donliter|donlitre|दोनलिटर|दोन\s*लिटर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 2 litre ", s, flags=re.IGNORECASE)

    # 3. Normalize unit slashes
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(?:kg|kilo|किलो)\s*/\s*(?:kilo|kg|किलो)", r"\1 kg", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:kilu|किलू|किलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " kilo ", s, flags=re.IGNORECASE)

    # 4. Phonetic corrections
    s = re.sub(make_unicode_regex(r"साकर|शुकर|सुकर"), "साखर", s)
    s = re.sub(make_unicode_regex(r"साट"), "साठ", s)
    s = re.sub(make_unicode_regex(r"माईदा|मैधा|माईधा|मायदा"), "मैदा", s)
    s = re.sub(make_unicode_regex(r"शेंग\s*दानी|शेंगदानी|शेंग\s*दाने|शेंगदाने"), "शेंगदाणे", s)
    s = re.sub(make_unicode_regex(r"सर्गं\s*पत्ती|सर्गप\s*चहा|सर्कं\s*पत्ती"), "सरगम पत्ती चहा", s)
    s = re.sub(make_unicode_regex(r"सूपर\s*डस्ट|सुपर\s*डस्ट"), "सुपर डस्ट चहा", s)
    s = re.sub(make_unicode_regex(r"पात्स"), "पाच", s)
    s = re.sub(make_unicode_regex(r"मूंगडाल|मुंग\s*दाल|मुंगदाल"), "मूग डाळ", s)
    s = re.sub(make_unicode_regex(r"पणनसरुपई|पण्नास\s*रुपये|पन्नास\s*रुब्बाई|पणनस\s*रुपये|पणनस"), "50 रुपये", s)
    s = re.sub(make_unicode_regex(r"एकशिचाईस|एकशिचारीफ|एकशेचाईस|एकशे\s*चाईस"), "140", s)
    s = re.sub(make_unicode_regex(r"पस्चे\s*पन्नस|पश्य\s*पन्नास"), "550 रुपये", s)
    s = re.sub(make_unicode_regex(r"रोपेज|रुपेज|रोबइ|रोपई|रुब्बाई|रुपिज|रुपीज"), "रुपये", s)
    # Murmura (puffed rice) - Whisper often spells it in various ways
    s = re.sub(make_unicode_regex(r"मूर्मूरी|मूरे|मुरमुऱ्या|मुरमूरे|मुरमूर|मुरमुर"), "मुरमुरे", s)
    # Number word phonetic corrections for Whisper output
    s = re.sub(make_unicode_regex(r"आईशी|आइंशी|आयशी|अऐंशी|ऐशी"), "ऐंशी", s)
    s = re.sub(make_unicode_regex(r"सत्याहत्तर|सत्याहत्तर"), "सत्तर", s)  # 70 variants
    s = re.sub(make_unicode_regex(r"पन्नस|पन्ना|पणनस"), "पन्नास", s)  # 50 variants

    # 5. Spoken numbers to digits (1 to 5000)
    s = parse_marathi_spoken_numbers(s)

    # 6a. Rate postpositions with Unicode boundary (e.g. "६० रुपये किलोने", "६० भावाने", "६० दराने", "६० रुपये किलोला")
    s = re.sub(
        rf"(?<!\d)(\d+(?:\.\d+)?)\s*(?:rs|rupaye|rupees|rupee|रुपये|रुपया|रू|₹)?\s*(?:per|\/|प्रति|प्रती)?\s*(?:किलोने|किलोला|लिटरने|लिटरला|डझनाने|डझनाला|नगाने|नगाला|पाकिटाने|पाकिटाला|पुड्याने){UNICODE_END_PATTERN}",
        r" \1 rs ",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        rf"(?<!\d)(\d+(?:\.\d+)?)\s*(?:rs|rupaye|rupees|rupee|रुपये|रुपया|रू|₹)?\s*(?:per|\/|प्रति|प्रती)?\s*(?:भावाने|भावाची|भावाचा|भावाचे|भाव|दराने|दराचा|दराची|दराचे|दर|रुपयाने|रुपयाला|रुपयाची|रुपयाचे|रुपयांचा|रुपयांची){UNICODE_END_PATTERN}",
        r" \1 rs ",
        s,
        flags=re.IGNORECASE,
    )

    # 6b. Standardize units
    for pattern, canonical in MARATHI_UNITS:
        s = pattern.sub(f" {canonical} ", s)

    # 7. Standardize price markers
    s = PRECOMPILED_PRICE_REGEX.sub(" rs ", s)

    # 7b. Collapse price echoes (e.g. "50 rs 50 rs" -> "50 rs", "60 60 rs" -> "60 rs", "120 120 rs" -> "120 rs")
    s = collapse_price_echoes(s)

    # 7c. Collapse duplicate adjacent numbers spoken for emphasis (e.g. "60 60" -> "60", "550 550" -> "550")
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s+\1\b", r"\1", s)

    # 7d. Clean rate per unit in clauses (e.g. "साखर 60 rs kg" -> "साखर 1 kg 60 rs", "2 kg साखर 60 rs kg" -> "2 kg साखर 60 rs")
    clauses = [clean_rate_per_unit_clause(c) for c in s.split(" , ")]
    s = " , ".join(clauses)

    # 8. Guard: Remove 100,000 hallucinations
    s = re.sub(r"\b100000\b", "", s)
    s = re.sub(r"\b(?:1|ek|एक)\s*(?:lakh|lac|laakh|लाख)\b", "", s, flags=re.IGNORECASE)

    # Convert MRP markers (e.g. 10/-)
    s = re.sub(r"(\d+)\s*/\s*-?", r"\1/-", s)

    # Second pass for unit echoes
    s = collapse_unit_echoes(s)

    # Clean multiple spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Compatibility alias
normalize_voice_transcript = normalize_marathi_transcript
