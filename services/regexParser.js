const {
  normalizeMarathiTranscript,
  canonicalizeMarathiItemName,
} = require('./marathiNormalizer');

const NUMBER_WORDS_MAP = {
  zero: 0, shunya: 0, 'शून्य': 0,
  half: 0.5, aadha: 0.5, adha: 0.5, ardha: 0.5, 'आधा': 0.5, 'अर्धा': 0.5,
  quarter: 0.25, paav: 0.25, pav: 0.25, 'पाव': 0.25,
  dedh: 1.5, deedh: 1.5, 'दीड': 1.5, 'डेढ़': 1.5,
  dhai: 2.5, adhai: 2.5, 'अडीच': 2.5, 'ढाई': 2.5,
  savva: 1.25, sawa: 1.25, 'सव्वा': 1.25, 'सवा': 1.25,
  paun: 0.75, paune: 0.75, 'पाऊण': 0.75, 'पौने': 0.75,
  one: 1, ek: 1, 'एक': 1,
  two: 2, do: 2, don: 2, 'दो': 2, 'दोन': 2,
  three: 3, teen: 3, tin: 3, 'तीन': 3,
  four: 4, char: 4, chaar: 4, 'चार': 4,
  five: 5, panch: 5, paanch: 5, pach: 5, 'पाच': 5, 'पाँच': 5,
  six: 6, chha: 6, chheh: 6, saha: 6, 'सहा': 6, 'छह': 6,
  seven: 7, saat: 7, sat: 7, 'सात': 7,
  eight: 8, aath: 8, ath: 8, 'आठ': 8,
  nine: 9, nau: 9, nav: 9, 'नऊ': 9, 'नौ': 9,
  ten: 10, das: 10, daha: 10, 'दहा': 10, 'दस': 10,
  eleven: 11, gyarah: 11, akara: 11, 'अकरा': 11,
  twelve: 12, barah: 12, bara: 12, 'बारा': 12, dozen: 12, 'डझन': 12, 'दर्जन': 12,
  thirteen: 13, terah: 13, tera: 13, 'तेरा': 13,
  fourteen: 14, chaudah: 14, chauda: 14, 'चौदा': 14,
  fifteen: 15, pandrah: 15, pandhra: 15, 'पंधरा': 15,
  sixteen: 16, solah: 16, sola: 16, 'सोळा': 16,
  seventeen: 17, satrah: 17, satra: 17, 'सतरा': 17,
  eighteen: 18, athrah: 18, athara: 18, 'अठरा': 18,
  nineteen: 19, unnis: 19, ekonis: 19, 'एकोणीस': 19,
  twenty: 20, bees: 20, vees: 20, 'वीस': 20, 'बीस': 20,
  twentyfive: 25, pachis: 25, panchvis: 25, 'पंचवीस': 25, 'पच्चीस': 25,
  thirty: 30, tees: 30, tis: 30, 'तीस': 30,
  forty: 40, chalis: 40, chaalis: 40, 'चाळीस': 40, 'चालीस': 40,
  fifty: 50, pachas: 50, pannas: 50, 'पन्नास': 50, 'पचास': 50,
  sixty: 60, saath: 60, sath: 60, 'साठ': 60,
  seventy: 70, sattar: 70, 'सत्तर': 70,
  eighty: 80, assi: 80, ayshi: 80, 'ऐंशी': 80, 'अस्सी': 80,
  ninety: 90, navve: 90, nabbe: 90, 'नव्वद': 90, 'नब्बे': 90,
  hundred: 100, sau: 100, shambhar: 100, 'शंभर': 100, 'सौ': 100,
};

const UNIT_MAP = {
  kg: 'kg', kgs: 'kg', kilo: 'kg', kilos: 'kg', kilogram: 'kg', kilograms: 'kg', 'k g': 'kg', 'k.g': 'kg', 'किलो': 'kg', 'किग्रा': 'kg',
  gm: 'gm', gms: 'gm', gram: 'gm', grams: 'gm', g: 'gm', 'ग्रॅम': 'gm', 'ग्राम': 'gm',
  l: 'litre', ltr: 'litre', ltrs: 'litre', litre: 'litre', litres: 'litre', liter: 'litre', liters: 'litre', 'लिटर': 'litre', 'लीटर': 'litre',
  ml: 'ml', mls: 'ml', milli: 'ml', millilitre: 'ml', milliliter: 'ml', 'मिली': 'ml',
  box: 'box', boxes: 'box', carton: 'box', cartons: 'box', 'बॉक्स': 'box', 'खोके': 'box', 'खोका': 'box', 'डबा': 'box',
  pcs: 'pcs', pc: 'pcs', piece: 'pcs', pieces: 'pcs', item: 'pcs', items: 'pcs', 'पीस': 'pcs', nag: 'nag', 'नग': 'nag',
  puda: 'packet', pude: 'packet', pkt: 'packet', pkts: 'packet', packet: 'packet', packets: 'packet', pouch: 'packet', pouches: 'packet', 'पुडा': 'packet', 'पाकीट': 'packet',
  dozen: 'dozen', 'डझन': 'dozen', 'दर्जन': 'dozen',
  btl: 'bottle', bottle: 'bottle', bottles: 'bottle', 'बाटली': 'bottle',
};

const NAME_MAP = {
  cheeni: 'Sugar', sakhar: 'Sugar', sugar: 'Sugar', 'साखर': 'Sugar', 'चीनी': 'Sugar',
  rawa: 'Rava', rava: 'Rava', sooji: 'Rava', suji: 'Rava', 'रवा': 'Rava', 'सुजी': 'Rava',
  maida: 'Maida', 'मैदा': 'Maida',
  tel: 'Oil', oil: 'Oil', 'तेल': 'Oil',
  tandul: 'Rice', chawal: 'Rice', rice: 'Rice', 'तांदूळ': 'Rice', 'चावल': 'Rice',
  atta: 'Atta', pith: 'Atta', 'आटा': 'Atta',
  chaha: 'Tea', chai: 'Tea', tea: 'Tea', 'चहा': 'Tea', 'चाय': 'Tea',
  doodh: 'Milk', dudh: 'Milk', milk: 'Milk', 'दूध': 'Milk',
  saban: 'Soap', soap: 'Soap', 'साबण': 'Soap',
  biscuit: 'Biscuit', biscuits: 'Biscuit', 'बिस्कीट': 'Biscuit',
  salt: 'Salt', meeth: 'Salt', 'मीठ': 'Salt', 'नमक': 'Salt',
  maggi: 'Maggi', 'मॅगी': 'Maggi',
};

function normalizeName(name, language = 'mr-IN', outputLang = null) {
  if (!name) return 'Item';
  const canonical = canonicalizeMarathiItemName(name, language, outputLang);
  if (canonical) return canonical;
  const clean = name.trim().toLowerCase();
  if (NAME_MAP[clean]) return NAME_MAP[clean];
  return clean.replace(/\b\w/g, (c) => c.toUpperCase());
}

function normalizeNumberWords(str) {
  if (!str) return '';
  let s = str.replace(/[०-९]/g, (d) => ({
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
  }[d] || d));

  const sortedWords = Object.keys(NUMBER_WORDS_MAP).sort((a, b) => b.length - a.length);
  for (const word of sortedWords) {
    const val = NUMBER_WORDS_MAP[word];
    const regex = new RegExp(`(?<=^|[\\s,;+])${word}(?=[\\s,;+]|$)`, 'gi');
    s = s.replace(regex, String(val));
  }
  return s;
}

function parseBillWithRegex(transcript, options = {}) {
  const priceMode = options.priceMode || 'per_unit';
  const language = options.language || 'mr-IN';
  const outputLang = options.outputLang || null;
  if (!transcript || !transcript.trim()) return [];

  let text = normalizeMarathiTranscript(transcript);
  text = normalizeNumberWords(text);
  text = text.replace(/[,;+\n]+/g, ' , ');
  text = text.replace(/\b(and|aur|ani|va|then|next|after that)\b/gi, ' , ');

  const unitListStr = Object.keys(UNIT_MAP).sort((a, b) => b.length - a.length).join('|');
  text = text.replace(new RegExp(`(\\d+(?:\\.\\d+)?)\\s*(${unitListStr})`, 'gi'), '$1 $2');
  text = text.replace(/(\d+(?:\.\d+)?)\s*(rs|rupees|rupaye|rupay|रुपये|रुपया|रू|₹|\/-)/gi, '$1 rs');

  const unitRegex = `(?:${unitListStr})`;
  const currRegex = `(?:rs|rupees|rupaye|rupay|रुपये|रुपया|रू|₹|\\/-)`;

  // Pattern A: <name> <qty> <unit> <price> <rs>
  const patternA = new RegExp(
    `([A-Za-z\\u0900-\\u097F][A-Za-z\\u0900-\\u097F\\s-]*?)\\s+(\\d+(?:\\.\\d+)?)\\s*(${unitRegex})\\s+(\\d+(?:\\.\\d+)?)\\s*${currRegex}`,
    'gi'
  );

  // Pattern B: <qty> <unit> <name> <price> <rs>
  const patternB = new RegExp(
    `(\\d+(?:\\.\\d+)?)\\s*(${unitRegex})\\s+([A-Za-z\\u0900-\\u097F][A-Za-z\\u0900-\\u097F\\s-]*?)\\s+(\\d+(?:\\.\\d+)?)\\s*${currRegex}`,
    'gi'
  );

  // Pattern E: <qty> <name> <unit> <price> <rs> (e.g. 2 parle box 1280 rs)
  const patternE = new RegExp(
    `(\\d+(?:\\.\\d+)?)\\s+([A-Za-z\\u0900-\\u097F][A-Za-z\\u0900-\\u097F\\s-]*?)\\s+(${unitRegex})\\s+(\\d+(?:\\.\\d+)?)\\s*${currRegex}`,
    'gi'
  );

  const matchedSpans = [];

  const addMatch = (start, end, rawName, rawQty, rawUnit, rawPrice) => {
    const overlaps = matchedSpans.some(
      (s) => (start >= s.start && start < s.end) || (end > s.start && end <= s.end)
    );
    if (overlaps) return;

    const qty = isNaN(rawQty) || rawQty <= 0 ? 1 : rawQty;
    const unit = UNIT_MAP[rawUnit.toLowerCase()] || rawUnit.toLowerCase();
    const cleanName = normalizeName(rawName.replace(/^[,\s]+|[,\s]+$/g, ''), language, outputLang);
    const priceVal = isNaN(rawPrice) || rawPrice < 0 ? 0 : rawPrice;

    const rate = priceMode === 'line_total' && qty > 0 ? parseFloat((priceVal / qty).toFixed(2)) : priceVal;
    const amount = Math.round(rate * qty * 100) / 100;

    matchedSpans.push({
      start,
      end,
      item: {
        id: 'voice_' + Math.random().toString(36).substring(2, 9),
        name: cleanName,
        quantity: qty,
        unit,
        price: rate,
        amount,
      },
    });
  };

  for (const m of text.matchAll(patternA)) {
    addMatch(m.index, m.index + m[0].length, m[1], parseFloat(m[2]), m[3], parseFloat(m[4]));
  }

  for (const m of text.matchAll(patternB)) {
    addMatch(m.index, m.index + m[0].length, m[3], parseFloat(m[1]), m[2], parseFloat(m[4]));
  }

  for (const m of text.matchAll(patternE)) {
    addMatch(m.index, m.index + m[0].length, m[2], parseFloat(m[1]), m[3], parseFloat(m[4]));
  }

  matchedSpans.sort((a, b) => a.start - b.start);
  return matchedSpans.map((s) => s.item);
}

module.exports = {
  parseBillWithRegex,
  normalizeNumberWords,
  normalizeName,
};

