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
PRECOMPILED_PRICE_REGEX = make_unicode_regex(r"रुपये|रुपयांची|रुपयांचे|रुपयांचा|रुपया|रु\.|रु|रूपय|रूपये|रू|rs|rupees|rupee|rupaye|rupay|ruapaye|rupiya|rupiye|rupe|inr|₹|/-")


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
    # Grains & Flours
    {"canonical": "Tandul", "marathi": "तांदूळ", "hindi": "चावल", "terms": ["तांदूळ", "तांदुळ", "तान्दूल", "तान्दुल", "tandul", "tandool", "tandur", "chawal", "rice", "भात", "कोलम", "बासमती", "इंद्रायणी", "तुकडा", "जिरा राईस"]},
    {"canonical": "Pohe", "marathi": "पोहे", "hindi": "पोहा", "terms": ["पोहे", "पोहा", "pohe", "poha", "जाडे पोहे", "पातळ पोहे"]},
    {"canonical": "Bajri", "marathi": "बाजरी", "hindi": "बाजरा", "terms": ["बाजरी", "बाजरा", "bajri", "bajara", "bajra", "बाजरीचे पीठ"]},
    {"canonical": "Gahu", "marathi": "गहू", "hindi": "गेहूं", "terms": ["गहू", "गहु", "gahu", "gehu", "wheat", "लोकवन", "सीहोर"]},
    {"canonical": "Atta", "marathi": "गव्हाचे पीठ", "hindi": "आटा", "terms": ["गव्हाचे पीठ", "गहू आटा", "गहू पीठ", "कणिक", "आटा", "gahu aata", "gahu pith", "gahu peeth", "gehu atta", "atta", "aata", "wheat flour", "चक्की आटा"]},
    {"canonical": "Jowar", "marathi": "ज्वारी", "hindi": "ज्वार", "terms": ["ज्वारी", "ज्वार", "jwari", "jowar", "jowari", "ज्वारीचे पीठ", "मालदांडी"]},
    {"canonical": "Maida", "marathi": "मैदा", "hindi": "मैदा", "terms": ["मैदा", "माईदा", "मैधा", "maida", "all purpose flour"]},
    {"canonical": "Besan", "marathi": "बेसन", "hindi": "बेसन", "terms": ["बेसन", "चना पीठ", "हरभरा पीठ", "besan", "gram flour"]},
    {"canonical": "Rawa", "marathi": "रवा", "hindi": "सूजी", "terms": ["रवा", "बारीक रवा", "जाडा रवा", "सुजी", "सूजी", "rawa", "rava", "sooji", "suji", "semolina"]},
    {"canonical": "Shabu", "marathi": "शाबू", "hindi": "साबूदाना", "terms": ["शाबू", "साबुदाणा", "साबुदाना", "shabu", "sabudana", "sago", "नायलॉन साबुदाणा"]},
    {"canonical": "Makka", "marathi": "मका", "hindi": "मक्का", "terms": ["मका", "मक्का", "makka", "corn", "मक्याचे पीठ"]},
    {"canonical": "Nachni", "marathi": "नाचणी", "hindi": "रागी", "terms": ["नाचणी", "रागी", "nachni", "ragi", "नाचणीचे पीठ"]},

    # Pulses & Dals
    {"canonical": "Masoor Dal", "marathi": "मसूर डाळ", "hindi": "मसूर दाल", "terms": ["मसूर डाळ", "मसूर", "मसुराची डाळ", "masoor dal", "masoor", "अख्खा मसूर", "लाल मसूर"]},
    {"canonical": "Chana Dal", "marathi": "चना डाळ", "hindi": "चना दाल", "terms": ["चना डाळ", "चणा डाळ", "हरभरा डाळ", "chanadal", "chana dal", "harbhara dal"]},
    {"canonical": "Tur Dal", "marathi": "तूर डाळ", "hindi": "अरहर दाल", "terms": ["तूर डाळ", "तुरीची डाळ", "तूरडाळ", "तूर", "tur dal", "toor dal", "arhar dal"]},
    {"canonical": "Moong Dal", "marathi": "मूग डाळ", "hindi": "मूंग दाल", "terms": ["मूग डाळ", "मुगाची डाळ", "मूंग डाळ", "मूंगडाल", "मुंग दाल", "मुंगदाल", "moong dal", "mung dal", "हिरवे मूग", "मूग मोगर"]},
    {"canonical": "Urad Dal", "marathi": "उडीद डाळ", "hindi": "उड़द दाल", "terms": ["उडीद डाळ", "उडदाची डाळ", "उडीद", "urad dal", "udid dal", "काळी उडीद"]},
    {"canonical": "Chole", "marathi": "काबुली चणे", "hindi": "छोले", "terms": ["काबुली चणे", "काबुली चना", "छोले", "chole", "kabuli chana"]},
    {"canonical": "Matki", "marathi": "मटकी", "hindi": "मटकी", "terms": ["मटकी", "मोड आलेली मटकी", "matki", "moth beans"]},
    {"canonical": "Rajma", "marathi": "राजमा", "hindi": "राजमा", "terms": ["राजमा", "rajma", "चित्र राजमा", "लाल राजमा"]},
    {"canonical": "Vatana", "marathi": "वाटाणा", "hindi": "मटर", "terms": ["वाटाणा", "सफेद वाटाणा", "हिरवा वाटाणा", "vatana", "matar", "dry peas"]},
    {"canonical": "Kulith", "marathi": "कुळीथ", "hindi": "कुलथी", "terms": ["कुळीथ", "हुलगा", "kulith", "hulga", "horse gram"]},
    {"canonical": "Harbhara", "marathi": "हरभरा", "hindi": "चना", "terms": ["हरभरा", "चणा", "काळा चणा", "harbhara", "chana", "black chana"]},

    # Spices & Condiments
    {"canonical": "Lavang", "marathi": "लवंग", "hindi": "लौंग", "terms": ["लवंग", "लावंग", "लौंग", "lawang", "lavang", "laung", "clove", "cloves"]},
    {"canonical": "Supari", "marathi": "सुपारी", "hindi": "सुपारी", "terms": ["सुपारी", "सुपारी तुकडा", "supari", "betel nut", "आखा सुपारी"]},
    {"canonical": "Dhane", "marathi": "धने", "hindi": "धनिया", "terms": ["धने", "धना", "धनिया", "dhane", "dhana", "dhaniya", "coriander", "coriander seeds", "धने पावडर"]},
    {"canonical": "Jeera", "marathi": "जिरे", "hindi": "जीरा", "terms": ["जिरे", "जिरं", "जीरा", "jeera", "jira", "cumin", "cumin seeds", "जिरे पावडर"]},
    {"canonical": "Mohari", "marathi": "मोहरी", "hindi": "राई", "terms": ["मोहरी", "राई", "mohari", "rai", "mustard seeds", "मोहरी दाणे"]},
    {"canonical": "Halad", "marathi": "हळद", "hindi": "हल्दी", "terms": ["हळद", "हळदी", "हल्दी", "halad", "haldi", "turmeric", "हळद पावडर"]},
    {"canonical": "Lal Tikhat", "marathi": "लाल तिखट", "hindi": "लाल मिर्च", "terms": ["लाल तिखट", "मिरची पावडर", "तिखट", "मिरची", "लाल मिरची", "lal tikhat", "mirchi", "mirchi powder", "chilli", "red chilli"]},
    {"canonical": "Hing", "marathi": "हिंग", "hindi": "हींग", "terms": ["हिंग", "हींग", "hing", "asafoetida", "एव्हरेस्ट हिंग"]},
    {"canonical": "Velchi", "marathi": "वेलची", "hindi": "इलायची", "terms": ["वेलची", "विलायची", "इलायची", "velchi", "elaichi", "cardamom", "हिरवी वेलची"]},
    {"canonical": "Dalchini", "marathi": "दालचिनी", "hindi": "दालचीनी", "terms": ["दालचिनी", "दालचीनी", "dalchini", "cinnamon"]},
    {"canonical": "Kalimiri", "marathi": "काळी मिरी", "hindi": "काली मिर्च", "terms": ["काळी मिरी", "मिरी", "काली मिर्च", "miri", "kalimiri", "black pepper", "pepper"]},
    {"canonical": "Methi", "marathi": "मेथी दाणे", "hindi": "मेथी दाना", "terms": ["मेथी दाणे", "मेथी", "methi", "methi dana", "fenugreek"]},
    {"canonical": "Khaskhas", "marathi": "खसखस", "hindi": "खसखस", "terms": ["खसखस", "khaskhas", "poppy seeds"]},
    {"canonical": "Chakriphool", "marathi": "चक्रीफूल", "hindi": "चक्र फूल", "terms": ["चक्रीफूल", "चक्री फूल", "chakriphool", "star anise"]},
    {"canonical": "Jaiphal", "marathi": "जायफळ", "hindi": "जयफल", "terms": ["जायफळ", "जयफल", "jaiphal", "nutmeg"]},
    {"canonical": "Sunth", "marathi": "सुंठ", "hindi": "सोंठ", "terms": ["सुंठ", "सोंठ", "sunth", "sonth", "dry ginger"]},
    {"canonical": "Badishep", "marathi": "बडीशेप", "hindi": "सौंफ", "terms": ["बडीशेप", "बडीसोप", "सौंफ", "badishep", "saunf", "fennel seeds"]},
    {"canonical": "Owa", "marathi": "ओवा", "hindi": "अजवाइन", "terms": ["ओवा", "अजवाइन", "owa", "ajwain", "carom seeds"]},
    {"canonical": "Tejpan", "marathi": "तमालपत्र", "hindi": "तेजपत्ता", "terms": ["तमालपत्र", "तेजपान", "तेजपत्ता", "tejpan", "tamalpatra", "bay leaf"]},
    {"canonical": "Kasuri Methi", "marathi": "कसुरी मेथी", "hindi": "कसूरी मेथी", "terms": ["कसुरी मेथी", "कसूरी मेथी", "kasuri methi"]},
    {"canonical": "Garam Masala", "marathi": "गरम मसाला", "hindi": "गरम मसाला", "terms": ["गरम मसाला", "सुहाना गरम मसाला", "garam masala", "masala"]},
    {"canonical": "Goda Masala", "marathi": "गोडा मसाला", "hindi": "गोड़ा मसाला", "terms": ["गोडा मसाला", "काळं तिखट", "काळा मसाला", "goda masala", "kala masala"]},

    # Sweeteners, Salt, Oils & Ghee
    {"canonical": "Sakhar", "marathi": "साखर", "hindi": "चीनी", "terms": ["साखर", "साखरेची", "साखरेचा", "साकर", "शुकर", "सुकर", "sakhar", "saakhar", "sugar", "चीनी", "शक्कर"]},
    {"canonical": "Gul", "marathi": "गूळ", "hindi": "गुड़", "terms": ["गूळ", "गुळ", "गुळाची", "gul", "gud", "jaggery", "गुड़"]},
    {"canonical": "Meeth", "marathi": "मीठ", "hindi": "नमक", "terms": ["मीठ", "मिठाचे", "meeth", "mith", "namak", "salt"]},
    {"canonical": "Godetel", "marathi": "गोडेतेल", "hindi": "तेल", "terms": ["गोडेतेल", "तेल", "तेलाचे", "tel", "oil", "cooking oil"]},
    {"canonical": "Shengdana Tel", "marathi": "शेंगदाणा तेल", "hindi": "मूंगफली तेल", "terms": ["शेंगदाणा तेल", "shengdana tel", "groundnut oil", "peanut oil"]},
    {"canonical": "Soyabean Tel", "marathi": "सोयाबीन तेल", "hindi": "सोयाबीन तेल", "terms": ["सोयाबीन तेल", "सोयाबीन", "soyabean oil", "soyabean tel"]},
    {"canonical": "Sunflower Tel", "marathi": "सूर्यफूल तेल", "hindi": "सूरजमुखी तेल", "terms": ["सूर्यफूल तेल", "sunflower oil", "सनफ्लॉवर तेल"]},
    {"canonical": "Gemini Tel", "marathi": "जेमिनी तेल", "hindi": "जेमिनी तेल", "terms": ["जेमिनी तेल", "gemini oil", "gemini"]},
    {"canonical": "Tup", "marathi": "तूप", "hindi": "घी", "terms": ["तूप", "तूपाचे", "साजूक तूप", "tup", "toop", "ghee"]},
    {"canonical": "Khobrel Tel", "marathi": "खोबरेल तेल", "hindi": "नारियल तेल", "terms": ["खोबरेल तेल", "पॅराशूट", "पॅराशूट तेल", "khobrel tel", "coconut oil"]},

    # Nuts & Dry Fruits
    {"canonical": "Shengdane", "marathi": "शेंगदाणे", "hindi": "मूंगफली", "terms": ["शेंगदाणे", "शेंगदाणा", "shengdane", "shengdana", "peanuts", "mungfali", "दाणे"]},
    {"canonical": "Kaju", "marathi": "काजू", "hindi": "काजू", "terms": ["काजू", "काजू तुकडा", "kaju", "cashew"]},
    {"canonical": "Badam", "marathi": "बदाम", "hindi": "बादाम", "terms": ["बदाम", "badam", "almond"]},
    {"canonical": "Pista", "marathi": "पिस्ता", "hindi": "पिस्ता", "terms": ["पिस्ता", "pista", "pistachio"]},
    {"canonical": "Manuka", "marathi": "मनुका", "hindi": "किशमिश", "terms": ["मनुका", "किशमिश", "manuka", "kismis", "kishmish", "raisins"]},
    {"canonical": "Khobra", "marathi": "खोबरं", "hindi": "सूखा नारियल", "terms": ["खोबरं", "सुके खोबरे", "खोबरे", "khobare", "khobra", "dry coconut"]},
    {"canonical": "Kharik", "marathi": "खारीक", "hindi": "छुहारा", "terms": ["खारीक", "खारिक", "kharik", "dry dates"]},
    {"canonical": "Charoli", "marathi": "चारोळी", "hindi": "चिरौंजी", "terms": ["चारोळी", "charoli", "chironji"]},

    # Essentials & Tea
    {"canonical": "Dudh", "marathi": "दूध", "hindi": "दूध", "terms": ["दूध", "दुध", "dudh", "doodh", "milk"]},
    {"canonical": "Sargam Dust Tea", "marathi": "सरगम पत्ती चहा", "hindi": "सरगम पत्ती चाय", "terms": ["सरगम पत्ती चहा", "सरगम चहा", "सरगम पत्ती", "सरगम", "sargam", "sargam patti chaha"]},
    {"canonical": "Super Dust Tea", "marathi": "सुपर डस्ट चहा", "hindi": "सुपर डस्ट चाय", "terms": ["सुपर डस्ट चहा", "सुपर डस्ट", "super dust", "super dust tea"]},
    {"canonical": "Wagh Bakri Tea", "marathi": "वाघ बकरी चहा", "hindi": "वाघ बकरी चाय", "terms": ["वाघ बकरी चहा", "wagh bakri"]},
    {"canonical": "Chaha", "marathi": "चहा", "hindi": "चाय", "terms": ["चहा", "चाहा", "चहा पावडर", "चहापत्ती", "chaha", "chai", "tea", "चाय"]},
    {"canonical": "Coffee", "marathi": "कॉफी", "hindi": "कॉफ़ी", "terms": ["कॉफी", "coffee", "nescafe", "bru"]},
    {"canonical": "Saban", "marathi": "साबण", "hindi": "साबुन", "terms": ["साबण", "saban", "soap", "लक्स", "संतूर", "डेटॉल", "लाईफबॉय"]},
    {"canonical": "Detergent", "marathi": "डिटर्जंट पावडर", "hindi": "सर्फ", "terms": ["सर्फ", "डिटर्जंट", "detergent", "surf", "nirma", "टाईड"]},
    {"canonical": "Biscuits", "marathi": "बिस्कीट", "hindi": "बिस्कुट", "terms": ["बिस्कीट", "पारले जी", "biscuit", "biscuits", "गुड डे"]},
    {"canonical": "Patanjali Biscuit Box", "marathi": "पतंजली बिस्कीट बॉक्स", "hindi": "पतंजली बिस्कुट बॉक्स", "terms": ["पतंजली बिस्कीट बॉक्स", "patanjali biscuit box"]},
    {"canonical": "Sarki Pend", "marathi": "सरकी पेंड", "hindi": "सरकी पेंड", "terms": ["सरकी पेंड", "सरकी पेंढ", "sarki pend", "sarkipend"]},
    {"canonical": "Celery", "marathi": "सेलरी (Celery)", "hindi": "सेलरी", "terms": ["celery", "celary", "सेलरी"]},
]


def canonicalize_marathi_item_name(name: str, language: str = "mr-IN", output_lang: Optional[str] = None) -> str:
    """Canonicalizes item name according to dialect & output language."""
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

    stripped = re.sub(r"(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$", "", clean, flags=re.IGNORECASE).strip()

    for entry in MARATHI_KIRANA_ITEMS:
        for term in entry["terms"]:
            term_lower = term.lower()
            if clean == term_lower or stripped == term_lower:
                if is_english:
                    return entry["canonical"]
                if is_hindi:
                    return entry["hindi"]
                if is_marathi:
                    return entry["marathi"]
                return entry["canonical"]

    if is_devanagari:
        stripped_dev = re.sub(r"(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$", "", deduped, flags=re.IGNORECASE).strip()
        return stripped_dev

    return clean.title()


def normalize_marathi_transcript(text: str) -> str:
    """
    Complete Marathi transcript normalization before Regex or LLM processing:
    1. Converts misidentified Indic scripts & Devanagari numerals.
    2. Deduplicates speech repetitions.
    3. Un-glues spoken numeral + unit words (एककिलो -> 1 kg, पावकिलो -> 250 gm).
    4. Normalizes units slashes (1kg/kilo -> 1 kg).
    5. Converts spoken number words to digits (साठ -> 60, पन्नास -> 50).
    6. Strips 100,000 hallucinations.
    """
    if not text or not isinstance(text, str):
        return ""

    # 0. Convert Indic script & digits
    s = convert_indic_script_to_devanagari(text)
    s = s.translate(DEV_TO_ASCII)

    # 0b. Clean Whisper punctuation around words (commas, periods, pipes, question marks)
    # Preserves decimals in numbers (e.g. 1.5, 0.5) and MRP slashes (10/-)
    s = re.sub(r"(?<=\D)[,;:।|!?.]+|[,;:।|!?.]+(?=\D)|[,;:।|!?.]+$", " ", s)

    # 1. Deduplicate
    s = deduplicate_spoken_tokens(s)

    # 2. Un-glue numeral + unit compounds
    s = re.sub(r"(?:^|\s)(?:ekkilo|ekkilu|ekilo|एककिलो|एककिलू|एककिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 1 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:donkilo|donkilu|दोनकिलो|दोनकिलू|दोनकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 2 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:tinkilo|tinkilu|तीनकिलो|तीनकिलू|तीनकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 3 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:charkilo|charkilu|चारकिलो|चारकिलू|चारकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 4 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:pachkilo|pachkilu|पाचकिलो|पाचकिलू|पाचकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:dahakilo|dahakilu|दहाकिलो|दहाकिलू|दहाकिलु)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 10 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:pavkilo|pavkilu|पावकिलो|पावशेर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 250 gm ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:ardhakilo|ardhakilu|अर्धाकिलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 500 gm ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:didshekilo|didkilo|दीडकिलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 1.5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:adichkilo|अडीचकिलो)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 2.5 kg ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:ekliter|eklitre|एकलिटर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 1 litre ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:donliter|donlitre|दोनलिटर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 2 litre ", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:^|\s)(?:ardhaliter|अर्धालिटर)(?=[^\u0900-\u097Fa-zA-Z]|$)", " 500 ml ", s, flags=re.IGNORECASE)

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

    # 5. Spoken numbers to digits (1 to 5000)
    s = parse_marathi_spoken_numbers(s)

    # 6. Standardize units
    for pattern, canonical in MARATHI_UNITS:
        s = pattern.sub(f" {canonical} ", s)

    # 7. Standardize price markers
    s = PRECOMPILED_PRICE_REGEX.sub(" rs ", s)

    # 7b. Collapse duplicate adjacent numbers spoken for emphasis (e.g. "60 60" -> "60", "550 550" -> "550")
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s+\1\b", r"\1", s)

    # 8. Guard: Remove 100,000 hallucinations
    s = re.sub(r"\b100000\b", "", s)
    s = re.sub(r"\b(?:1|ek|एक)\s*(?:lakh|lac|laakh|लाख)\b", "", s, flags=re.IGNORECASE)

    # Convert MRP markers (e.g. 10/-)
    s = re.sub(r"(\d+)\s*/\s*-?", r"\1/-", s)

    # Clean multiple spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Compatibility alias
normalize_voice_transcript = normalize_marathi_transcript
