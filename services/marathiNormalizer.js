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

// 2. Comprehensive Marathi & Indian Number Words (Hundreds, Compounds, Tens, Units, Fractions)
const HUNDREDS_MAP = {
  // Marathi Devanagari & Phonetic Hundreds
  'एकशे': 100, 'ekshe': 100, 'ekashe': 100, 'ekshey': 100, 'ek sau': 100, 'one hundred': 100, 'शंभर': 100, 'shambhar': 100,
  'दोनशे': 200, 'दोंशे': 200, 'donshe': 200, 'donashe': 200, 'donshey': 200, 'do sau': 200, 'two hundred': 200,
  'तीनशे': 300, 'teenshe': 300, 'teenashe': 300, 'teenshey': 300, 'teen sau': 300, 'three hundred': 300,
  'चारशे': 400, 'charshe': 400, 'charashe': 400, 'charshey': 400, 'char sau': 400, 'four hundred': 400,
  'पाचशे': 500, 'pachshe': 500, 'paachshe': 500, 'pachashe': 500, 'paachashe': 500, 'pachashey': 500, 'pachshey': 500, 'paanch sau': 500, 'panch sau': 500, 'five hundred': 500,
  'सहाशे': 600, 'sahashe': 600, 'sahashey': 600, 'chha sau': 600, 'six hundred': 600,
  'सातशे': 700, 'saatshe': 700, 'saatashe': 700, 'saatshey': 700, 'saat sau': 700, 'seven hundred': 700,
  'आठशे': 800, 'aathshe': 800, 'aathashe': 800, 'aathshey': 800, 'aath sau': 800, 'eight hundred': 800,
  'नऊशे': 900, 'naushe': 900, 'nauashe': 900, 'naushey': 900, 'nau sau': 900, 'nine hundred': 900,
  'हजार': 1000, 'hazar': 1000, 'hazaar': 1000, 'ek hazar': 1000, 'one thousand': 1000,

  // Direct Hundred-Tens Compounds
  'एकशेचाळीस': 140, 'एकशेचालीस': 140, 'एकशेच्चाइश': 140, 'एकशेचायच': 140, 'एकशेचाईस': 140,
  'दोनशेपन्नास': 250, 'दोंशेपन्नस': 250, 'दोनशे पन्नास': 250, 'दोंशे पन्नास': 250, 'donshepannas': 250, 'donshe pannas': 250,

  // Colloquial half-hundreds
  'साडेपाचशे': 550, 'sade pachshe': 550, 'sade paachshe': 550, 'sade pachashe': 550, 'sade paachashe': 550, 'pachashe pannas': 550, 'pachshe pannas': 550,
  'साडेचारशे': 450, 'sade charshe': 450,
  'साडेतीनशे': 350, 'sade teenshe': 350,
  'अडीचशे': 250, 'adeechshe': 250, 'dhai sau': 250,
  'दीडशे': 150, 'deedshe': 150, 'dedh sau': 150,
  'साडेसहाशे': 650, 'sade sahashe': 650,
  'साडेसातशे': 750, 'sade saatshe': 750,
  'साडेआठशे': 850, 'sade aathshe': 850,
  'साडेनऊशे': 950, 'sade naushe': 950,
  'सव्वाशे': 125, 'savvashe': 125,
};

const UNITS_AND_TENS_MAP = {
  // 90s
  'नव्व्याण्णव': 99, 'अठ्ठ्याण्णव': 98, 'सत्याण्णव': 97, 'शहाण्णव': 96,
  'पंच्याण्णव': 95, 'चौऱ्याण्णव': 94, 'त्र्याण्णव': 93, 'ब्याण्णव': 92, 'एक्याण्णव': 91,
  'navvad': 90, 'navve': 90, 'nabbe': 90, 'नव्वद': 90, 'नब्बे': 90, 'ninety': 90,

  // 80s
  'एक्याऐंशी': 81, 'ब्याऐंशी': 82, 'त्र्याऐंशी': 83, 'चौऱ्याऐंशी': 84,
  'पंच्याऐंशी': 85, 'पंचाइश': 85, 'पंचाईश': 85, 'पंचाशी': 85, 'पंच्यांशी': 85, 'पंचाऐंशी': 85, 'panchaishi': 85, 'panchashi': 85, 'pachasi': 85, 'पचासी': 85,
  'शहाऐंशी': 86, 'सत्याऐंशी': 87, 'अठ्ठ्याऐंशी': 88,
  'एकोणनव्वद': 89, 'nawasi': 89, 'ekonnavvad': 89,
  'aishi': 80, 'ayshi': 80, 'assi': 80, 'ऐंशी': 80, 'अस्सी': 80, 'eighty': 80,

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
  'पस्तीस': 35, 'pastis': 35, 'paintis': 35,
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
  'बारा': 12, 'bara': 12, 'barah': 12, 'twelve': 12, 'डझन': 12, 'dozen': 12,
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

function parseMarathiSpokenNumbers(text) {
  if (!text || typeof text !== 'string') return '';
  let s = text.trim();

  // 1. Convert Devanagari digits [०-९]
  s = s.replace(/[०-९]/g, (d) => DEVANAGARI_DIGITS[d] || d);

  const replaceWord = (targetStr, word, replacement) => {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))${escaped}(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`, 'gi');
    return targetStr.replace(regex, replacement);
  };

  // 2. Compound Hundreds (e.g. एकशे चाळीस -> 140, पाचशे अडुसष्ट -> 568, सातशे एकोणनव्वद -> 789, पाचशे पन्नास -> 550)
  const sortedHundreds = Object.keys(HUNDREDS_MAP).sort((a, b) => b.length - a.length);
  const sortedUnitsTens = Object.keys(UNITS_AND_TENS_MAP).sort((a, b) => b.length - a.length);

  for (const hWord of sortedHundreds) {
    const hVal = HUNDREDS_MAP[hWord];

    // Check if followed by unit/tens word: e.g. "एकशे चाळीस"
    for (const uWord of sortedUnitsTens) {
      const uVal = UNITS_AND_TENS_MAP[uWord];
      if (typeof uVal !== 'number' || uVal <= 0 || uVal >= 100) continue;

      const regex = new RegExp(`(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))${hWord}\\s+${uWord}(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`, 'gi');
      if (regex.test(s)) {
        s = s.replace(regex, ` ${hVal + uVal} `);
      }
    }

    // Check if followed by an already-numeric digit: e.g. "एकशे 40" -> 140
    const numRegex = new RegExp(`(?:^|(?<=[^\\u0900-\\u097Fa-zA-Z0-9]))${hWord}\\s+(\\d{1,2})(?=[^\\u0900-\\u097Fa-zA-Z0-9]|$)`, 'gi');
    s = s.replace(numRegex, (_, d) => ` ${hVal + parseInt(d, 10)} `);

    // Replace standalone hundreds (e.g. "पाचशे", "नऊशे", "साडेपाचशे")
    s = replaceWord(s, hWord, ` ${hVal} `);
  }

  // 3. Standalone Units & Tens (e.g. 60, 50, 90, 80, 40, 10, 5)
  for (const uWord of sortedUnitsTens) {
    const uVal = UNITS_AND_TENS_MAP[uWord];
    s = replaceWord(s, uWord, ` ${uVal} `);
  }

  return s;
}

// 3. Marathi Unit Normalization (Unicode-safe)
const MARATHI_UNITS = [
  { pattern: makeUnicodeRegex('किलो|किग्र|कि\\.ग्रा|kilo|kilos|kg|kgs|kilogram'), canonical: 'kg' },
  { pattern: makeUnicodeRegex('ग्रॅम|ग्राम|ग्रा|गरयम|गराम|गिराम|ग्रेम|gram|grams|gm|gms|g'), canonical: 'g' },
  { pattern: makeUnicodeRegex('लिटर|लीटर|litre|litres|liter|liters|ltr|ltrs|l'), canonical: 'litre' },
  { pattern: makeUnicodeRegex('मिली|मिलीलिटर|ml|mls|millilitre'), canonical: 'ml' },
  { pattern: makeUnicodeRegex('पुडा|पुडे|पुडी|पाकीट|पाकिटे|packet|packets|pkt|pkts|pouch'), canonical: 'packet' },
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
  { canonical: 'Sugar', marathi: 'साखर', hindi: 'चीनी', terms: ['साखर', 'साखरेची', 'साखरेचा', 'sakhar', 'sakharachi', 'sakhrechi', 'cheeni', 'chini', 'sugar', 'शक्कर'] },
  { canonical: 'Jaggery', marathi: 'गूळ', hindi: 'गुड़', terms: ['गूळ', 'गुळ', 'गुळाची', 'गुळाचा', 'gul', 'gud', 'jaggery', 'कोल्हापुरी गूळ'] },
  { canonical: 'Salt', marathi: 'मीठ', hindi: 'नमक', terms: ['मीठ', 'मिठाचे', 'मिठाचा', 'meeth', 'mith', 'namak', 'salt', 'टाटा मीठ'] },

  // Grains & Flours
  { canonical: 'Rice', marathi: 'तांदूळ', hindi: 'चावल', terms: ['तांदूळ', 'तांदुळ', 'तांदळाचे', 'तांदळाची', 'tandul', 'tandool', 'chawal', 'rice', 'भात', 'कोलम', 'इंद्रायणी', 'बासमती', 'तुकडा'] },
  { canonical: 'Wheat', marathi: 'गहू', hindi: 'गेहूं', terms: ['गहू', 'गव्हाचे', 'गव्हाचा', 'gahu', 'gehu', 'wheat', 'शरबती गहू', 'सीहोर गहू', 'लोकवन गहू'] },
  { canonical: 'Atta', marathi: 'गव्हाचे पीठ', hindi: 'आटा', terms: ['आटा', 'पीठ', 'गव्हाचे पीठ', 'कणिक', 'atta', 'aata', 'peeth', 'pith', 'wheat flour', 'चक्की फ्रेश'] },
  { canonical: 'Maida', marathi: 'मैदा', hindi: 'मैदा', terms: ['मैदा', 'मैद्याचे', 'maida', 'all purpose flour'] },
  { canonical: 'Besan', marathi: 'बेसन', hindi: 'बेसन', terms: ['बेसन', 'चना पीठ', 'हरभरा पीठ', 'डाळीचे पीठ', 'besan', 'gram flour'] },
  { canonical: 'Rava', marathi: 'रवा', hindi: 'सूजी', terms: ['रवा', 'बारीक रवा', 'जाडा रवा', 'सुजी', 'सूजी', 'rawa', 'rava', 'sooji', 'suji', 'semolina'] },
  { canonical: 'Poha', marathi: 'पोहे', hindi: 'पोहा', terms: ['पोहे', 'पोहा', 'जाडे पोहे', 'पातळ पोहे', 'दगडी पोहे', 'pohe', 'poha'] },
  { canonical: 'Jowar', marathi: 'ज्वारी', hindi: 'ज्वार', terms: ['ज्वारी', 'ज्वारीचे पीठ', 'jowar', 'jowari', 'मालदांडी'] },
  { canonical: 'Bajra', marathi: 'बाजरी', hindi: 'बाजरा', terms: ['बाजरी', 'बाजरीचे पीठ', 'bajri', 'bajra'] },
  { canonical: 'Sabudana', marathi: 'साबुदाणा', hindi: 'साबूदाना', terms: ['साबुदाणा', 'साबुदाना', 'sabudana', 'sago'] },
  { canonical: 'Murmura', marathi: 'चुरमुरे', hindi: 'मुरमुरा', terms: ['चुरमुरे', 'मुरमुरा', 'कुरमुरे', 'churmure', 'murmura', 'kurmura'] },

  // Dals & Pulses
  { canonical: 'Toor Dal', marathi: 'तूर डाळ', hindi: 'अरहर दाल', terms: ['तूर डाळ', 'तुरीची डाळ', 'तूरडाळ', 'tur dal', 'toor dal', 'arhar dal'] },
  { canonical: 'Chana Dal', marathi: 'चना डाळ', hindi: 'चना दाल', terms: ['चना डाळ', 'हरभरा डाळ', 'chana dal', 'harbhara dal'] },
  { canonical: 'Moong Dal', marathi: 'मूग डाळ', hindi: 'मूंग दाल', terms: ['मूग डाळ', 'मुगाची डाळ', 'moong dal', 'mung dal', 'हिरवे मूग'] },
  { canonical: 'Urad Dal', marathi: 'उडीद डाळ', hindi: 'उड़द दाल', terms: ['उडीद डाळ', 'उडदाची डाळ', 'urad dal', 'udid dal'] },
  { canonical: 'Masoor Dal', marathi: 'मसूर डाळ', hindi: 'मसूर दाल', terms: ['मसूर डाळ', 'मसुराची डाळ', 'masoor dal', 'अख्खा मसूर'] },
  { canonical: 'Chole', marathi: 'काबुली चणे', hindi: 'छोले', terms: ['काबुली चणे', 'काबुली चना', 'छोले', 'chole', 'kabuli chana'] },
  { canonical: 'Matki', marathi: 'मटकी', hindi: 'मटकी', terms: ['मटकी', 'मोड आलेली मटकी', 'matki', 'moth beans'] },
  { canonical: 'Rajma', marathi: 'राजमा', hindi: 'राजमा', terms: ['राजमा', 'rajma', 'red rajma'] },
  { canonical: 'Vatana', marathi: 'वाटाणा', hindi: 'मटर', terms: ['वाटाणा', 'सफेद वाटाणा', 'हिरवा वाटाणा', 'vatana', 'matar'] },

  // Cooking Oils & Ghee
  { canonical: 'Cooking Oil', marathi: 'गोडेतेल', hindi: 'तेल', terms: ['गोडेतेल', 'तेल', 'तेलाची', 'तेलाचे', 'tel', 'oil', 'cooking oil'] },
  { canonical: 'Groundnut Oil', marathi: 'शेंगदाणा तेल', hindi: 'मूंगफली तेल', terms: ['शेंगदाणा तेल', 'shengdana tel', 'groundnut oil', 'peanut oil'] },
  { canonical: 'Sunflower Oil', marathi: 'सूर्यफूल तेल', hindi: 'सूरजमुखी तेल', terms: ['सूर्यफूल तेल', 'sunflower oil', 'फॉर्च्यून तेल', 'फॉर्च्यून'] },
  { canonical: 'Gemini Oil', marathi: 'जेमिनी तेल', hindi: 'जेमिनी तेल', terms: ['जेमिनी तेल', 'जेमिनी', 'gemini oil', 'gemini'] },
  { canonical: 'Mustard Oil', marathi: 'मोहरी तेल', hindi: 'सरसों तेल', terms: ['मोहरी तेल', 'राई तेल', 'mustard oil', 'sarson oil'] },
  { canonical: 'Coconut Oil', marathi: 'खोबरेल तेल', hindi: 'नारियल तेल', terms: ['खोबरेल तेल', 'पॅराशूट', 'पॅराशूट तेल', 'khobrel tel', 'coconut oil', 'parachute'] },
  { canonical: 'Ghee', marathi: 'तूप', hindi: 'घी', terms: ['तूप', 'तूपाची', 'तूपाचा', 'साजूक तूप', 'गायीचे तूप', 'tup', 'toop', 'ghee', 'amul ghee'] },

  // Spices & Condiments
  { canonical: 'Turmeric', marathi: 'हळद', hindi: 'हल्दी', terms: ['हळद', 'हळदी', 'हळदीची', 'halad', 'haldi', 'turmeric', 'हळद पावडर'] },
  { canonical: 'Red Chilli Powder', marathi: 'लाल तिखट', hindi: 'लाल मिर्च', terms: ['लाल तिखट', 'मिरची पावडर', 'तिखट', 'मिरची', 'lal tikhat', 'mirchi powder', 'red chilli powder'] },
  { canonical: 'Jeera', marathi: 'जिरे', hindi: 'जीरा', terms: ['जिरे', 'जिरं', 'जीरा', 'jeera', 'jira', 'cumin'] },
  { canonical: 'Mohari', marathi: 'मोहरी', hindi: 'राई', terms: ['मोहरी', 'राई', 'mohari', 'rai', 'mustard seeds'] },
  { canonical: 'Dhane', marathi: 'धने', hindi: 'धनिया', terms: ['धने', 'धने पावडर', 'धनिया', 'dhane', 'dhaniya', 'coriander seeds'] },
  { canonical: 'Garam Masala', marathi: 'गरम मसाला', hindi: 'गरम मसाला', terms: ['गरम मसाला', 'सुहाना मसाला', 'एव्हरेस्ट मसाला', 'garam masala', 'masala'] },
  { canonical: 'Hing', marathi: 'हिंग', hindi: 'हींग', terms: ['हिंग', 'hing', 'asafoetida'] },
  { canonical: 'Elaichi', marathi: 'वेलची', hindi: 'इलायची', terms: ['वेलची', 'विलायची', 'इलायची', 'velchi', 'elaichi', 'cardamom'] },
  { canonical: 'Lavang', marathi: 'लवंग', hindi: 'लौंग', terms: ['लवंग', 'लावंग', 'lavang', 'laung', 'clove'] },
  { canonical: 'Dalchini', marathi: 'दालचिनी', hindi: 'दालचीनी', terms: ['दालचिनी', 'dalchini', 'cinnamon'] },
  { canonical: 'Methi Seeds', marathi: 'मेथी दाणे', hindi: 'मेथी दाना', terms: ['मेथी दाणे', 'मेथी', 'methi seeds', 'fenugreek'] },
  { canonical: 'Dry Coconut', marathi: 'खोबरं', hindi: 'सूखा नारियल', terms: ['खोबरं', 'सुके खोबरे', 'खोबरे', 'khobare', 'dry coconut'] },

  // Dairy & Daily Essentials
  { canonical: 'Milk', marathi: 'दूध', hindi: 'दूध', terms: ['दूध', 'दुध', 'दुधाची', 'dudh', 'doodh', 'milk', 'गोकुळ दूध', 'अमुल दूध', 'चितळे दूध'] },
  { canonical: 'Tea', marathi: 'चहा', hindi: 'चाय', terms: ['चहा', 'चाहा', 'चहाची', 'चाहाची', 'चहा पावडर', 'चहापत्ती', 'chaha', 'chai', 'tea', 'वाघ बकरी', 'रेड लेबल', 'सोसायटी चहा', 'सुपर डस्ट', 'सूपर डस्ट', 'super dust', 'dust tea'] },
  { canonical: 'Coffee', marathi: 'कॉफी', hindi: 'कॉफ़ी', terms: ['कॉफी', 'coffee', 'nescafe', 'bru'] },
  { canonical: 'Peanuts', marathi: 'शेंगदाणे', hindi: 'मूंगफली', terms: ['शेंगदाणे', 'शेंगदाणा', 'दाणे', 'shengdane', 'dane', 'peanuts', 'groundnuts'] },
  { canonical: 'Cashews', marathi: 'काजू', hindi: 'काजू', terms: ['काजू', 'काजू तुकडा', 'kaju', 'cashew'] },
  { canonical: 'Almonds', marathi: 'बदाम', hindi: 'बादाम', terms: ['बदाम', 'badam', 'almond'] },
  { canonical: 'Kishmish', marathi: 'मनुका', hindi: 'किशमिश', terms: ['मनुका', 'किशमिश', 'manuka', 'kishmish', 'raisins'] },

  // Household & Personal Care
  { canonical: 'Soap', marathi: 'साबण', hindi: 'साबुन', terms: ['साबण', 'अंगाचा साबण', 'कपड्यांचा साबण', 'saban', 'soap', 'लाईफबॉय', 'लक्स', 'डेटॉल', 'संतूर'] },
  { canonical: 'Detergent Powder', marathi: 'डिटर्जंट पावडर', hindi: 'सर्फ', terms: ['निरमा', 'सर्फ', 'डिटर्जंट पावडर', 'टाईड', 'एरिअल', 'detergent', 'surf', 'nirma'] },
  { canonical: 'Dishwash Bar', marathi: 'भांड्यांचा साबण', hindi: 'बर्तन साबुन', terms: ['भांड्यांचा साबण', 'विम बार', 'विम', 'भांडी घासण्याचा साबण', 'vim bar', 'dishwash'] },
  { canonical: 'Matchbox', marathi: 'काडेपेटी', hindi: 'माचिस', terms: ['काडेपेटी', 'माचिस', 'काडीपेटी', 'kadepeti', 'machis', 'matchbox'] },
  { canonical: 'Agarbatti', marathi: 'अगरबत्ती', hindi: 'अगरबत्ती', terms: ['अगरबत्ती', 'अगरबत्त्या', 'धूप', 'agarbatti', 'incense'] },
  { canonical: 'Toothpaste', marathi: 'टूथपेस्ट', hindi: 'टूथपेस्ट', terms: ['कोलगेट', 'पेस्ट', 'टूथपेस्ट', 'colgate', 'toothpaste', 'क्लोजअप'] },
  { canonical: 'Biscuits', marathi: 'बिस्कीट', hindi: 'बिस्कुट', terms: ['बिस्कीट', 'बिस्किट', 'पारले जी', 'गुड डे', 'मारी', 'क्रॅकजॅक', 'biscuit', 'parle g', 'good day'] },
  { canonical: 'Maggi', marathi: 'मॅगी', hindi: 'मैगी', terms: ['मॅगी', 'शेवया', 'नूडल्स', 'maggi', 'noodles'] },

  // Fresh Produce
  { canonical: 'Onion', marathi: 'कांदे', hindi: 'प्याज़', terms: ['कांदे', 'कांदा', 'kande', 'kanda', 'onion'] },
  { canonical: 'Potato', marathi: 'बटाटे', hindi: 'आलू', terms: ['बटाटे', 'बटाटा', 'batate', 'batata', 'potato', 'aloo'] },
  { canonical: 'Garlic', marathi: 'लसूण', hindi: 'लहसुन', terms: ['लसूण', 'लसून', 'lasun', 'garlic'] },
  { canonical: 'Ginger', marathi: 'आले', hindi: 'अदरक', terms: ['आले', 'अद्रक', 'ale', 'adrak', 'ginger'] },
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

  // 1. Remove stutter/echo repetitions (sakhar-sakhar -> sakhar)
  s = deduplicateSpokenTokens(s);

  // 1b. Correct common STT acoustic phonetics in Marathi speech
  s = s.replace(makeUnicodeRegex('वाज\\s+किलो'), 'पाव किलो');
  s = s.replace(makeUnicodeRegex('साकर'), 'साखर');
  s = s.replace(makeUnicodeRegex('साट'), 'साठ');
  s = s.replace(makeUnicodeRegex('शमब'), 'शंभर');
  s = s.replace(makeUnicodeRegex('गरयम|गराम|गिराम|ग्रेम'), 'ग्राम');

  // 2. Convert Devanagari digits [०-९]
  s = s.replace(/[०-९]/g, (d) => DEVANAGARI_DIGITS[d] || d);

  // 3. Remove common spoken filler/connecting words in Marathi (Unicode-safe)
  const fillerRegex = makeUnicodeRegex('आणि|तसेच|त्यानंतर|त्याच्यानंतर|बरं|पुढे|द्या|घ्या|पाहिजे|लाव|टाक|आणखी|आण');
  s = s.replace(fillerRegex, ' , ');

  // 4. Normalizes Marathi numbers, compound hundreds & fractions (e.g. 140, 60, 50, 90, 80, 40, 500, 10, 5, 900, 568, 789, 550, 110, 108)
  s = parseMarathiSpokenNumbers(s);

  // 5. Normalizes units
  for (const { pattern, canonical } of MARATHI_UNITS) {
    s = s.replace(pattern, ` ${canonical} `);
  }

  // 6. Normalizes price indicators (रुपये, रुपयांची, रुपयांचे, रु, rs, rupaye, ruapaye, etc.) (Unicode-safe)
  const priceRegex = makeUnicodeRegex('रुपये|रुपयांची|रुपयांचे|रुपयांचा|रुपया|रु\\.|रु|रूपय|रूपये|रू|rs|rupees|rupee|rupaye|rupay|ruapaye|rupiya|rupiye|rupe|inr|₹|\\/-');
  s = s.replace(priceRegex, ' rs ');

  // 7. Clean multiple spaces and comma separators
  s = s.replace(/\s+/g, ' ').replace(/\s*,\s*/g, ' , ').trim();

  return s;
}

/**
 * Canonicalizes an extracted item name while strictly preserving the spoken language.
 * If spoken in Marathi -> returns Marathi name (साखर, तूर डाळ, पोहे, गोडेतेल, चहा)
 * If spoken in Hindi -> returns Hindi name (चीनी, अरहर दाल, चावल, तेल, चाय)
 * If spoken in English -> returns English name (Sugar, Rice, Oil, Tea)
 */
function canonicalizeMarathiItemName(name, language = 'mr-IN') {
  if (!name || typeof name !== 'string') return '';
  const converted = convertIndicScriptToDevanagari(name);
  const deduped = deduplicateSpokenTokens(converted);
  const clean = deduped.toLowerCase().trim();

  const isDevanagari = /[\u0900-\u097F]/.test(deduped);
  const langLower = String(language || 'mr-IN').toLowerCase();
  const isHindi = langLower.startsWith('hi');
  const isEnglish = langLower.startsWith('en');
  // If language is Marathi or default mr-IN
  const isMarathi = langLower.startsWith('mr') || (!isHindi && !isEnglish);

  // Strip common grammatical post-positions (साखरेची -> साखर, तेलाचे -> तेल)
  const stripped = clean
    .replace(/(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$/gi, '')
    .trim();

  for (const entry of MARATHI_KIRANA_ITEMS) {
    for (const term of entry.terms) {
      const termLower = term.toLowerCase();
      if (
        clean === termLower ||
        stripped === termLower ||
        clean.split(/\s+/).includes(termLower) ||
        clean.includes(termLower)
      ) {
        if (isMarathi) return entry.marathi || entry.canonical;
        if (isHindi) return entry.hindi || entry.canonical;
        if (isEnglish) return entry.canonical;
        return entry.marathi || entry.canonical;
      }
    }
  }

  // Fallback: If in Devanagari, strip suffixes and return user's actual spoken word
  if (isDevanagari) {
    return deduped.replace(/(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$/gi, '').trim();
  }

  // English fallback: Title case
  return clean.replace(/\b\w/g, (c) => c.toUpperCase());
}

module.exports = {
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
