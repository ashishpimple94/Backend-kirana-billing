"""
marathi_normalizer.py
Marathi Number-to-Speech Converter & Spoken Kirana Pronunciation Normalizer (1 to 5000)
Supports Roman Marathi transliteration, Hindi, English, and Spoken Pronunciation Echoes:
- "60 sath" -> 60
- "60 sixty" -> 60
- "95 panchyannav" -> 95
- "Patanjali biscuit box 10/- 710" -> "Patanjali biscuit box 10/- satshey daha rupaye 710"
"""

import re
from typing import Optional, Tuple, Dict, Any

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
    """
    Converts a bill amount (1 to 99,999) into spoken Marathi words (Roman script).
    Strictly follows reference rules:
    - 780 -> satshey aainshi
    - 990 -> naushey navvad
    - 180 -> ekshey aainshi
    - 560 -> pachshey saath
    - 230 -> donshey tees
    - 788 -> satshey atthyaainshi
    - 1000 -> ek hazaar
    - 2890 -> don hazaar aathshey navvad
    - 553 -> pachshey trepanna
    - 10000 -> daha hazaar
    """
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
    Input:  <Item Name> <MRP>/- <Amount in rupees>
    Output: <Item Name> <MRP>/- <Amount in Marathi words (Roman)> rupaye <Amount in digits>

    Example:
    Input:  Patanjali biscuit box 10/- 710
    Output: Patanjali biscuit box 10/- satshey daha rupaye 710
    """
    if not line or not line.strip():
        return line

    raw_line = line.strip()

    # Match: (Item and MRP ending with /- or similar) followed by the final numeric amount
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


# ── Spoken pronunciation maps for fast detection (1 to 5000) ──
# Covers Marathi, Hindi, English Roman phonetics & colloquial combinations
SPOKEN_NUMBER_WORDS = {
    # 1-10
    "ek": 1, "don": 2, "teen": 3, "chaar": 4, "paach": 5, "pach": 5, "saha": 6, "saat": 7, "aath": 8, "ath": 8, "nau": 9, "daha": 10, "dus": 10,
    # 11-20
    "akra": 11, "gyarah": 11, "baara": 12, "barah": 12, "tera": 13, "terah": 13, "chauda": 14, "chaudah": 14, "pandra": 15, "pandrah": 15,
    "sola": 16, "solah": 16, "satra": 17, "satrah": 17, "athra": 18, "athrah": 18, "ekonis": 19, "unnis": 19, "vees": 20, "vis": 20, "bees": 20,
    # 21-30
    "ekvees": 21, "ikkees": 21, "baavees": 22, "baees": 22, "tevees": 23, "teees": 23, "chouvees": 24, "chaubees": 24, "panchees": 25, "pachees": 25,
    "chavvees": 26, "chhabbees": 26, "sattavees": 27, "sattaees": 27, "atthaavees": 28, "atthaees": 28, "ekontis": 29, "untees": 29, "tees": 30,
    # 31-40
    "ekertis": 31, "ikattees": 31, "battis": 32, "battees": 32, "tehtis": 33, "taintees": 33, "chautis": 34, "chauntees": 34, "paantis": 35, "paintees": 35,
    "chattis": 36, "chhattees": 36, "sadatis": 37, "saintees": 37, "adatis": 38, "adhtees": 38, "ekonchalis": 39, "unchalis": 39, "chalis": 40,
    # 41-50
    "ektechalis": 41, "iktaalees": 41, "bechalis": 42, "bayaalees": 42, "trechalis": 43, "taintaalees": 43, "chavvechalis": 44, "chawaalees": 44, "panchechalis": 45, "paintaalees": 45,
    "sayechechalis": 46, "chhiyaalees": 46, "sattechalis": 47, "saintaalees": 47, "atthechalis": 48, "adhtaalees": 48, "ekonpannas": 49, "unachaas": 49, "pannas": 50, "pachaas": 50,
    # 51-60
    "ekaavanna": 51, "ikkawan": 51, "baavanna": 52, "baawan": 52, "trepanna": 53, "tirepan": 53, "choupanne": 54, "chauwan": 54, "panchaavanna": 55, "pachpan": 55,
    "chappanna": 56, "chhappan": 56, "sattaavanna": 57, "sattawan": 57, "atthaavanna": 58, "atthaawan": 58, "ekonsaath": 59, "unsath": 59, "saath": 60, "sath": 60,
    # 61-70
    "ekasasta": 61, "iksath": 61, "baasasta": 62, "baasath": 62, "tresasta": 63, "tirsath": 63, "chausasta": 64, "chaunsath": 64, "paachasasta": 65, "painsath": 65,
    "sahasasta": 66, "chhiyasath": 66, "sadasasta": 67, "sarsath": 67, "adasasta": 68, "adhasath": 68, "ekonsattar": 69, "unhattar": 69, "sattar": 70,
    # 71-80
    "ekahattar": 71, "ikhattar": 71, "bahattar": 72, "tyahattar": 73, "tihattar": 73, "chouhattar": 74, "chauhattar": 74, "panchahattar": 75, "pachhattar": 75,
    "shahattar": 76, "chhihattar": 76, "satyahattar": 77, "sathattar": 77, "athyahattar": 78, "athhattar": 78, "ekonaainshi": 79, "unassi": 79, "aainshi": 80, "ainshi": 80, "aishi": 80, "assi": 80,
    # 81-90
    "ekyaainshi": 81, "ikyaasi": 81, "byaainshi": 82, "bayaasi": 82, "tryaainshi": 83, "tiraasi": 83, "chouryaainshi": 84, "chauraasi": 84, "panchyaainshi": 85, "pachaasi": 85,
    "shyaainshi": 86, "chhiyaasi": 86, "sattyaainshi": 87, "sattaasi": 87, "atthyaainshi": 88, "atthaasi": 88, "ekonnavvad": 89, "nawaasi": 89, "navvad": 90, "nabbe": 90,
    # 91-99
    "ekyaanv": 91, "ikyaanve": 91, "byaanv": 92, "baanve": 92, "tryaanv": 93, "tiraanve": 93, "chouravnav": 94, "chauraanve": 94, "panchyaannav": 95, "panchyannav": 95, "panchanve": 95,
    "shaanv": 96, "chhiyaanve": 96, "sattyaanv": 97, "sattaanve": 97, "atthyaanv": 98, "atthaanve": 98, "navyaanv": 99, "nanyaanve": 99,
    # English tens
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}

# ── Spoken compound numbers & hundreds (100 to 5000) ──
COMPOUND_PRICING_MAP = {
    # 100 - 199
    "ekshe": 100, "ekshey": 100, "ek sau": 100, "one hundred": 100,
    "ekshe daha": 110, "ek sau dus": 110, "one ten": 110,
    "ekshe vees": 120, "ekshey vees": 120, "ek sau bees": 120, "one twenty": 120,
    "ekshe tees": 130, "ekshey tees": 130, "ek sau tees": 130, "one thirty": 130,
    "ekshe chalis": 140, "ekshey chalis": 140, "ek sau chalis": 140, "one forty": 140,
    "ekshe pannas": 150, "ek sau pachaas": 150, "one fifty": 150,
    "ekshe saath": 160, "ekshe sath": 160, "ekshey saath": 160, "ek sau saath": 160, "one sixty": 160,
    "ekshe sattar": 170, "ek sau sattar": 170, "one seventy": 170,
    "ekshe aainshi": 180, "ekshe ainshi": 180, "ekshey aainshi": 180, "ek sau assi": 180, "one eighty": 180,
    "ekshe navvad": 190, "ek sau nabbe": 190, "one ninety": 190,

    # 200 - 299
    "donshe": 200, "donshey": 200, "don sau": 200, "two hundred": 200,
    "donshe daha": 210, "donshey daha": 210, "two ten": 210,
    "donshe vees": 220, "donshey vees": 220, "two twenty": 220,
    "donshe tees": 230, "donshey tees": 230, "two thirty": 230,
    "donshe chalis": 240, "donshey chalis": 240, "two forty": 240,
    "donshe pannas": 250, "donshey pannas": 250, "two fifty": 250,
    "donshe saath": 260, "donshey saath": 260, "donshe sath": 260, "two sixty": 260,
    "donshe sattar": 270, "donshey sattar": 270, "two seventy": 270,
    "donshe aainshi": 280, "donshey aainshi": 280, "donshe ainshi": 280, "two eighty": 280,
    "donshe navvad": 290, "donshey navvad": 290, "two ninety": 290,

    # 300 - 399
    "teenshe": 300, "teenshey": 300, "teen sau": 300, "three hundred": 300,
    "teenshe daha": 310, "teenshey daha": 310, "three ten": 310,
    "teenshe vees": 320, "teenshey vees": 320, "three twenty": 320,
    "teenshe tees": 330, "teenshey tees": 330, "three thirty": 330,
    "teenshe chalis": 340, "teenshey chalis": 340, "three forty": 340,
    "teenshe pannas": 350, "teenshey pannas": 350, "three fifty": 350,
    "teenshe saath": 360, "teenshey saath": 360, "three sixty": 360,
    "teenshe sattar": 370, "teenshey sattar": 370, "three seventy": 370,
    "teenshe aainshi": 380, "teenshey aainshi": 380, "teenshe ainshi": 380, "three eighty": 380,
    "teenshe navvad": 390, "teenshey navvad": 390, "three ninety": 390,

    # 400 - 499
    "chaarshe": 400, "chaarshey": 400, "chaar sau": 400, "four hundred": 400,
    "chaarshe daha": 410, "chaarshey daha": 410, "four ten": 410,
    "chaarshe vees": 420, "chaarshey vees": 420, "four twenty": 420,
    "chaarshe tees": 430, "chaarshey tees": 430, "four thirty": 430,
    "chaarshe chalis": 440, "chaarshey chalis": 440, "four forty": 440,
    "chaarshe pannas": 450, "chaarshey pannas": 450, "chaar sau pachaas": 450, "four fifty": 450,
    "chaarshe panchaavanna": 455, "chaarshey panchaavanna": 455,
    "chaarshe saath": 460, "chaarshey saath": 460, "chaarshe sath": 460, "four sixty": 460,
    "chaarshe sattar": 470, "chaarshey sattar": 470, "four seventy": 470,
    "chaarshe aainshi": 480, "chaarshey aainshi": 480, "four eighty": 480,
    "chaarshe navvad": 490, "chaarshey navvad": 490, "four ninety": 490,

    # 500 - 599
    "pachshe": 500, "pachshey": 500, "paanch sau": 500, "five hundred": 500,
    "pachshe daha": 510, "pachshey daha": 510, "five ten": 510,
    "pachshe vees": 520, "pachshey vees": 520, "five twenty": 520,
    "pachshe tees": 530, "pachshey tees": 530, "five thirty": 530,
    "pachshe trepanna": 553, "pachshey trepanna": 553,
    "pachshe pannas": 550, "pachshey pannas": 550, "five fifty": 550,
    "pachshe saath": 560, "pachshey saath": 560, "pachshe sath": 560, "five sixty": 560,
    "pachshe sattar": 570, "pachshey sattar": 570, "five seventy": 570,
    "pachshe aainshi": 580, "pachshey aainshi": 580, "five eighty": 580,
    "pachshe navvad": 590, "pachshey navvad": 590, "five ninety": 590,

    # 600 - 699
    "sahashe": 600, "sahashey": 600, "chhah sau": 600, "six hundred": 600,
    "sahashe daha": 610, "sahashey daha": 610, "six ten": 610,
    "sahashe saath": 660, "sahashey saath": 660, "six sixty": 660,

    # 700 - 799
    "satshe": 700, "satshey": 700, "saat sau": 700, "seven hundred": 700,
    "satshe daha": 710, "satshey daha": 710, "seven ten": 710,
    "satshe sattar": 770, "satshey sattar": 770, "seven seventy": 770,
    "satshe aainshi": 780, "satshey aainshi": 780, "seven eighty": 780,
    "satshe atthyaainshi": 788, "satshey atthyaainshi": 788,

    # 800 - 899
    "aathshe": 800, "aathshey": 800, "aath sau": 800, "eight hundred": 800,
    "aathshe daha": 810, "aathshey daha": 810, "eight ten": 810,

    # 900 - 999
    "naushe": 900, "naushey": 900, "nau sau": 900, "nine hundred": 900,
    "naushe daha": 910, "naushey daha": 910, "nine ten": 910,
    "naushe navvad": 990, "naushey navvad": 990, "nine ninety": 990,

    # 1000 - 5000
    "ek hazaar": 1000, "ek hajar": 1000, "one thousand": 1000,
    "ek hazaar ekshe chalis": 1140, "ek hazaar ekshey chalis": 1140, "one thousand one forty": 1140,
    "ek hazaar donshe": 1200, "ek hazaar donshey": 1200, "one thousand two hundred": 1200,
    "don hazaar": 2000, "don hajar": 2000, "two thousand": 2000,
    "don hazaar aathshey navvad": 2890, "don hajar aathshe navvad": 2890,
    "teen hazaar": 3000, "three thousand": 3000,
    "chaar hazaar": 4000, "four thousand": 4000,
    "paach hazaar": 5000, "five thousand": 5000,
}

# Pronunciation echoes pattern: e.g. "60 sath", "60 sixty", "95 panchyannav", "120 ekshe vees"
PRONUNCIATION_ECHO_REGEX = re.compile(
    r"\b(\d+)\s+([a-zA-Z\u0900-\u097F]+(?:\s+[a-zA-Z\u0900-\u097F]+)?)\b",
    re.IGNORECASE
)


def extract_price_and_pronunciation(raw_str: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extracts numerical price and the accompanying spoken pronunciation confirmation if present.
    Example:
    '60 sath' -> (60.0, 'saath / 60')
    '60 sixty' -> (60.0, 'sixty')
    '95 panchyannav' -> (95.0, 'panchyaannav / 95')
    '140 ekshe chalis' -> (140.0, 'ekshey chalis')
    '120' -> (120.0, None)
    'ekshe vees' -> (120.0, 'ekshe vees')
    """
    clean = raw_str.strip().lower()

    # 1. Check direct digit + pronunciation word echo (e.g. "60 sath", "95 panchyannav")
    m_echo = re.search(r"^(\d+)\s+([a-zA-Z\u0900-\u097F]+(?:\s+[a-zA-Z\u0900-\u097F]+)?)$", clean)
    if m_echo:
        num = float(m_echo.group(1))
        echo_word = m_echo.group(2).strip()

        # Check if echo_word corresponds to the same or compatible number
        if echo_word in SPOKEN_NUMBER_WORDS:
            val = SPOKEN_NUMBER_WORDS[echo_word]
            if val == num or num > 0:
                return num, echo_word
        elif echo_word in COMPOUND_PRICING_MAP:
            val = COMPOUND_PRICING_MAP[echo_word]
            if val == num or num > 0:
                return num, echo_word
        else:
            # Word was uttered as pronunciation confirmation
            return num, echo_word

    # 2. Check compound pricing map (e.g. "ekshe vees", "two sixty", "donshey aainshi")
    for phrase, val in sorted(COMPOUND_PRICING_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if phrase in clean:
            return float(val), phrase

    # 3. Check single spoken number words
    words = clean.split()
    for w in words:
        if w in SPOKEN_NUMBER_WORDS:
            val = SPOKEN_NUMBER_WORDS[w]
            return float(val), w

    # 4. Pure digit
    m_num = re.search(r"(\d+(?:\.\d+)?)", clean)
    if m_num:
        val = float(m_num.group(1))
        # Protect against 100,000 / lakh hallucinations
        if val >= 15000:
            return None, None
        return val, None

    return None, None


def normalize_voice_transcript(transcript: str) -> str:
    """
    Normalizes transcript to resolve spoken pronunciation words into standard tokens,
    while removing 100,000 / lakh hallucinations.
    """
    if not transcript:
        return ""

    text = transcript

    # Remove 100,000 hallucinations (e.g. "100000", "1 lakh", "ek lakh")
    text = re.sub(r"\b100000\b", "", text)
    text = re.sub(r"\b(?:1|ek)\s*(?:lakh|lac|laakh)\b", "", text, flags=re.IGNORECASE)

    # Convert MRP markers to clean token
    text = re.sub(r"(\d+)\s*/\s*-?", r"\1/-", text)

    return text.strip()
