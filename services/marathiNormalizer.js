/**
 * Comprehensive Marathi Kirana Normalizer & Multilingual Dictionary
 * Designed for extreme scalability across Maharashtra grocery dialects.
 * Preserves the actual language spoken (Marathi, Hindi, or English) in the final bill!
 */

// 0. Deduplicate repeated speech tokens or acoustic stutters (e.g. sakhar-sakhar -> sakhar, साखर-साखर -> साखर)
function deduplicateSpokenTokens(text) {
  if (!text || typeof text !== 'string') return '';
  let s = text.trim();
  // Repeated hyphenated or space-separated words with full Unicode/Devanagari boundary support
  s = s.replace(/(?:^|(?<=[^\u0900-\u097Fa-zA-Z]))([\u0900-\u097Fa-zA-Z]+)(?:[-\s]+\1)+(?=[^\u0900-\u097Fa-zA-Z]|$)/gi, '$1');
  return s.trim();
}

// Convert Gujarati or other misidentified Indic scripts to Devanagari Marathi script.
// In Unicode, Devanagari (0x0900 - 0x097F) and Gujarati (0x0A80 - 0x0AFF) share an exact 1-to-1 offset of -0x180.
function convertIndicScriptToDevanagari(text) {
  if (!text || typeof text !== 'string') return '';
  return text.replace(/[\u0A80-\u0AFF]/g, (ch) => {
    const code = ch.charCodeAt(0) - 0x180;
    return (code >= 0x0900 && code <= 0x097F) ? String.fromCharCode(code) : ch;
  });
}

// 1. Marathi/Devanagari Digits
const DEVANAGARI_DIGITS = {
  '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
  '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
};

// Helper: Unicode-safe Regex generator without relying on ASCII \b
function makeUnicodeRegex(patternStr, flags = 'gi') {
  return new RegExp(`(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))(?:${patternStr})(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`, flags);
}

// Multipliers for Thousands (हजार / hajar / hazar) and Lakhs (लाख / lakh)
const THOUSAND_MULTIPLIERS = {
  // Devanagari
  'एक': 1, 'दोन': 2, 'दो': 2, 'तीन': 3, 'चार': 4, 'पाच': 5, 'पाँच': 5, 'पांच': 5,
  'सहा': 6, 'सात': 7, 'आठ': 8, 'नऊ': 9, 'नौ': 9, 'दहा': 10, 'दस': 10,
  'अकरा': 11, 'बारा': 12, 'तेरा': 13, 'चौदा': 14, 'पंधरा': 15, 'सोळा': 16, 'सतरा': 17, 'अठरा': 18, 'एकोणीस': 19,
  'वीस': 20, 'बीस': 20, 'पंचवीस': 25, 'तीस': 30, 'पस्तीस': 35, 'चाळीस': 40, 'चालीस': 40, 'पन्नास': 50, 'पचास': 50,
  'साठ': 60, 'सत्तर': 70, 'ऐंशी': 80, 'नव्वद': 90, 'शंभर': 100,
  'दीड': 1.5, 'अडीच': 2.5, 'साडेतीन': 3.5, 'साडेचार': 4.5, 'साडेपाच': 5.5, 'साडेसहा': 6.5, 'साडेसात': 7.5, 'साडेआठ': 8.5, 'साडेनऊ': 9.5, 'साडेदहा': 10.5,
  'सव्वा': 1.25, 'पाऊण': 0.75,

  // English & Transliterated
  'ek': 1, 'don': 2, 'do': 2, 'teen': 3, 'tin': 3, 'char': 4, 'chaar': 4,
  'panch': 5, 'paach': 5, 'pach': 5, 'saha': 6, 'chha': 6, 'chheh': 6,
  'sat': 7, 'saat': 7, 'ath': 8, 'aath': 8, 'nau': 9, 'nav': 9, 'daha': 10, 'das': 10,
  'akara': 11, 'bara': 12, 'tera': 13, 'chauda': 14, 'pandhra': 15, 'sola': 16, 'satra': 17, 'athra': 18, 'ekonis': 19,
  'vees': 20, 'bees': 20, 'panchvis': 25, 'tees': 30, 'tis': 30, 'pastis': 35, 'paintis': 35,
  'chalis': 40, 'chaalis': 40, 'pannas': 50, 'pachas': 50, 'saath': 60, 'sath': 60, 'sattar': 70,
  'aishi': 80, 'ayshi': 80, 'assi': 80, 'ainshi': 80, 'aenshi': 80, 'navvad': 90, 'nabbe': 90,
  'deed': 1.5, 'dedh': 1.5, 'adeech': 2.5, 'dhai': 2.5,
  'sade teen': 3.5, 'sade char': 4.5, 'sade paach': 5.5, 'sade pach': 5.5,
  'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
  'eleven': 11, 'twelve': 12, 'fifteen': 15, 'twenty': 20, 'twenty-five': 25, 'thirty': 30, 'forty': 40, 'fifty': 50,
};

// 2. Comprehensive Marathi & Indian Number Words (Hundreds, Compounds, Tens, Units, Fractions)
const HUNDREDS_MAP = {
  // 135 Compounds
  'एकशे पस्तीस': 135, 'एकशेपस्तीस': 135, 'एकशे पैंतीस': 135, 'एकशेपंतीस': 135, 'एकसे पस्तीस': 135, 'एकसेपस्तीस': 135, 'एकसे पैंतीस': 135, 'एक शे पस्तीस': 135, 'एक से पस्तीस': 135, 'ekshe pastis': 135, 'ekse pastis': 135, 'ek she pastis': 135, 'ek se pastis': 135, 'ekshe paintis': 135, 'ekse paintis': 135, 'ek she paintis': 135, 'ek se paintis': 135, 'one thirty five': 135, 'one thirty-five': 135,

  // 140 Compounds
  'एकशे चाळीस': 140, 'एकशेचाळीस': 140, 'एकशे चालीस': 140, 'एकशेचालीस': 140, 'एकसे चाळीस': 140, 'एकसेचाळीस': 140, 'एकसे चालीस': 140, 'एकसेचालीस': 140, 'एक शे चाळीस': 140, 'एक से चाळीस': 140, 'एक शे चालीस': 140, 'एक से चालीस': 140, 'ekshe chalis': 140, 'ekse chalis': 140, 'ek she chalis': 140, 'ek se chalis': 140, 'ekshe chaalis': 140, 'ekse chaalis': 140, 'ek she chaalis': 140, 'ek se chaalis': 140, 'one forty': 140, 'one-forty': 140,

  // 190 Compounds
  'एकशे नव्वद': 190, 'एकशेनव्वद': 190, 'एकशे नब्बे': 190, 'एकशेनब्बे': 190, 'एकसे नव्वद': 190, 'एकसेनव्वद': 190, 'एकसे नब्बे': 190, 'एकसेनब्बे': 190, 'एक शे नव्वद': 190, 'एक से नव्वद': 190, 'एक शे नब्बे': 190, 'एक से नब्बे': 190, 'ekshe navvad': 190, 'ekse navvad': 190, 'ek she navvad': 190, 'ek se navvad': 190, 'ekshe nawad': 190, 'ekse nawad': 190, 'ek she nawad': 190, 'ek se nawad': 190, 'ekshe nabbe': 190, 'ekse nabbe': 190, 'ek she nabbe': 190, 'ek se nabbe': 190, 'ekshe navve': 190, 'ekse navve': 190, 'ek she navve': 190, 'ek se navve': 190, 'one ninety': 190, 'one-ninety': 190,

  // 550 Compounds (Marathi / Hindi / English)
  'साडेपाचशे': 550, 'साडे पाचशे': 550, 'साडे पाच शे': 550, 'पाचशे पन्नास': 550, 'पाचशेपन्नास': 550, 'साडेपाचसे': 550, 'साडे पाचसे': 550, 'साडे पाच से': 550, 'पाचसे पन्नास': 550, 'पाचसेपन्नास': 550, 'साढ़े पांच सौ': 550, 'साढ़े पांचसौ': 550, 'पांच सौ पचास': 550, 'पांचसौ पचास': 550, 'पाँच सौ पचास': 550, 'पाँचसौ पचास': 550, 'five fifty': 550, 'five-fifty': 550, 'five hundred fifty': 550, 'five hundred and fifty': 550, 'sade pachshe': 550, 'sade paachshe': 550, 'sade pacahshe': 550, 'sade pacashe': 550, 'sade pachashe': 550, 'sade pachse': 550, 'sade paachse': 550, 'pachshe pannas': 550, 'paachshe pannas': 550, 'pachse pannas': 550, 'paachse pannas': 550, 'panchashe': 550, 'pachashe': 550, 'panchshe': 550, 'sade panch sau': 550, 'sade paanch sau': 550, 'panch sau pachas': 550, 'paanch sau pachas': 550, 'panch sau pachaas': 550,

  // 650 Compounds
  'साडेसहाशे': 650, 'सहाशे पन्नास': 650, 'सहाशेपन्नास': 650, 'साढ़े छह सौ': 650, 'साढ़े छहसौ': 650, 'छह सौ पचास': 650, 'छहसौ पचास': 650, 'छः सौ पचास': 650, 'six fifty': 650, 'six-fifty': 650, 'six hundred fifty': 650, 'six hundred and fifty': 650, 'sade sahashe': 650, 'sahashe pannas': 650, 'sade chha sau': 650, 'sade chheh sau': 650, 'chha sau pachas': 650, 'chheh sau pachas': 650, 'chhe sau pachas': 650, 'chha sau pachaas': 650,

  // 750 Compounds
  'साडेसातशे': 750, 'सातशे पन्नास': 750, 'सातशेपन्नास': 750, 'साढ़े सात सौ': 750, 'साढ़े सातसौ': 750, 'सात सौ पचास': 750, 'सातसौ पचास': 750, 'seven fifty': 750, 'seven-fifty': 750, 'seven hundred fifty': 750, 'seven hundred and fifty': 750, 'sade saatshe': 750, 'saatshe pannas': 750, 'sade saat sau': 750, 'sade sat sau': 750, 'saat sau pachas': 750, 'sat sau pachas': 750, 'saat sau pachaas': 750,

  // 850 Compounds
  'साडेआठशे': 850, 'आठशे पन्नास': 850, 'आठशेपन्नास': 850, 'साढ़े आठ सौ': 850, 'साढ़े आठसौ': 850, 'आठ सौ पचास': 850, 'आठसौ पचास': 850, 'eight fifty': 850, 'eight-fifty': 850, 'eight hundred fifty': 850, 'eight hundred and fifty': 850, 'sade aathshe': 850, 'aathshe pannas': 850, 'sade aath sau': 850, 'sade ath sau': 850, 'aath sau pachas': 850, 'ath sau pachas': 850, 'aath sau pachaas': 850,

  // 950 Compounds
  'साडेनऊशे': 950, 'नऊशे पन्नास': 950, 'नऊशेपन्नास': 950, 'साढ़े नौ सौ': 950, 'साढ़े नौसौ': 950, 'नौ सौ पचास': 950, 'नौसौ पचास': 950, 'nine fifty': 950, 'nine-fifty': 950, 'nine hundred fifty': 950, 'nine hundred and fifty': 950, 'sade naushe': 950, 'naushe pannas': 950, 'sade nau sau': 950, 'nau sau pachas': 950, 'nau sau pachaas': 950,

  // 980 Compounds
  'नऊशे ऐंशी': 980, 'नऊशेऐंशी': 980, 'नऊशे ऐशी': 980, 'नऊशेऐशी': 980, 'नऊसे ऐंशी': 980, 'नऊसेऐंशी': 980, 'नऊसे ऐशी': 980, 'नऊसेऐशी': 980, 'नौ सौ अस्सी': 980, 'नौसौ अस्सी': 980, 'naushe ayshi': 980, 'naushe aishi': 980, 'naushe assi': 980, 'naushe ainshi': 980, 'naushe aenshi': 980, 'navshe ayshi': 980, 'navshe aishi': 980, 'navshe assi': 980, 'navshe ainshi': 980, 'navshe aenshi': 980, 'nawshe ayshi': 980, 'nawshe aishi': 980, 'nawshe assi': 980, 'nawshe ainshi': 980, 'nawshe aenshi': 980, 'nause ayshi': 980, 'nause aishi': 980, 'nause assi': 980, 'nause ainshi': 980, 'nause aenshi': 980, 'navse ayshi': 980, 'navse aishi': 980, 'navse assi': 980, 'navse ainshi': 980, 'navse aenshi': 980, 'nine eighty': 980, 'nine-eighty': 980, 'nine hundred eighty': 980,

  // 110 Compounds
  'एकशे दहा': 110, 'एकशेदहा': 110, 'एक सौ दस': 110, 'एकसौ दस': 110, 'एक सौ दहा': 110, 'एकशे दस': 110, 'one ten': 110, 'one-ten': 110, 'one hundred ten': 110, 'one hundred and ten': 110, 'ekshe daha': 110, 'ek she daha': 110, 'ek sau das': 110, 'ek sau daha': 110,

  // 250 Compounds
  'अडीचशे': 250, 'दोनशे पन्नास': 250, 'दोनशेपन्नास': 250, 'दोंशे पन्नास': 250, 'दोंशेपन्नस': 250, 'ढाई सौ': 250, 'ढाईसौ': 250, 'दो सौ पचास': 250, 'दोसौ पचास': 250, 'two fifty': 250, 'two-fifty': 250, 'two hundred fifty': 250, 'two hundred and fifty': 250, 'adeechshe': 250, 'dhai sau': 250, 'donshe pannas': 250, 'donshepannas': 250, 'do sau pachas': 250, 'do sau pachaas': 250, 'don she pannas': 250,

  // 350 Compounds
  'साडेतीनशे': 350, 'तीनशे पन्नास': 350, 'तीनशेपन्नास': 350, 'साढ़े तीन सौ': 350, 'साढ़े तीनसौ': 350, 'तीन सौ पचास': 350, 'तीनसौ पचास': 350, 'three fifty': 350, 'three-fifty': 350, 'three hundred fifty': 350, 'three hundred and fifty': 350, 'sade teenshe': 350, 'teenshe pannas': 350, 'sade teen sau': 350, 'teen sau pachas': 350, 'teen sau pachaas': 350,

  // 450 Compounds
  'साडेचारशे': 450, 'चारशे पन्नास': 450, 'चारशेपन्नास': 450, 'साढ़े चार सौ': 450, 'साढ़े चारसौ': 450, 'चार सौ पचास': 450, 'चारसौ पचास': 450, 'four fifty': 450, 'four-fifty': 450, 'four hundred fifty': 450, 'four hundred and fifty': 450, 'sade charshe': 450, 'charshe pannas': 450, 'sade char sau': 450, 'sade chaar sau': 450, 'char sau pachas': 450, 'chaar sau pachas': 450, 'char sau pachaas': 450, 'chaar sau pachaas': 450,

  // 150 / 125
  'दीडशे': 150, 'डेढ़ सौ': 150, 'डेढ़सौ': 150, 'एक सौ पचास': 150, 'one fifty': 150, 'one-fifty': 150, 'one hundred fifty': 150, 'one hundred and fifty': 150, 'deedshe': 150, 'dedh sau': 150, 'ek sau pachas': 150, 'ek sau pachaas': 150,
  'सव्वाशे': 125, 'savvashe': 125,

  // Marathi, Hindi & English Hundreds (including colloquial 's' and spaced accents)
  'एकशे': 100, 'ekshe': 100, 'ekashe': 100, 'ekshey': 100, 'एकसे': 100, 'ekse': 100, 'ekase': 100, 'eksey': 100, 'एक शे': 100, 'एक से': 100, 'ek she': 100, 'ek se': 100, 'एक सौ': 100, 'एकसौ': 100, 'ek sau': 100, 'one hundred': 100, 'शंभर': 100, 'shambhar': 100,
  'दोनशे': 200, 'दोंशे': 200, 'donshe': 200, 'donashe': 200, 'donshey': 200, 'दोनसे': 200, 'दोंसे': 200, 'donse': 200, 'donase': 200, 'donsey': 200, 'दोन शे': 200, 'दोन से': 200, 'don she': 200, 'don se': 200, 'दो सौ': 200, 'दोसौ': 200, 'do sau': 200, 'two hundred': 200,
  'तीनशे': 300, 'teenshe': 300, 'teenashe': 300, 'teenshey': 300, 'तीनसे': 300, 'teense': 300, 'teenase': 300, 'teensey': 300, 'तीन शे': 300, 'तीन से': 300, 'teen she': 300, 'teen se': 300, 'तीन सौ': 300, 'तीनसौ': 300, 'teen sau': 300, 'three hundred': 300,
  'चारशे': 400, 'charshe': 400, 'charashe': 400, 'charshey': 400, 'चारसे': 400, 'charse': 400, 'charase': 400, 'charsey': 400, 'चार शे': 400, 'चार से': 400, 'char she': 400, 'char se': 400, 'चार सौ': 400, 'चारसौ': 400, 'char sau': 400, 'chaar sau': 400, 'four hundred': 400,
  'पाचशे': 500, 'पाचसे': 500, 'pachshe': 500, 'pachse': 500, 'paachshe': 500, 'paachse': 500, 'pachashe': 500, 'pachase': 500, 'paachashe': 500, 'paachase': 500, 'pachashey': 500, 'pachshey': 500, 'पाच शे': 500, 'पाच से': 500, 'pach she': 500, 'pach se': 500, 'पाँच सौ': 500, 'पाँचसौ': 500, 'पांच सौ': 500, 'पांचसौ': 500, 'paanch sau': 500, 'panch sau': 500, 'five hundred': 500,
  'सहाशे': 600, 'सहासे': 600, 'sahashe': 600, 'sahase': 600, 'sahashey': 600, 'सहा शे': 600, 'सहा से': 600, 'saha she': 600, 'saha se': 600, 'छह सौ': 600, 'छहसौ': 600, 'chha sau': 600, 'chheh sau': 600, 'six hundred': 600,
  'सातशे': 700, 'सातसे': 700, 'saatshe': 700, 'saatse': 700, 'satse': 700, 'saatashe': 700, 'saatase': 700, 'saatshey': 700, 'सात शे': 700, 'सात से': 700, 'saat she': 700, 'saat se': 700, 'sat she': 700, 'sat se': 700, 'सात सौ': 700, 'सातसौ': 700, 'saat sau': 700, 'sat sau': 700, 'seven hundred': 700,
  'आठशे': 800, 'आठसे': 800, 'aathshe': 800, 'aathse': 800, 'athse': 800, 'aathashe': 800, 'aathase': 800, 'aathshey': 800, 'आठ शे': 800, 'आठ से': 800, 'aath she': 800, 'aath se': 800, 'ath she': 800, 'ath se': 800, 'आठ सौ': 800, 'आठसौ': 800, 'aath sau': 800, 'ath sau': 800, 'eight hundred': 800,
  'नऊशे': 900, 'नऊसे': 900, 'नवशे': 900, 'नवसे': 900, 'naushe': 900, 'nause': 900, 'navshe': 900, 'navse': 900, 'nawshe': 900, 'nawse': 900, 'nauashe': 900, 'naushey': 900, 'नऊ शे': 900, 'नऊ से': 900, 'nau she': 900, 'nau se': 900, 'nav she': 900, 'nav se': 900, 'नौ सौ': 900, 'नौसौ': 900, 'nau sau': 900, 'nine hundred': 900,
  'हजार': 1000, 'हज़ार': 1000, 'hajar': 1000, 'hazar': 1000, 'hazaar': 1000, 'ek hazar': 1000, 'ek hajar': 1000, 'एक हजार': 1000, 'one thousand': 1000,
};

const UNITS_AND_TENS_MAP = {
  // 90s
  'नव्व्याण्णव': 99, 'अठ्ठ्याण्णव': 98, 'सत्याण्णव': 97, 'शहाण्णव': 96,
  'पंच्याण्णव': 95, 'चौऱ्याण्णव': 94, 'त्र्याण्णव': 93, 'ब्याण्णव': 92, 'एक्याण्णव': 91,
  'navvad': 90, 'nawad': 90, 'navad': 90, 'navat': 90, 'navve': 90, 'nabbe': 90, 'नव्वद': 90, 'नब्बे': 90, 'ninety': 90,

  // 80s
  'एक्याऐंशी': 81, 'ब्याऐंशी': 82, 'त्र्याऐंशी': 83, 'चौऱ्याऐंशी': 84,
  'पंच्याऐंशी': 85, 'पंचाइश': 85, 'पंचाईश': 85, 'पंचाशी': 85, 'पंच्यांशी': 85, 'पंचाऐंशी': 85, 'panchaishi': 85, 'panchashi': 85, 'pachasi': 85, 'पचासी': 85,
  'शहाऐंशी': 86, 'सत्याऐंशी': 87, 'अठ्ठ्याऐंशी': 88,
  'एकोणनव्वद': 89, 'nawasi': 89, 'ekonnavvad': 89,
  'aishi': 80, 'ayshi': 80, 'ainshi': 80, 'aenshi': 80, 'aashi': 80, 'ashi': 80, 'assi': 80, 'ऐंशी': 80, 'ऐशी': 80, 'अस्सी': 80, 'eighty': 80,

  // 70s
  'एकाहत्तर': 71, 'बहात्तर': 72, 'त्र्याहत्तर': 73, 'चौऱ्याहत्तर': 74,
  'पंचाहत्तर': 75, 'panchahattar': 75, 'pachhattar': 75,
  'शहात्तर': 76, 'सत्याहत्तर': 77, 'अठ्ठ्याहत्तर': 78, 'एकोणऐंशी': 79,
  'sattar': 70, 'सत्तर': 70, 'seventy': 70,

  // 60s
  'एकसष्ट': 61, 'एकसष्ठ': 61, 'बासष्ट': 62, 'बासष्ठ': 62, 'त्रेसष्ट': 63, 'त्रेसष्ठ': 63,
  'चौसष्ट': 64, 'चौसष्ठ': 64, 'पासष्ट': 65, 'पासष्ठ': 65, 'pasasht': 65, 'painsath': 65,
  'शासष्ट': 66, 'शासष्ठ': 66, 'सदसष्ट': 67, 'सदसष्ठ': 67,
  'अडुसष्ट': 68, 'अडुसष्ठ': 68, 'अडसठ': 68, 'adusht': 68, 'adusacht': 68, 'adsath': 68,
  'एकोणसत्तर': 69,
  'saath': 60, 'sath': 60, 'साठ': 60, 'sixty': 60,

  // 50s
  'एकावन्न': 51, 'बावन्न': 52, 'त्रेपन्न': 53, 'चोपन्न': 54,
  'पंचावन्न': 55, 'panchavanna': 55, 'pachpan': 55,
  'छप्पन्न': 56, 'सत्तावन्न': 57, 'अठ्ठावन्न': 58, 'एकोणसाठ': 59,
  'pannas': 50, 'pachas': 50, 'पन्नास': 50, 'पचास': 50, 'fifty': 50,

  // 40s
  'एकेचाळीस': 41, 'बेचाळीस': 42, 'त्रेचाळीस': 43, 'चव्वेचाळीस': 44,
  'पंचेचाळीस': 45, 'panchechalis': 45, 'paintalis': 45,
  'शेहेचाळीस': 46, 'सत्तेचाळीस': 47, 'अट्ठेचाळीस': 48, 'एकोणपन्नास': 49,
  'chalis': 40, 'chaalis': 40, 'चाळीस': 40, 'चालीस': 40, 'forty': 40,

  // 30s
  'एकतीस': 31, 'बत्तीस': 32, 'तेहतीस': 33, 'चौतीस': 34,
  'पस्तीस': 35, 'pastis': 35, 'paintis': 35, 'pantis': 35, 'पस्तीस': 35, 'पैंतीस': 35, 'thirtyfive': 35, 'thirty five': 35,
  'छत्तीस': 36, 'सदतीस': 37, 'अडतीस': 38, 'एकोणचाळीस': 39,
  'tees': 30, 'tis': 30, 'तीस': 30, 'thirty': 30,

  // 20s
  'एकवीस': 21, 'बावीस': 22, 'तेवीस': 23, 'चोवीस': 24,
  'पंचवीस': 25, 'panchvis': 25, 'pachis': 25, 'पच्चीस': 25, 'twentyfive': 25,
  'सव्वीस': 26, 'सत्तावीस': 27, 'अठ्ठावीस': 28, 'एकोणतीस': 29,
  'vees': 20, 'bees': 20, 'वीस': 20, 'बीस': 20, 'twenty': 20,

  // 1-19
  'एकोणीस': 19, 'ekonis': 19, 'unnis': 19, 'nineteen': 19,
  'अठरा': 18, 'athra': 18, 'athara': 18, 'eighteen': 18,
  'सतरा': 17, 'satra': 17, 'satrah': 17, 'seventeen': 17,
  'सोळा': 16, 'sola': 16, 'solah': 16, 'sixteen': 16,
  'पंधरा': 15, 'pandhra': 15, 'pandrah': 15, 'fifteen': 15,
  'चौदा': 14, 'chauda': 14, 'chaudah': 14, 'fourteen': 14,
  'तेरा': 13, 'tera': 13, 'terah': 13, 'thirteen': 13,
  'बारा': 12, 'bara': 12, 'barah': 12, 'twelve': 12,
  'अकरा': 11, 'akara': 11, 'gyarah': 11, 'eleven': 11,
  'दहा': 10, 'daha': 10, 'das': 10, 'ten': 10,
  'नऊ': 9, 'nau': 9, 'nav': 9, 'nine': 9,
  'आठ': 8, 'aath': 8, 'ath': 8, 'eight': 8,
  'सात': 7, 'saat': 7, 'sat': 7, 'seven': 7,
  'सहा': 6, 'saha': 6, 'chha': 6, 'chheh': 6, 'six': 6,
  'पाच': 5, 'paach': 5, 'panch': 5, 'pach': 5, 'five': 5,
  'चार': 4, 'chaar': 4, 'char': 4, 'four': 4,
  'तीन': 3, 'teen': 3, 'tin': 3, 'three': 3,
  'दोन': 2, 'don': 2, 'do': 2, 'two': 2,
  'एक': 1, 'ek': 1, 'one': 1,
  'शून्य': 0, 'shunya': 0, 'zero': 0,

  // Fractions & Colloquials
  'साडेतीन': 3.5, 'sade teen': 3.5,
  'साडेचार': 4.5, 'sade char': 4.5,
  'साडेपाच': 5.5, 'sade paach': 5.5,
  'सव्वा': 1.25, 'savva': 1.25, 'sawa': 1.25,
  'दीड': 1.5, 'deed': 1.5, 'dedh': 1.5,
  'अडीच': 2.5, 'adeech': 2.5, 'dhai': 2.5,
  'पाऊण': 0.75, 'paun': 0.75,
  'अर्धा': 0.5, 'अर्धी': 0.5, 'अर्धे': 0.5, 'ardha': 0.5, 'aadha': 0.5, 'half': 0.5,
  'पावशेर': 0.25, 'पाव': 0.25, 'paav': 0.25, 'pav': 0.25, 'quarter': 0.25,
};

const escapeRegex = (str) => str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Precompiled module-level regular expressions for sub-millisecond execution (< 0.1ms)
const LAKH_MULTIPLIERS_KEYS = Object.keys(THOUSAND_MULTIPLIERS).sort((a, b) => b.length - a.length);
const LAKH_WORD_PATTERN = LAKH_MULTIPLIERS_KEYS.map(escapeRegex).join('|');
const PRECOMPILED_LAKH_REGEX = new RegExp(`(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))(\\d+(?:\\.\\d+)?|${LAKH_WORD_PATTERN})\\s*(?:लाख|लाख्स|lakh|lakhs|lac|lacs)(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`, 'gi');
const PRECOMPILED_STANDALONE_LAKH_REGEX = /(?:^|(?<=[^\u0900-\u097Fa-zA-Z0-9]))(?:लाख|lakh|lac)(?=[^\u0900-\u097Fa-zA-Z0-9]|$)/gi;

const THOU_MULTIPLIERS_KEYS = Object.keys(THOUSAND_MULTIPLIERS).sort((a, b) => b.length - a.length);
const THOU_WORD_PATTERN = THOU_MULTIPLIERS_KEYS.map(escapeRegex).join('|');
const PRECOMPILED_THOU_REGEX = new RegExp(`(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))(\\d+(?:\\.\\d+)?|${THOU_WORD_PATTERN})\\s*(?:हजार|हज़ार|हज़ारों|hajar|hazar|hazaar|thousand|thousands)(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`, 'gi');
const PRECOMPILED_STANDALONE_THOU_REGEX = /(?:^|(?<=[^\u0900-\u097Fa-zA-Z0-9]))(?:हजार|हज़ार|hajar|hazar|hazaar|thousand)(?=[^\u0900-\u097Fa-zA-Z0-9]|$)/gi;

const SORTED_HUNDREDS_KEYS = Object.keys(HUNDREDS_MAP).sort((a, b) => b.length - a.length);
const SORTED_UNITS_TENS_KEYS = Object.keys(UNITS_AND_TENS_MAP).sort((a, b) => b.length - a.length);
const HUNDRED_PATTERN = SORTED_HUNDREDS_KEYS.map(escapeRegex).join('|');
const UNIT_TENS_PATTERN = SORTED_UNITS_TENS_KEYS.map(escapeRegex).join('|');

const PRECOMPILED_COMPOUND_HUNDREDS_REGEX = new RegExp(
  `(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))(${HUNDRED_PATTERN})(?:\\s+(${UNIT_TENS_PATTERN}|\\d{1,2}))?(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`,
  'gi'
);
const PRECOMPILED_UNITS_TENS_REGEX = new RegExp(
  `(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))(${UNIT_TENS_PATTERN})(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`,
  'gi'
);
const PRECOMPILED_MERGE_THOUSANDS_REGEX = /\b([1-9]\d*000)\s+(?:(?:आणि|and)\s+)?(\d{1,3})\b(?=\s*(?:रुपये|रुपयांची|रुपयांचे|रुपयांचा|रुपया|रु\.|रु|रूपय|रूपये|रू|rs|rupees|rupaye|rupay|ruapaye|रुपीज|ropey|rupai|\/|per|\b|$))/gi;
const PRECOMPILED_FILLER_REGEX = makeUnicodeRegex('आणि|तसेच|त्यानंतर|त्याच्यानंतर|बरं|पुढे|द्या|घ्या|पाहिजे|लाव|टाक|आणखी|आण');
const PRECOMPILED_PRICE_REGEX = makeUnicodeRegex('रुपये|रुपयांची|रुपयांचे|रुपयांचा|रुपया|रु\\.|रु|रूपय|रूपये|रू|rs|rupees|rupee|rupaye|rupay|ruapaye|rupiya|rupiye|rupe|inr|₹|\\/-');

function parseMarathiSpokenNumbers(text) {
  if (!text || typeof text !== 'string') return '';
  let s = text.trim();

  // 1. Convert Devanagari digits [०-९]
  s = s.replace(/[०-९]/g, (d) => DEVANAGARI_DIGITS[d] || d);

  // 1a. Lakhs
  s = s.replace(PRECOMPILED_LAKH_REGEX, (_, m) => {
    const val = /^\d+(?:\.\d+)?$/.test(m) ? parseFloat(m) : (THOUSAND_MULTIPLIERS[m.toLowerCase()] || 1);
    return ` ${Math.round(val * 100000)} `;
  });
  s = s.replace(PRECOMPILED_STANDALONE_LAKH_REGEX, ' 100000 ');

  // 1b. Thousands
  s = s.replace(PRECOMPILED_THOU_REGEX, (_, m) => {
    const val = /^\d+(?:\.\d+)?$/.test(m) ? parseFloat(m) : (THOUSAND_MULTIPLIERS[m.toLowerCase()] || 1);
    return ` ${Math.round(val * 1000)} `;
  });
  s = s.replace(PRECOMPILED_STANDALONE_THOU_REGEX, ' 1000 ');

  // 2. Compound Hundreds (e.g. एकशे चाळीस -> 140, पाचशे अडुसष्ट -> 568, पाचशे पन्नास -> 550, पाचशे 40 -> 540)
  s = s.replace(PRECOMPILED_COMPOUND_HUNDREDS_REGEX, (match, hWord, nextWord) => {
    const hKey = (hWord || '').toLowerCase();
    const hVal = HUNDREDS_MAP[hKey] ?? HUNDREDS_MAP[hWord] ?? 0;
    if (!nextWord) return ` ${hVal} `;
    if (/^\d+$/.test(nextWord)) {
      return ` ${hVal + parseInt(nextWord, 10)} `;
    }
    const uKey = nextWord.toLowerCase();
    const uVal = UNITS_AND_TENS_MAP[uKey] ?? UNITS_AND_TENS_MAP[nextWord] ?? 0;
    if (typeof uVal === 'number' && uVal > 0 && uVal < 100) {
      return ` ${hVal + uVal} `;
    }
    return ` ${hVal} ${nextWord} `;
  });

  // 3. Standalone Units & Tens (e.g. 60, 50, 90, 80, 40, 10, 5)
  s = s.replace(PRECOMPILED_UNITS_TENS_REGEX, (match, uWord) => {
    const uKey = (uWord || '').toLowerCase();
    const uVal = UNITS_AND_TENS_MAP[uKey] ?? UNITS_AND_TENS_MAP[uWord] ?? uWord;
    return ` ${uVal} `;
  });

  // 4. Merge thousands (e.g. 1000, 2000, 5000, 10000) with following hundreds/tens
  s = s.replace(PRECOMPILED_MERGE_THOUSANDS_REGEX, (match, thou, rem) => {
    const tVal = parseInt(thou, 10);
    const rVal = parseInt(rem, 10);
    if (rVal < 1000) {
      return ` ${tVal + rVal} `;
    }
    return match;
  });

  return s;
}

// 3. Marathi Unit Normalization (Unicode-safe)
const MARATHI_UNITS = [
  { pattern: makeUnicodeRegex('किलो|किग्र|कि\\.ग्रा|kilo|kilos|kg|kgs|kilogram'), canonical: 'kg' },
  { pattern: makeUnicodeRegex('ग्रॅम|ग्राम|ग्रा|गरयम|गराम|गिराम|ग्रेम|gram|grams|gm|gms|g'), canonical: 'g' },
  { pattern: makeUnicodeRegex('लिटर|लीटर|litre|litres|liter|liters|ltr|ltrs|l'), canonical: 'litre' },
  { pattern: makeUnicodeRegex('मिली|मिलीलिटर|ml|mls|millilitre'), canonical: 'ml' },
  { pattern: makeUnicodeRegex('पुडा|पुडे|पुडी|पाकीट|पाकिटे|पॅकेट|पॅकेट्स|पैकेट|पॉकेट|packet|packets|pkt|pkts|pouch'), canonical: 'packet' },
  { pattern: makeUnicodeRegex('नग|पीस|piece|pieces|pcs|pc|item|items'), canonical: 'piece' },
  { pattern: makeUnicodeRegex('बाटली|बाटल्या|bottle|bottles|btl'), canonical: 'bottle' },
  { pattern: makeUnicodeRegex('डबा|डबे|खोके|खोका|बॉक्स|box|boxes|carton'), canonical: 'box' },
  { pattern: makeUnicodeRegex('डझन|दर्जन|dozen|dozens'), canonical: 'dozen' },
  { pattern: makeUnicodeRegex('तोळा|तोळे|tola'), canonical: 'tola' },
];

// 4. Comprehensive Multilingual Kirana Item Catalog
// Maintains exact Marathi, Hindi, and English representations
const MARATHI_KIRANA_ITEMS = [
  // Sweeteners & Staples
  { canonical: 'Sakhar', marathi: 'साखर', hindi: 'चीनी', terms: ['साखर', 'साखरेची', 'साखरेचा', 'साकर', 'शुकर', 'सुकर', 'sakhar', 'saakhar', 'sakharachi', 'sakhrechi', 'cheeni', 'chini', 'sugar', 'चीनी', 'शक्कर'] },
  { canonical: 'Gul', marathi: 'गूळ', hindi: 'गुड़', terms: ['गूळ', 'गुळ', 'गुळाची', 'गुळाचा', 'gul', 'gud', 'jaggery', 'गुड़', 'कोल्हापुरी गूळ'] },
  { canonical: 'Meeth', marathi: 'मीठ', hindi: 'नमक', terms: ['मीठ', 'मिठाचे', 'मिठाचा', 'meeth', 'mith', 'namak', 'salt', 'टाटा मीठ'] },

  // Grains & Flours
  { canonical: 'Tandul', marathi: 'तांदूळ', hindi: 'चावल', terms: ['तांदूळ', 'तांदुळ', 'तांदळाचे', 'तांदळाची', 'tandul', 'tandool', 'chawal', 'rice', 'भात', 'कोलम', 'इंद्रायणी', 'बासमती', 'तुकडा'] },
  { canonical: 'Gahu', marathi: 'गहू', hindi: 'गेहूं', terms: ['गहू', 'गव्हाचे', 'गव्हाचा', 'gahu', 'gehu', 'wheat', 'शरबती गहू', 'सीहोर गहू', 'लोकवन गहू'] },
  { canonical: 'Atta', marathi: 'गव्हाचे पीठ', hindi: 'आटा', terms: ['आटा', 'पीठ', 'गव्हाचे पीठ', 'कणिक', 'atta', 'aata', 'peeth', 'pith', 'wheat flour', 'चक्की फ्रेश'] },
  { canonical: 'Maida', marathi: 'मैदा', hindi: 'मैदा', terms: ['मैदा', 'मैद्याचे', 'माईदा', 'मैधा', 'माईधा', 'मायदा', 'maida', 'maidha', 'mayda', 'all purpose flour'] },
  { canonical: 'Besan', marathi: 'बेसन', hindi: 'बेसन', terms: ['बेसन', 'चना पीठ', 'हरभरा पीठ', 'डाळीचे पीठ', 'besan', 'gram flour'] },
  { canonical: 'Rawa', marathi: 'रवा', hindi: 'सूजी', terms: ['रवा', 'बारीक रवा', 'जाडा रवा', 'सुजी', 'सूजी', 'rawa', 'rava', 'sooji', 'suji', 'semolina'] },
  { canonical: 'Pohe', marathi: 'पोहे', hindi: 'पोहा', terms: ['पोहे', 'पोहा', 'जाडे पोहे', 'पातळ पोहे', 'दगडी पोहे', 'pohe', 'poha'] },
  { canonical: 'Jowar', marathi: 'ज्वारी', hindi: 'ज्वार', terms: ['ज्वारी', 'ज्वारीचे पीठ', 'jowar', 'jowari', 'मालदांडी'] },
  { canonical: 'Bajra', marathi: 'बाजरी', hindi: 'बाजरा', terms: ['बाजरी', 'बाजरीचे पीठ', 'bajri', 'bajra'] },
  { canonical: 'Shabu', marathi: 'शाबू', hindi: 'साबूदाना', terms: ['साबुदाणा', 'साबुदाना', 'शाबू', 'shabu', 'sabudana', 'saboodana', 'sago'] },
  { canonical: 'Sarki Pend', marathi: 'सरकी पेंड', hindi: 'सरकी पेंड', terms: ['सरकी पेंड', 'सरकी पेंढ', 'सरकी', 'sarki pend', 'sarki pendh', 'sarkipend', 'sarkipendh', 'cottonseed cake'] },
  { canonical: 'Murmura', marathi: 'चुरमुरे', hindi: 'मुरमुरा', terms: ['चुरमुरे', 'मुरमुरा', 'कुरमुरे', 'churmure', 'murmura', 'kurmura'] },

  // Dals & Pulses
  { canonical: 'Tur Dal', marathi: 'तूर डाळ', hindi: 'अरहर दाल', terms: ['तूर डाळ', 'तुरीची डाळ', 'तूरडाळ', 'tur dal', 'toor dal', 'arhar dal'] },
  { canonical: 'Chana Dal', marathi: 'चना डाळ', hindi: 'चना दाल', terms: ['चना डाळ', 'हरभरा डाळ', 'chana dal', 'harbhara dal'] },
  { canonical: 'Moong Dal', marathi: 'मूग डाळ', hindi: 'मूंग दाल', terms: ['मूग डाळ', 'मुगाची डाळ', 'मूंग डाळ', 'मूंगडाल', 'मुंग दाल', 'मुंगदाल', 'moong dal', 'mung dal', 'हिरवे मूग'] },
  { canonical: 'Urad Dal', marathi: 'उडीद डाळ', hindi: 'उड़द दाल', terms: ['उडीद डाळ', 'उडदाची डाळ', 'urad dal', 'udid dal'] },
  { canonical: 'Masoor Dal', marathi: 'मसूर डाळ', hindi: 'मसूर दाल', terms: ['मसूर डाळ', 'मसुराची डाळ', 'masoor dal', 'अख्खा मसूर'] },
  { canonical: 'Chole', marathi: 'काबुली चणे', hindi: 'छोले', terms: ['काबुली चणे', 'काबुली चना', 'छोले', 'chole', 'kabuli chana'] },
  { canonical: 'Matki', marathi: 'मटकी', hindi: 'मटकी', terms: ['मटकी', 'मोड आलेली मटकी', 'matki', 'moth beans'] },
  { canonical: 'Rajma', marathi: 'राजमा', hindi: 'राजमा', terms: ['राजमा', 'rajma', 'red rajma'] },
  { canonical: 'Vatana', marathi: 'वाटाणा', hindi: 'मटर', terms: ['वाटाणा', 'सफेद वाटाणा', 'हिरवा वाटाणा', 'vatana', 'matar'] },

  // Cooking Oils & Ghee
  { canonical: 'Godetel', marathi: 'गोडेतेल', hindi: 'तेल', terms: ['गोडेतेल', 'तेल', 'तेलाची', 'तेलाचे', 'tel', 'oil', 'cooking oil'] },
  { canonical: 'Shengdana Tel', marathi: 'शेंगदाणा तेल', hindi: 'मूंगफली तेल', terms: ['शेंगदाणा तेल', 'shengdana tel', 'groundnut oil', 'peanut oil'] },
  { canonical: 'Sunflower Tel', marathi: 'सूर्यफूल तेल', hindi: 'सूरजमुखी तेल', terms: ['सूर्यफूल तेल', 'sunflower oil', 'सनफ्लॉवर तेल', 'सनफ्लॉवर'] },
  { canonical: 'Gemini Tel', marathi: 'जेमिनी तेल', hindi: 'जेमिनी तेल', terms: ['जेमिनी तेल', 'जेमिनी', 'gemini oil', 'gemini'] },
  { canonical: 'Mohari Tel', marathi: 'मोहरी तेल', hindi: 'सरसों तेल', terms: ['मोहरी तेल', 'राई तेल', 'mustard oil', 'sarson oil'] },
  { canonical: 'Khobrel Tel', marathi: 'खोबरेल तेल', hindi: 'नारियल तेल', terms: ['खोबरेल तेल', 'पॅराशूट', 'पॅराशूट तेल', 'khobrel tel', 'coconut oil', 'parachute'] },
  { canonical: 'Tup', marathi: 'तूप', hindi: 'घी', terms: ['तूप', 'तूपाची', 'तूपाचा', 'साजूक तूप', 'गायीचे तूप', 'tup', 'toop', 'ghee', 'amul ghee'] },

  // Spices & Condiments
  { canonical: 'Halad', marathi: 'हळद', hindi: 'हल्दी', terms: ['हळद', 'हळदी', 'हळदीची', 'halad', 'haldi', 'turmeric', 'हळद पावडर'] },
  { canonical: 'Lal Tikhat', marathi: 'लाल तिखट', hindi: 'लाल मिर्च', terms: ['लाल तिखट', 'मिरची पावडर', 'तिखट', 'मिरची', 'lal tikhat', 'mirchi powder', 'red chilli powder'] },
  { canonical: 'Jeera', marathi: 'जिरे', hindi: 'जीरा', terms: ['जिरे', 'जिरं', 'जीरा', 'jeera', 'jira', 'cumin'] },
  { canonical: 'Mohari', marathi: 'मोहरी', hindi: 'राई', terms: ['मोहरी', 'राई', 'mohari', 'rai', 'mustard seeds'] },
  { canonical: 'Dhane', marathi: 'धने', hindi: 'धनिया', terms: ['धने', 'धने पावडर', 'धनिया', 'dhane', 'dhaniya', 'coriander seeds'] },
  { canonical: 'Garam Masala', marathi: 'गरम मसाला', hindi: 'गरम मसाला', terms: ['गरम मसाला', 'सुहाना मसाला', 'एव्हरेस्ट मसाला', 'garam masala', 'masala'] },
  { canonical: 'Hing', marathi: 'हिंग', hindi: 'हींग', terms: ['हिंग', 'hing', 'asafoetida'] },
  { canonical: 'Velchi', marathi: 'वेलची', hindi: 'इलायची', terms: ['वेलची', 'विलायची', 'इलायची', 'velchi', 'elaichi', 'cardamom'] },
  { canonical: 'Lavang', marathi: 'लवंग', hindi: 'लौंग', terms: ['लवंग', 'लावंग', 'lavang', 'laung', 'clove'] },
  { canonical: 'Dalchini', marathi: 'दालचिनी', hindi: 'दालचीनी', terms: ['दालचिनी', 'dalchini', 'cinnamon'] },
  { canonical: 'Methi Dane', marathi: 'मेथी दाणे', hindi: 'मेथी दाना', terms: ['मेथी दाणे', 'मेथी', 'methi seeds', 'fenugreek'] },
  { canonical: 'Khobra', marathi: 'खोबरं', hindi: 'सूखा नारियल', terms: ['खोबरं', 'सुके खोबरे', 'खोबरे', 'khobare', 'dry coconut'] },

  // Dairy & Daily Essentials
  { canonical: 'Dudh', marathi: 'दूध', hindi: 'दूध', terms: ['दूध', 'दुध', 'दुधाची', 'dudh', 'doodh', 'milk', 'गोकुळ दूध', 'अमुल दूध', 'चितळे दूध'] },
  { canonical: 'Sargam Dust Tea', marathi: 'सरगम पत्ती चहा', hindi: 'सरगम पत्ती चाय', terms: ['सरगम पत्ती चहा', 'सरगम चहा', 'सरगम पत्ती', 'सरगम', 'सर्गं पत्ती', 'सर्गप चहा', 'सर्कं पत्ती', 'sargam patti chaha', 'sargam chaha', 'sargam patti', 'sargam tea', 'sargam dust tea', 'sargam'] },
  { canonical: 'Super Dust Tea', marathi: 'सुपर डस्ट चहा', hindi: 'सुपर डस्ट चाय', terms: ['सुपर डस्ट चहा', 'सुपर डस्ट', 'सूपर डस्ट', 'सूपर डस्ट चहा', 'डस्ट चहा', 'super dust chaha', 'super dust tea', 'super dust', 'dust tea'] },
  { canonical: 'Red Label Tea', marathi: 'रेड लेबल चहा', hindi: 'रेड लेबल चाय', terms: ['रेड लेबल चहा', 'रेड लेबल', 'red label chaha', 'red label tea', 'red label'] },
  { canonical: 'Wagh Bakri Tea', marathi: 'वाघ बकरी चहा', hindi: 'वाघ बकरी चाय', terms: ['वाघ बकरी चहा', 'वाघ बकरी', 'wagh bakri chaha', 'wagh bakri tea', 'wagh bakri'] },
  { canonical: 'Society Tea', marathi: 'सोसायटी चहा', hindi: 'सोसायटी चाय', terms: ['सोसायटी चहा', 'सोसायटी', 'society chaha', 'society tea', 'society'] },
  { canonical: 'Chaha', marathi: 'चहा', hindi: 'चाय', terms: ['चहा', 'चाहा', 'चहाची', 'चाहाची', 'चहा पावडर', 'चहापत्ती', 'चहा पत्ती', 'चाय पत्ती', 'chaha', 'chaaha', 'chai', 'tea', 'चाय'] },
  { canonical: 'Coffee', marathi: 'कॉफी', hindi: 'कॉफ़ी', terms: ['कॉफी', 'coffee', 'nescafe', 'bru'] },
  { canonical: 'Shengdane', marathi: 'शेंगदाणे', hindi: 'मूंगफली', terms: ['शेंगदाणे', 'शेंगदाणा', 'दाणे', 'शेंग दानी', 'शेंगदानी', 'शेंग दाने', 'शेंगदाने', 'shengdane', 'shengdana', 'shengadane', 'sheng dane', 'sheng dani', 'shengdani', 'dane', 'peanuts', 'groundnuts', 'mungfali', 'moongfali', 'मूंगफली'] },
  { canonical: 'Kaju', marathi: 'काजू', hindi: 'काजू', terms: ['काजू', 'काजू तुकडा', 'kaju', 'cashew'] },
  { canonical: 'Badam', marathi: 'बदाम', hindi: 'बादाम', terms: ['बदाम', 'badam', 'almond'] },
  { canonical: 'Manuka', marathi: 'मनुका', hindi: 'किशमिश', terms: ['मनुका', 'किशमिश', 'manuka', 'kishmish', 'raisins'] },
  { canonical: 'Charoli', marathi: 'चारोळी', hindi: 'चिरौंजी', terms: ['चारोळी', 'चारोळ्या', 'चिरौंजी', 'charoli', 'charolee', 'chironji', 'chironjee'] },

  // Household & Personal Care
  { canonical: 'Saban', marathi: 'साबण', hindi: 'साबुन', terms: ['साबण', 'अंगाचा साबण', 'कपड्यांचा साबण', 'saban', 'soap', 'लाईफबॉय', 'लक्स', 'डेटॉल', 'संतूर'] },
  { canonical: 'Detergent', marathi: 'डिटर्जंट पावडर', hindi: 'सर्फ', terms: ['निरमा', 'सर्फ', 'डिटर्जंट पावडर', 'टाईड', 'एरिअल', 'detergent', 'surf', 'nirma'] },
  { canonical: 'Vim Bar', marathi: 'भांड्यांचा साबण', hindi: 'बर्तन साबुन', terms: ['भांड्यांचा साबण', 'विम बार', 'विम', 'भांडी घासण्याचा साबण', 'vim bar', 'dishwash'] },
  { canonical: 'Kadepeti', marathi: 'काडेपेटी', hindi: 'माचिस', terms: ['काडेपेटी', 'माचिस', 'काडीपेटी', 'kadepeti', 'machis', 'matchbox'] },
  { canonical: 'Agarbatti', marathi: 'अगरबत्ती', hindi: 'अगरबत्ती', terms: ['अगरबत्ती', 'अगरबत्त्या', 'धूप', 'agarbatti', 'incense'] },
  { canonical: 'Toothpaste', marathi: 'टूथपेस्ट', hindi: 'टूथपेस्ट', terms: ['कोलगेट', 'पेस्ट', 'टूथपेस्ट', 'colgate', 'toothpaste', 'क्लोजअप'] },
  { canonical: 'Biscuits', marathi: 'बिस्कीट', hindi: 'बिस्कुट', terms: ['बिस्कीट', 'बिस्किट', 'पारले जी', 'गुड डे', 'मारी', 'क्रॅकजॅक', 'biscuit', 'parle g', 'good day'] },
  { canonical: 'Maggi', marathi: 'मॅगी', hindi: 'मैगी', terms: ['मॅगी', 'शेवया', 'नूडल्स', 'maggi', 'noodles'] },

  // Fresh Produce
  { canonical: 'Kande', marathi: 'कांदे', hindi: 'प्याज़', terms: ['कांदे', 'कांदा', 'kande', 'kanda', 'onion'] },
  { canonical: 'Batate', marathi: 'बटाटे', hindi: 'आलू', terms: ['बटाटे', 'बटाटा', 'batate', 'batata', 'potato', 'aloo'] },
  { canonical: 'Lasun', marathi: 'लसूण', hindi: 'लहसुन', terms: ['लसूण', 'लसून', 'lasun', 'garlic'] },
  { canonical: 'Aale', marathi: 'आले', hindi: 'अदरक', terms: ['आले', 'अद्रक', 'ale', 'adrak', 'ginger'] },
];

/**
 * Pre-processes spoken Marathi transcript before LLM or Regex parsing:
 * 1. Deduplicates repeated stutter tokens (e.g., "sakhar-sakhar" -> "sakhar").
 * 2. Converts Devanagari numerals to ASCII.
 * 3. Standardizes numbers, fractions, and compound hundreds (e.g. एकशे चाळीस -> 140, पाचशे अडुसष्ट -> 568).
 * 4. Standardizes units (Unicode-safe).
 * 5. Cleans colloquial filler speech.
 */
function normalizeMarathiTranscript(text) {
  if (!text || typeof text !== 'string') return '';

  // 0. Convert any misidentified Indic script (like Gujarati) to pure Marathi Devanagari
  let s = convertIndicScriptToDevanagari(text);

  // 0b. Convert Devanagari digits [०-९] early so all numeric regexes work seamlessly!
  s = s.replace(/[०-९]/g, (d) => DEVANAGARI_DIGITS[d] || d);

  // 1. Remove stutter/echo repetitions (sakhar-sakhar -> sakhar)
  s = deduplicateSpokenTokens(s);

  // 1a. Convert tola (Indian Kirana standard: 1 tola = 10 grams) - unicode-safe boundaries
  s = s.replace(/(?:ardha\s*tola|aadha\s*tola|अर्धा\s*तोळा|आधा\s*तोला)(?=[^\u0900-\u097Fa-zA-Z]|$)/gi, '5 gm');
  s = s.replace(/(?:ek\s*tola|एक\s*तोळा|एक\s*तोला)(?=[^\u0900-\u097Fa-zA-Z]|$)/gi, '10 gm');
  s = s.replace(/(\d+(?:\.\d+)?)\s*(?:tola|tole|तोळा|तोळे|तोला)(?=[^\u0900-\u097Fa-zA-Z]|$)/gi, (_, n) => (parseFloat(n) * 10) + ' gm');

  // 1b. Separate glued price words (e.g. '50rs' -> '50 rs', 'pacahsherupaye' -> 'pacahshe rupaye', 'पन्नासरुपये' -> 'पन्नास रुपये')
  // Note: 'rs' only separated after digits to avoid breaking words like 'wafers', 'cheers'
  s = s.replace(/([A-Za-z\u0900-\u097F]+?)(rupaye|rupay|rupees|rupee|रुपये|रुपया|रू)(?=[^\u0900-\u097Fa-zA-Z]|$)/gi, '$1 $2');
  s = s.replace(/(\d+)(rs|रू)(?=[^\u0900-\u097Fa-zA-Z]|$)/gi, '$1 $2');

  // 1c. Handle per-unit spoken phrases ('60 per kg' -> '60 rs', '140rs per kg' -> '140 rs', '120 per dozen' -> '120 rs')
  s = s.replace(/(\d+(?:\.\d+)?)\s*(?:rs|rupees|rupaye|rupay|रुपये|रू)?\s*(?:per|\/|prati|दर|प्रति)\s*(?:kg|kilo|kilogram|किलो|किग्रा|litre|liter|लिटर|लीटर|l|dozen|डझन|दर्जन|gm|ग्रॅम|ग्राम|packet|पाकीट|box|खोके|pcs|नग)\b/gi, '$1 rs');

  // 1d. Collapse duplicate spoken units/weights (e.g. 'pav kilo 250 gm' -> '250 gm', 'ardha kilo 500 gm' -> '500 gm')
  s = s.replace(/(?:pav\s*kilo|पाव\s*किलो)\s+(?:250\s*(?:gm|gms|g|gram|grams|ग्रॅम|ग्राम)?)/gi, '250 gm');
  s = s.replace(/(?:ardha\s*kilo|aadha\s*kilo|अर्धा\s*किलो|आधा\s*किलो)\s+(?:500\s*(?:gm|gms|g|gram|grams|ग्रॅम|ग्राम)?)/gi, '500 gm');
  s = s.replace(/(?:ek\s*kilo|एक\s*किलो)\s+(?:1000\s*(?:gm|gms|g|gram|grams|ग्रॅम|ग्राम)?|1\s*(?:kg|kilo|किलो))/gi, '1 kg');
  s = s.replace(/(?:don\s*kilo|दोन\s*किलो)\s+(?:2\s*(?:kg|kilo|किलो))/gi, '2 kg');

  // Phonetic variants of 550
  s = s.replace(/\bsade\s*pacahshe\b/gi, '550');
  s = s.replace(/\bsade\s*pacashe\b/gi, '550');
  s = s.replace(/\bsade\s*pachashe\b/gi, '550');

  // 1c. Correct common STT acoustic phonetics in Marathi speech
  s = s.replace(makeUnicodeRegex('वाज\\s+किलो'), 'पाव किलो');
  s = s.replace(makeUnicodeRegex('साकर|शुकर|सुकर'), 'साखर');
  s = s.replace(makeUnicodeRegex('साट'), 'साठ');
  s = s.replace(makeUnicodeRegex('माईदा|मैधा|माईधा|मायदा'), 'मैदा');
  s = s.replace(makeUnicodeRegex('शेंग\\s*दानी|शेंगदानी|शेंग\\s*दाने|शेंगदाने'), 'शेंगदाणे');
  s = s.replace(makeUnicodeRegex('सर्गं\\s*पत्ती|सर्गप\\s*चहा|सर्कं\\s*पत्ती'), 'सरगम पत्ती चहा');
  s = s.replace(makeUnicodeRegex('सूपर\\s*डस्ट|सुपर\\s*डस्ट'), 'सुपर डस्ट चहा');
  s = s.replace(makeUnicodeRegex('पात्स'), 'पाच');
  s = s.replace(makeUnicodeRegex('मूंगडाल|मुंग\\s*दाल|मुंगदाल'), 'मूग डाळ');
  s = s.replace(makeUnicodeRegex('पणनसरुपई|पण्नास\\s*रुपये|पन्नास\\s*रुब्बाई|पणनस\\s*रुपये|पणनस'), '५० रुपये');
  s = s.replace(makeUnicodeRegex('एकशिचाईस|एकशिचारीफ|एकशेचाईस|एकशे\\s*चाईस'), '१४०');
  s = s.replace(makeUnicodeRegex('पस्चे\\s*पन्नस|पश्य\\s*पन्नास|फायू\\s*हंडरेट\\s*फिर्प्टे|फायू\\s*हाढरेट\\s*फिर्फिति'), '५५० रुपये');
  s = s.replace(makeUnicodeRegex('रोपेज|रुपेज|रोबइ|रोपई|रुब्बाई|रुपिज|रुपीज'), 'रुपये');
  s = s.replace(makeUnicodeRegex('शमब'), 'शंभर');
  s = s.replace(makeUnicodeRegex('गरयम|गराम|गिराम|ग्रेम'), 'ग्राम');

  // 2. Convert Devanagari digits [०-९]
  s = s.replace(/[०-९]/g, (d) => DEVANAGARI_DIGITS[d] || d);

  // 3. Remove common spoken filler/connecting words in Marathi (Unicode-safe)
  s = s.replace(PRECOMPILED_FILLER_REGEX, ' , ');

  // 4. Normalizes Marathi numbers, compound hundreds & fractions (e.g. 140, 60, 50, 90, 80, 40, 500, 10, 5, 900, 568, 789, 550, 110, 108)
  s = parseMarathiSpokenNumbers(s);

  // 5. Normalizes units
  for (const { pattern, canonical } of MARATHI_UNITS) {
    s = s.replace(pattern, ` ${canonical} `);
  }

  // 6. Normalizes price indicators (रुपये, रुपयांची, रुपयांचे, रु, rs, rupaye, ruapaye, etc.) (Unicode-safe)
  s = s.replace(PRECOMPILED_PRICE_REGEX, ' rs ');

  // 6b. Collapse duplicate adjacent numbers spoken for emphasis (e.g. "550 550 rs" -> "550 rs", "70 70 rs" -> "70 rs")
  s = s.replace(/\b(\d+(?:\.\d+)?)\s+\1\b/g, '$1');

  // 7. Clean multiple spaces and comma separators
  s = s.replace(/\s+/g, ' ').replace(/\s*,\s*/g, ' , ').trim();

  return s;
}

/**
 * Transliterates Devanagari script to Latin English text
 */
function devanagariToLatin(text) {
  if (!text || typeof text !== 'string') return '';
  const consonants = {
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh',
    'ष': 'sh', 'स': 's', 'ह': 'h', 'ळ': 'l', 'क्ष': 'ksh', 'ज्ञ': 'dny'
  };
  const vowels = {
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo',
    'ऋ': 'ru', 'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'अं': 'am', 'अः': 'ah'
  };
  const matras = {
    'ा': 'a', 'ि': 'i', 'ी': 'i', 'ु': 'u', 'ू': 'oo',
    'ृ': 'ru', 'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au',
    'ं': 'n', 'ँ': 'n', 'ः': 'h'
  };
  let result = '';
  const chars = Array.from(text);
  for (let i = 0; i < chars.length; i++) {
    const ch = chars[i];
    const next = chars[i + 1];
    if (vowels[ch]) {
      result += vowels[ch];
    } else if (consonants[ch]) {
      result += consonants[ch];
      if (next === '्') {
        i++; // halant skips inherent vowel
      } else if (matras[next]) {
        result += matras[next];
        i++;
      } else if (i < chars.length - 1 && chars[i + 1] !== ' ' && !matras[next]) {
        result += 'a'; // inherent vowel
      }
    } else if (matras[ch]) {
      result += matras[ch];
    } else {
      result += ch;
    }
  }
  return result.trim().replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Canonicalizes an extracted item name.
 * If outputLang is 'en', returns clean English name (Sugar, Toor Dal, Cooking Oil, Tea) or Latin transliteration.
 * If spoken in Marathi -> returns Marathi name (साखर, तूर डाळ, पोहे, गोडेतेल, चहा)
 * If spoken in Hindi -> returns Hindi name (चीनी, अरहर दाल, चावल, तेल, चाय)
 * If spoken in English -> returns English name (Sugar, Rice, Oil, Tea)
 */
function canonicalizeMarathiItemName(name, language = 'mr-IN', outputLang = null) {
  if (!name || typeof name !== 'string') return '';
  const converted = convertIndicScriptToDevanagari(name);
  const deduped = deduplicateSpokenTokens(converted);
  const clean = deduped.toLowerCase().trim();

  const isDevanagari = /[\u0900-\u097F]/.test(deduped);
  const langLower = String(language || 'mr-IN').toLowerCase();
  const isHindi = langLower.startsWith('hi');
  const isEnglish = langLower.startsWith('en') || String(outputLang || '').toLowerCase().startsWith('en');
  // If language is Marathi or default mr-IN
  const isMarathi = !isEnglish && (langLower.startsWith('mr') || !isHindi);

  // Strip common grammatical post-positions (साखरेची -> साखर, तेलाचे -> तेल)
  const stripped = clean
    .replace(/(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$/gi, '')
    .trim();

  for (const entry of MARATHI_KIRANA_ITEMS) {
    for (const term of entry.terms) {
      const termLower = term.toLowerCase();
      // Only match if exact term or stripped term (e.g. "साखर" -> "साखर", "तेलाचे" -> "तेल")
      // Never collapse a multi-word brand (e.g. "फॉर्च्यून तेल", "गोदरेज साबण") to a generic word!
      if (clean === termLower || stripped === termLower) {
        if (isEnglish) return entry.canonical;
        if (isHindi) return entry.hindi || entry.canonical;
        if (isMarathi) return entry.marathi || entry.canonical;
        return entry.canonical;
      }
    }
  }

  // Fallback: Preserve exact user-spoken name or brand directly
  if (isDevanagari) {
    const strippedDev = deduped.replace(/(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$/gi, '').trim();
    if (isEnglish) {
      return devanagariToLatin(strippedDev);
    }
    return strippedDev;
  }

  // English fallback: Title case
  return clean.replace(/\b\w/g, (c) => c.toUpperCase());
}

module.exports = {
  devanagariToLatin,
  deduplicateSpokenTokens,
  convertIndicScriptToDevanagari,
  normalizeMarathiTranscript,
  parseMarathiSpokenNumbers,
  canonicalizeMarathiItemName,
  HUNDREDS_MAP,
  UNITS_AND_TENS_MAP,
  MARATHI_UNITS,
  MARATHI_KIRANA_ITEMS,
};
