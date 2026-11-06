/**
 * Comprehensive Marathi Kirana Normalizer & Dictionary
 * Designed for extreme scalability across Maharashtra grocery dialects.
 */

// 1. Marathi/Devanagari Digits
const DEVANAGARI_DIGITS = {
  '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
  '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
};

// 2. Comprehensive Marathi & Phonetic Number Words
const MARATHI_NUMBERS = [
  // Fractions & Colloquial Weights (Longest first to avoid partial replacement)
  { pattern: /\b(one\s+and\s+a\s+half)\b/gi, value: '1.5' },
  { pattern: /\b(two\s+and\s+a\s+half)\b/gi, value: '2.5' },
  { pattern: /\b(साडेतीन|sade\s*teen)\b/gi, value: '3.5' },
  { pattern: /\b(साडेचार|sade\s*char)\b/gi, value: '4.5' },
  { pattern: /\b(साडेपाच|sade\s*paach|sade\s*panch)\b/gi, value: '5.5' },
  { pattern: /\b(साडेसहा|sade\s*saha)\b/gi, value: '6.5' },
  { pattern: /\b(साडेसात|sade\s*saat)\b/gi, value: '7.5' },
  { pattern: /\b(साडेआठ|sade\s*aath)\b/gi, value: '8.5' },
  { pattern: /\b(साडेनऊ|sade\s*nau)\b/gi, value: '9.5' },
  { pattern: /\b(साडेदहा|sade\s*daha)\b/gi, value: '10.5' },
  { pattern: /\b(सव्वा|savva|sawa)\b/gi, value: '1.25' },
  { pattern: /\b(दीड|deed|dedh|deedh)\b/gi, value: '1.5' },
  { pattern: /\b(अडीच|adeech|dhai|adhai)\b/gi, value: '2.5' },
  { pattern: /\b(पाऊण|paun|paune|pauna)\b/gi, value: '0.75' },
  { pattern: /\b(अर्धा|अर्धी|अर्धे|ardha|ardhi|ardhe|aadha|adha|half)\b/gi, value: '0.5' },
  { pattern: /\b(पावशेर|paavsher|pavsher)\b/gi, value: '0.25' },
  { pattern: /\b(पाव|paav|pav|quarter)\b/gi, value: '0.25' },

  // Whole Numbers (1 - 100)
  { pattern: /\b(शंभर|shambhar|sau|hundred)\b/gi, value: '100' },
  { pattern: /\b(नव्वद|navvad|navve|nabbe)\b/gi, value: '90' },
  { pattern: /\b(ऐंशी|aishi|ayshi|assi)\b/gi, value: '80' },
  { pattern: /\b(पंचाहत्तर|panchahattar|pachhattar)\b/gi, value: '75' },
  { pattern: /\b(सत्तर|sattar)\b/gi, value: '70' },
  { pattern: /\b(पासष्ट|pasasht|painsath)\b/gi, value: '65' },
  { pattern: /\b(साठ|saath|sath)\b/gi, value: '60' },
  { pattern: /\b(पंचावन्न|panchavanna|pachpan)\b/gi, value: '55' },
  { pattern: /\b(पन्नास|pannas|pachas)\b/gi, value: '50' },
  { pattern: /\b(पंचेचाळीस|panchechalis|paintalis)\b/gi, value: '45' },
  { pattern: /\b(चाळीस|chalis|chaalis)\b/gi, value: '40' },
  { pattern: /\b(पस्तीस|pastis|paintis)\b/gi, value: '35' },
  { pattern: /\b(तीस|tees|tis)\b/gi, value: '30' },
  { pattern: /\b(पंचवीस|panchvis|pachis)\b/gi, value: '25' },
  { pattern: /\b(वीस|vees|bees)\b/gi, value: '20' },
  { pattern: /\b(एकोणीस|ekonis|unnis)\b/gi, value: '19' },
  { pattern: /\b(अठरा|athra|athara|athrah)\b/gi, value: '18' },
  { pattern: /\b(सतरा|satra|satrah)\b/gi, value: '17' },
  { pattern: /\b(सोळा|sola|solah)\b/gi, value: '16' },
  { pattern: /\b(पंधरा|pandhra|pandrah)\b/gi, value: '15' },
  { pattern: /\b(चौदा|chauda|chaudah)\b/gi, value: '14' },
  { pattern: /\b(तेरा|tera|terah)\b/gi, value: '13' },
  { pattern: /\b(बारा|bara|barah)\b/gi, value: '12' },
  { pattern: /\b(अकरा|akara|gyarah)\b/gi, value: '11' },
  { pattern: /\b(दहा|daha|das)\b/gi, value: '10' },
  { pattern: /\b(नऊ|nau|nav)\b/gi, value: '9' },
  { pattern: /\b(आठ|aath|ath)\b/gi, value: '8' },
  { pattern: /\b(सात|saat|sat)\b/gi, value: '7' },
  { pattern: /\b(सहा|saha|chha|chheh)\b/gi, value: '6' },
  { pattern: /\b(पाच|paach|panch|pach)\b/gi, value: '5' },
  { pattern: /\b(चार|chaar|char)\b/gi, value: '4' },
  { pattern: /\b(तीन|teen|tin)\b/gi, value: '3' },
  { pattern: /\b(दोन|don|do|two)\b/gi, value: '2' },
  { pattern: /\b(एक|ek|one)\b/gi, value: '1' },
  { pattern: /\b(शून्य|shunya|zero)\b/gi, value: '0' },
  { pattern: /\b(डझन|दर्जन|dozen)\b/gi, value: '12' },
];

// 3. Marathi Unit Normalization
const MARATHI_UNITS = [
  { pattern: /\b(किलो|किग्र|कि\.ग्रा|kilo|kilos|kg|kgs|kilogram)\b/gi, canonical: 'kg' },
  { pattern: /\b(ग्रॅम|ग्राम|ग्रा|gram|grams|gm|gms|g)\b/gi, canonical: 'g' },
  { pattern: /\b(लिटर|लीटर|litre|litres|liter|liters|ltr|ltrs|l)\b/gi, canonical: 'litre' },
  { pattern: /\b(मिली|मिलीलिटर|ml|mls|millilitre)\b/gi, canonical: 'ml' },
  { pattern: /\b(पुडा|पुडे|पुडी|पाकीट|पाकिटे|packet|packets|pkt|pkts|pouch)\b/gi, canonical: 'packet' },
  { pattern: /\b(नग|पीस|piece|pieces|pcs|pc|item|items)\b/gi, canonical: 'piece' },
  { pattern: /\b(बाटली|बाटल्या|bottle|bottles|btl)\b/gi, canonical: 'bottle' },
  { pattern: /\b(डबा|डबे|खोके|खोका|बॉक्स|box|boxes|carton)\b/gi, canonical: 'box' },
  { pattern: /\b(डझन|दर्जन|dozen|dozens)\b/gi, canonical: 'dozen' },
  { pattern: /\b(तोळा|तोळे|tola)\b/gi, canonical: 'tola' },
];

// 4. Comprehensive Kirana Item Canonical Names & Marathi Phonetics
const MARATHI_KIRANA_ITEMS = [
  // Sweeteners & Staples
  { canonical: 'Sugar', terms: ['साखर', 'साखरेची', 'साखरेचा', 'sakhar', 'sakharachi', 'sakhrechi', 'cheeni', 'chini', 'sugar', 'शक्कर'] },
  { canonical: 'Jaggery', terms: ['गूळ', 'गुळ', 'गुळाची', 'गुळाचा', 'gul', 'gud', 'jaggery', 'कोल्हापुरी गूळ'] },
  { canonical: 'Salt', terms: ['मीठ', 'मिठाचे', 'मिठाचा', 'meeth', 'mith', 'namak', 'salt', 'टाटा मीठ'] },

  // Grains & Flours
  { canonical: 'Rice', terms: ['तांदूळ', 'तांदुळ', 'तांदळाचे', 'तांदळाची', 'tandul', 'tandool', 'chawal', 'rice', 'भात', 'कोलम', 'इंद्रायणी', 'बासमती', 'तुकडा'] },
  { canonical: 'Wheat', terms: ['गहू', 'गव्हाचे', 'गव्हाचा', 'gahu', 'gehu', 'wheat', 'शरबती गहू', 'सीहोर गहू', 'लोकवन गहू'] },
  { canonical: 'Atta', terms: ['आटा', 'पीठ', 'गव्हाचे पीठ', 'कणिक', 'atta', 'aata', 'peeth', 'pith', 'wheat flour', 'चक्की फ्रेश'] },
  { canonical: 'Maida', terms: ['मैदा', 'मैद्याचे', 'maida', 'all purpose flour'] },
  { canonical: 'Besan', terms: ['बेसन', 'चना पीठ', 'हरभरा पीठ', 'डाळीचे पीठ', 'besan', 'gram flour'] },
  { canonical: 'Rava', terms: ['रवा', 'बारीक रवा', 'जाडा रवा', 'सुजी', 'rawa', 'rava', 'sooji', 'suji', 'semolina'] },
  { canonical: 'Poha', terms: ['पोहे', 'पोहा', 'जाडे पोहे', 'पातळ पोहे', 'दगडी पोहे', 'pohe', 'poha'] },
  { canonical: 'Jowar', terms: ['ज्वारी', 'ज्वारीचे पीठ', 'jowar', 'jowari', 'मालदांडी'] },
  { canonical: 'Bajra', terms: ['बाजरी', 'बाजरीचे पीठ', 'bajri', 'bajra'] },
  { canonical: 'Sabudana', terms: ['साबुदाणा', 'साबुदाना', 'sabudana', 'sago'] },
  { canonical: 'Murmura', terms: ['चुरमुरे', 'मुरमुरा', 'कुरमुरे', 'churmure', 'murmura', 'kurmura'] },

  // Dals & Pulses
  { canonical: 'Toor Dal', terms: ['तूर डाळ', 'तुरीची डाळ', 'तूरडाळ', 'tur dal', 'toor dal', 'arhar dal'] },
  { canonical: 'Chana Dal', terms: ['चना डाळ', 'हरभरा डाळ', 'chana dal', 'harbhara dal'] },
  { canonical: 'Moong Dal', terms: ['मूग डाळ', 'मुगाची डाळ', 'moong dal', 'mung dal', 'हिरवे मूग'] },
  { canonical: 'Urad Dal', terms: ['उडीद डाळ', 'उडदाची डाळ', 'urad dal', 'udid dal'] },
  { canonical: 'Masoor Dal', terms: ['मसूर डाळ', 'मसुराची डाळ', 'masoor dal', 'अख्खा मसूर'] },
  { canonical: 'Chole', terms: ['काबुली चणे', 'काबुली चना', 'छोले', 'chole', 'kabuli chana'] },
  { canonical: 'Matki', terms: ['मटकी', 'मोड आलेली मटकी', 'matki', 'moth beans'] },
  { canonical: 'Rajma', terms: ['राजमा', 'rajma', 'red rajma'] },
  { canonical: 'Vatana', terms: ['वाटाणा', 'सफेद वाटाणा', 'हिरवा वाटाणा', 'vatana', 'matar'] },

  // Cooking Oils & Ghee
  { canonical: 'Cooking Oil', terms: ['गोडेतेल', 'तेल', 'तेलाची', 'तेलाचे', 'tel', 'oil', 'cooking oil'] },
  { canonical: 'Groundnut Oil', terms: ['शेंगदाणा तेल', 'shengdana tel', 'groundnut oil', 'peanut oil'] },
  { canonical: 'Sunflower Oil', terms: ['सूर्यफूल तेल', 'sunflower oil', 'फॉर्च्यून तेल', 'फॉर्च्यून'] },
  { canonical: 'Gemini Oil', terms: ['जेमिनी तेल', 'जेमिनी', 'gemini oil', 'gemini'] },
  { canonical: 'Mustard Oil', terms: ['मोहरी तेल', 'राई तेल', 'mustard oil', 'sarson oil'] },
  { canonical: 'Coconut Oil', terms: ['खोबरेल तेल', 'पॅराशूट', 'पॅराशूट तेल', 'khobrel tel', 'coconut oil', 'parachute'] },
  { canonical: 'Ghee', terms: ['तूप', 'तूपाची', 'तूपाचा', 'साजूक तूप', 'गायीचे तूप', 'tup', 'toop', 'ghee', 'amul ghee'] },

  // Spices & Condiments
  { canonical: 'Turmeric', terms: ['हळद', 'हळदी', 'हळदीची', 'halad', 'haldi', 'turmeric', 'हळद पावडर'] },
  { canonical: 'Red Chilli Powder', terms: ['लाल तिखट', 'मिरची पावडर', 'तिखट', 'मिरची', 'lal tikhat', 'mirchi powder', 'red chilli powder'] },
  { canonical: 'Jeera', terms: ['जिरे', 'जिरं', 'जीरा', 'jeera', 'jira', 'cumin'] },
  { canonical: 'Mohari', terms: ['मोहरी', 'राई', 'mohari', 'rai', 'mustard seeds'] },
  { canonical: 'Dhane', terms: ['धने', 'धने पावडर', 'धनिया', 'dhane', 'dhaniya', 'coriander seeds'] },
  { canonical: 'Garam Masala', terms: ['गरम मसाला', 'सुहाना मसाला', 'एव्हरेस्ट मसाला', 'garam masala', 'masala'] },
  { canonical: 'Hing', terms: ['हिंग', 'hing', 'asafoetida'] },
  { canonical: 'Elaichi', terms: ['वेलची', 'विलायची', 'इलायची', 'velchi', 'elaichi', 'cardamom'] },
  { canonical: 'Lavang', terms: ['लवंग', 'लावंग', 'lavang', 'laung', 'clove'] },
  { canonical: 'Dalchini', terms: ['दालचिनी', 'dalchini', 'cinnamon'] },
  { canonical: 'Methi Seeds', terms: ['मेथी दाणे', 'मेथी', 'methi seeds', 'fenugreek'] },
  { canonical: 'Dry Coconut', terms: ['खोबरं', 'सुके खोबरे', 'खोबरे', 'khobare', 'dry coconut'] },

  // Dairy & Daily Essentials
  { canonical: 'Milk', terms: ['दूध', 'दुध', 'दुधाची', 'dudh', 'doodh', 'milk', 'गोकुळ दूध', 'अमुल दूध', 'चितळे दूध'] },
  { canonical: 'Tea', terms: ['चहा', 'चहा पावडर', 'चहापत्ती', 'chaha', 'chai', 'tea', 'वाघ बकरी', 'रेड लेबल', 'सोसायटी चहा'] },
  { canonical: 'Coffee', terms: ['कॉफी', 'coffee', 'nescafe', 'bru'] },
  { canonical: 'Peanuts', terms: ['शेंगदाणे', 'शेंगदाणा', 'दाणे', 'shengdane', 'dane', 'peanuts', 'groundnuts'] },
  { canonical: 'Cashews', terms: ['काजू', 'काजू तुकडा', 'kaju', 'cashew'] },
  { canonical: 'Almonds', terms: ['बदाम', 'badam', 'almond'] },
  { canonical: 'Kishmish', terms: ['मनुका', 'किशमिश', 'manuka', 'kishmish', 'raisins'] },

  // Household & Personal Care
  { canonical: 'Soap', terms: ['साबण', 'अंगाचा साबण', 'कपड्यांचा साबण', 'saban', 'soap', 'लाईफबॉय', 'लक्स', 'डेटॉल', 'संतूर'] },
  { canonical: 'Detergent Powder', terms: ['निरमा', 'सर्फ', 'डिटर्जंट पावडर', 'टाईड', 'एरिअल', 'detergent', 'surf', 'nirma'] },
  { canonical: 'Dishwash Bar', terms: ['भांड्यांचा साबण', 'विम बार', 'विम', 'भांडी घासण्याचा साबण', 'vim bar', 'dishwash'] },
  { canonical: 'Matchbox', terms: ['काडेपेटी', 'माचिस', 'काडीपेटी', 'kadepeti', 'machis', 'matchbox'] },
  { canonical: 'Agarbatti', terms: ['अगरबत्ती', 'अगरबत्त्या', 'धूप', 'agarbatti', 'incense'] },
  { canonical: 'Toothpaste', terms: ['कोलगेट', 'पेस्ट', 'टूथपेस्ट', 'colgate', 'toothpaste', 'क्लोजअप'] },
  { canonical: 'Biscuits', terms: ['बिस्कीट', 'बिस्किट', 'पारले जी', 'गुड डे', 'मारी', 'क्रॅकजॅक', 'biscuit', 'parle g', 'good day'] },
  { canonical: 'Maggi', terms: ['मॅगी', 'शेवया', 'नूडल्स', 'maggi', 'noodles'] },

  // Fresh Produce
  { canonical: 'Onion', terms: ['कांदे', 'कांदा', 'kande', 'kanda', 'onion'] },
  { canonical: 'Potato', terms: ['बटाटे', 'बटाटा', 'batate', 'batata', 'potato', 'aloo'] },
  { canonical: 'Garlic', terms: ['लसूण', 'लसून', 'lasun', 'garlic'] },
  { canonical: 'Ginger', terms: ['आले', 'अद्रक', 'ale', 'adrak', 'ginger'] },
];

/**
 * Pre-processes spoken Marathi transcript before LLM or Regex parsing:
 * 1. Converts Devanagari numerals to ASCII.
 * 2. Standardizes numbers and fractions.
 * 3. Standardizes units.
 * 4. Cleans colloquial filler speech.
 */
function normalizeMarathiTranscript(text) {
  if (!text || typeof text !== 'string') return '';

  let s = text.trim();

  // 1. Convert Devanagari digits
  s = s.replace(/[०-९]/g, (d) => DEVANAGARI_DIGITS[d] || d);

  // 2. Remove common spoken filler/connecting words in Marathi
  s = s.replace(/\b(आणि|तसेच|त्यानंतर|त्याच्यानंतर|बरं|पुढे|द्या|घ्या|पाहिजे|लाव|टाक|आणखी|आण)\b/gi, ' , ');

  // 3. Normalizes Marathi numbers & fractions
  for (const { pattern, value } of MARATHI_NUMBERS) {
    s = s.replace(pattern, ` ${value} `);
  }

  // 4. Normalizes units
  for (const { pattern, canonical } of MARATHI_UNITS) {
    s = s.replace(pattern, ` ${canonical} `);
  }

  // 5. Normalizes price indicators (रुपये, रुपयांची, रुपयांचे, रु, rs)
  s = s.replace(/\b(रुपये|रुपयांची|रुपयांचे|रुपयांचा|रुपया|रु\.|रु|rs|rupees|inr)\b/gi, ' rs ');

  // 6. Clean multiple spaces and comma separators
  s = s.replace(/\s+/g, ' ').replace(/\s*,\s*/g, ' , ').trim();

  return s;
}

/**
 * Canonicalizes an extracted item name using Marathi Kirana dictionary
 */
function canonicalizeMarathiItemName(name) {
  if (!name || typeof name !== 'string') return '';
  const clean = name.trim().toLowerCase();

  // Strip common Marathi grammatical post-positions (साखरेची -> साखर, तेलाचे -> तेल)
  const stripped = clean
    .replace(/(?:ची|चे|चा|च्या|ला|मध्ये|वाले)$/gi, '')
    .trim();

  for (const entry of MARATHI_KIRANA_ITEMS) {
    for (const term of entry.terms) {
      const termLower = term.toLowerCase();
      if (clean === termLower || stripped === termLower || clean.includes(termLower)) {
        return entry.canonical;
      }
    }
  }

  // Fallback: Title case original
  return clean.replace(/\b\w/g, (c) => c.toUpperCase());
}

module.exports = {
  normalizeMarathiTranscript,
  canonicalizeMarathiItemName,
  MARATHI_NUMBERS,
  MARATHI_UNITS,
  MARATHI_KIRANA_ITEMS,
};
