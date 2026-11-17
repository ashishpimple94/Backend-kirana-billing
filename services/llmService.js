/**
 * Unified LLM Audio Parser Service
 * Supports Gemini (gemini-2.5-flash inline audio) as default,
 * and OpenAI (Whisper / gpt-4o-mini-transcribe + gpt-4o-mini) as alternative.
 */

const {
  deduplicateSpokenTokens,
  convertIndicScriptToDevanagari,
  canonicalizeMarathiItemName,
  normalizeMarathiTranscript,
} = require('./marathiNormalizer');
const { parseBillWithRegex } = require('./regexParser');

const SYSTEM_PROMPT = `You are an expert bilingual Kirana Billing Assistant specialized in Indian dialects (Marathi, Hindi, English, and Hinglish).
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
- Hundreds: शंभर/एकशे/एकसे=100, दोनशे/दोनसे=200, तीनशे/तीनसे=300, चारशे/चारसे=400, पाचशे/पाचसे=500, सहाशे/सहासे=600, सातशे/सातसे=700, आठशे/आठसे=800, नऊशे/नऊसे/नवशे=900, एक हजार=1000.
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
- "एक किलो सरगम पत्ती चहा ५५० साडेपाचशे रुपये" / "ek kilo sargam patti chaha 550 sade pacahsherupaye" -> name: "सरगम पत्ती चहा", quantity: 1, unit: "kg", price: 550
- "पाव किलो २५० ग्रॅम सुपर डस्ट ७० सत्तर रुपये" / "pav kilo 250 gm super dust 70 sattar rupaye" -> name: "सुपर डस्ट चहा", quantity: 250, unit: "gm", price: 70
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
One object per item, in the order spoken.`;

const JSON_SCHEMA = {
  type: 'OBJECT',
  properties: {
    transcript: { type: 'STRING' },
    items: {
      type: 'ARRAY',
      items: {
        type: 'OBJECT',
        properties: {
          name: { type: 'STRING' },
          quantity: { type: 'NUMBER' },
          unit: { type: 'STRING' },
          price: { type: 'NUMBER' },
        },
        required: ['name', 'quantity', 'unit', 'price'],
      },
    },
  },
  required: ['transcript', 'items'],
};

/**
 * Standardizes units to canonical abbreviations
 */
function canonicalizeUnit(unit) {
  if (!unit) return 'piece';
  const u = String(unit).trim().toLowerCase();
  if (['kg', 'kgs', 'kilo', 'kilos', 'kilogram', 'kilograms', 'किलो', 'किग्र', 'कि.ग्रा', 'शेर'].includes(u)) return 'kg';
  if (['g', 'gm', 'gms', 'gram', 'grams', 'ग्रॅम', 'ग्राम', 'ग्रा', 'पावशेर'].includes(u)) return 'g';
  if (['l', 'ltr', 'ltrs', 'litre', 'litres', 'liter', 'liters', 'लिटर', 'लीटर'].includes(u)) return 'litre';
  if (['ml', 'mls', 'millilitre', 'मिली', 'मिलीलिटर'].includes(u)) return 'ml';
  if (['packet', 'packets', 'pkt', 'pkts', 'puda', 'pude', 'pudi', 'पुडा', 'पुडे', 'पुडी', 'पाकीट', 'पाकिटे'].includes(u)) return 'packet';
  if (['box', 'boxes', 'carton', 'cartons', 'बॉक्स', 'खोके', 'खोका', 'डबा', 'डबे'].includes(u)) return 'box';
  if (['dozen', 'dozens', 'डझन', 'दर्जन'].includes(u)) return 'dozen';
  if (['bottle', 'bottles', 'btl', 'बाटली', 'बाटल्या'].includes(u)) return 'bottle';
  if (['tola', 'tole', 'तोळा', 'तोळे'].includes(u)) return 'tola';
  if (['piece', 'pieces', 'pcs', 'pc', 'item', 'items', 'nag', 'पीस', 'नग'].includes(u)) return 'piece';
  return u;
}

/**
 * Normalizes item names using the comprehensive Marathi Kirana database
 * Supports outputLang: 'en' for English bill display, or 'mr' for Marathi.
 */
function normalizeItemName(rawName, language = 'mr-IN', outputLang = null) {
  if (!rawName) return '';
  const converted = convertIndicScriptToDevanagari(rawName);
  const deduped = deduplicateSpokenTokens(converted);
  const matched = canonicalizeMarathiItemName(deduped, language, outputLang);
  if (matched) return matched;

  const clean = deduped.trim();
  const isEnglish = String(outputLang || '').toLowerCase().startsWith('en') || String(language || '').toLowerCase().startsWith('en');
  if (/[\u0900-\u097F]/.test(clean)) {
    const stripped = clean.replace(/(?:ची|चे|चा|च्या|ला|मध्ये|वाले|वाली|वाला)$/gi, '').trim();
    if (isEnglish) {
      const { devanagariToLatin } = require('./marathiNormalizer');
      return devanagariToLatin ? devanagariToLatin(stripped) : stripped;
    }
    return stripped;
  }
  return clean.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Validates parsed items:
 * name not empty, quantity > 0, price >= 0
 */
function sanitizeItems(rawItems, priceMode = 'per_unit', language = 'mr-IN', outputLang = null) {
  if (!Array.isArray(rawItems)) return [];
  const valid = [];

  for (const item of rawItems) {
    if (!item) continue;
    let rawNameStr = String(item.name || item.item || '').trim();
    // Guardrail: Strip stray currency/rate/unit tokens that occasionally leak into name
    rawNameStr = rawNameStr.replace(/\b(?:\d+(?:\.\d+)?\s*(?:kg|kilo|gm|g|gram|litre|l|ml|packet|box|dozen|pcs|rs|रुपये|रु|रू))\b/gi, '').trim();
    if (!rawNameStr || /^[\d\s.,;+!?-]+$/.test(rawNameStr)) continue;

    const name = normalizeItemName(rawNameStr, language, outputLang);
    if (!name || /^[\d\s.,;+!?-]+$/.test(name)) continue;

    // Guardrail: Quantity validation & clamping
    let quantity = parseFloat(item.quantity || item.qty);
    if (isNaN(quantity) || quantity <= 0) {
      quantity = 1;
    } else if (quantity > 10000) {
      quantity = 10000;
    }

    // Guardrail: Price validation & clamping (reject hallucinated 100000+ amounts)
    let price = parseFloat(item.price || item.rate || 0);
    if (isNaN(price) || price < 0 || price >= 15000) {
      price = 0;
    }

    const unit = canonicalizeUnit(item.unit);
    let amount = Math.round(quantity * price * 100) / 100;

    // Handle grams (250gm, 500gm, 100gm, etc.):
    // Spoken price is the price for that weight portion (e.g. 250gm tea @ 110 rs, 500gm sugar @ 30 rs).
    // Amount is 110 rs. Price is per-kg rate ((price / quantity) * 1000) so frontend cart math works seamlessly.
    if ((unit === 'g' || unit === 'gm') && quantity >= 20) {
      amount = price;
      price = parseFloat(((price / quantity) * 1000).toFixed(2));
    } else if (priceMode === 'line_total' && quantity > 0) {
      price = parseFloat((price / quantity).toFixed(2));
      amount = Math.round(price * quantity * 100) / 100;
    }

    valid.push({
      id: 'voice_' + Math.random().toString(36).substring(2, 9),
      name,
      quantity,
      unit,
      price,
      amount,
    });
  }

  return valid;
}

/**
 * Gemini Provider implementation:
 * Uses gemini-2.5-flash with inline audio data and responseMimeType: "application/json".
 */
class GeminiProvider {
  constructor(apiKey) {
    this.apiKey = apiKey || process.env.GEMINI_API_KEY;
  }

  async parseAudio({ audioBuffer, mimeType = 'audio/mp4', language = 'mr-IN', priceMode = 'per_unit', outputLang = null }) {
    if (!this.apiKey) {
      throw new Error('GEMINI_API_KEY is not set in environment variables');
    }

    // Normalize MIME types to what Gemini accepts.
    // React Native / Android sometimes sends audio/x-m4a or application/octet-stream.
    let normalizedMime = mimeType || 'audio/mp4';
    if (normalizedMime === 'audio/x-m4a' || normalizedMime === 'audio/m4a') normalizedMime = 'audio/mp4';
    if (normalizedMime === 'application/octet-stream') normalizedMime = 'audio/mp4';
    if (normalizedMime === 'audio/aac') normalizedMime = 'audio/aac'; // Gemini supports this

    const base64Audio = audioBuffer.toString('base64');
    const models = ['gemini-2.5-flash', 'gemini-1.5-flash'];

    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');
    const langPrompt = isEnglishOutput
      ? `${SYSTEM_PROMPT}\nNOTE: User spoke in ${language}, BUT wants the final bill items written in simple PHONETIC ENGLISH / Latin script matching their exact Marathi spoken words (e.g., "Sakhar", "Maida", "Rawa", "Shengdane", "Chaha", "Gul", "Shabu", "Sarki Pend", "Pohe", "Godetel", "Meeth", "Dudh", "Tup"). DO NOT translate into dictionary English words (e.g. NEVER output "Sugar", "Peanuts", "Semolina", "Jaggery"). Keep it as the exact spoken Marathi words spelled in English letters.\nAudio input follows.`
      : `${SYSTEM_PROMPT}\nUser preferred language hint: ${language}. Audio input follows.`;

    let lastError = null;
    for (const model of models) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${this.apiKey}`;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 28000);

        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            contents: [
              {
                parts: [
                  { text: langPrompt },
                  {
                    inlineData: {
                      mimeType: normalizedMime,
                      data: base64Audio,
                    },
                  },
                ],
              },
            ],
            generationConfig: {
              temperature: 0,
              responseMimeType: 'application/json',
              responseSchema: JSON_SCHEMA,
            },
          }),
        });

        clearTimeout(timeout);

        if (!response.ok) {
          const errText = await response.text();
          lastError = new Error(`Gemini API error (${response.status}): ${errText}`);
          continue;
        }

        const data = await response.json();
        const textResponse = data?.candidates?.[0]?.content?.parts?.[0]?.text;
        if (!textResponse) {
          lastError = new Error('Empty response content from Gemini');
          continue;
        }

        // Clean code fences if any and parse JSON safely
        const cleanJson = textResponse.replace(/```(?:json)?/gi, '').replace(/```/g, '').trim();
        const parsed = JSON.parse(cleanJson);

        const transcript = convertIndicScriptToDevanagari(String(parsed.transcript || '').trim());
        const items = sanitizeItems(parsed.items, priceMode, language, outputLang);

        return {
          transcript,
          items,
          provider: 'gemini',
          model,
        };
      } catch (err) {
        lastError = err;
      }
    }

    throw lastError || new Error('Failed to parse audio with Gemini models');
  }

  async parseTranscript({ transcript, language = 'mr-IN', priceMode = 'per_unit', outputLang = null }) {
    if (!this.apiKey) {
      throw new Error('GEMINI_API_KEY is not set in environment variables');
    }

    const preNormalized = normalizeMarathiTranscript(transcript);
    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');

    const prompt = `${SYSTEM_PROMPT}
${isEnglishOutput ? 'NOTE: Output all item names in simple PHONETIC ENGLISH / Latin alphabet matching their exact Marathi spoken words (e.g., "Sakhar", "Maida", "Rawa", "Shengdane", "Chaha", "Gul", "Shabu", "Sarki Pend", "Pohe", "Godetel", "Meeth", "Dudh", "Tup"). DO NOT translate to English dictionary words (e.g. NEVER output Sugar, Peanuts, Jaggery). Use the exact Marathi words spelled in English letters.' : ''}

Extract items from this counter billing transcript:
Spoken Transcript: "${transcript}"
Normalized Words: "${preNormalized}"
Language: ${language}
Price Mode: "${priceMode}"`;

    const models = ['gemini-2.5-flash', 'gemini-1.5-flash'];
    let lastError = null;

    for (const model of models) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${this.apiKey}`;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 15000);

        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            contents: [{ parts: [{ text: prompt }] }],
            generationConfig: {
              temperature: 0,
              responseMimeType: 'application/json',
            },
          }),
        });

        clearTimeout(timeout);

        if (!response.ok) {
          const errText = await response.text();
          lastError = new Error(`Gemini API error (${response.status}): ${errText}`);
          continue;
        }

        const data = await response.json();
        const textResponse = data?.candidates?.[0]?.content?.parts?.[0]?.text;
        if (!textResponse) {
          lastError = new Error('Empty response content from Gemini');
          continue;
        }

        const cleanJson = textResponse.replace(/```(?:json)?/gi, '').replace(/```/g, '').trim();
        const parsed = JSON.parse(cleanJson);
        const rawItems = Array.isArray(parsed) ? parsed : (parsed.items || []);
        const items = sanitizeItems(rawItems, priceMode, language, outputLang);

        return {
          transcript,
          items,
          provider: 'gemini',
          model,
        };
      } catch (err) {
        lastError = err;
      }
    }

    throw lastError || new Error('Failed to parse transcript with Gemini models');
  }
}

/**
 * OpenAI Provider implementation (Alternative swappable provider):
 * Uses Whisper / gpt-4o-mini-transcribe + gpt-4o-mini.
 */
class OpenAIProvider {
  constructor(apiKey) {
    this.apiKey = apiKey || process.env.OPENAI_API_KEY;
  }

  async parseAudio({ audioBuffer, mimeType = 'audio/mp4', language = 'mr-IN', priceMode = 'per_unit', outputLang = null }) {
    if (!this.apiKey) {
      throw new Error('OPENAI_API_KEY is not set in environment variables');
    }

    // Step 1: Transcribe using Whisper
    const formData = new FormData();
    const blob = new Blob([audioBuffer], { type: mimeType });
    formData.append('file', blob, 'audio.m4a');
    formData.append('model', 'whisper-1');
    if (language) formData.append('language', language.split('-')[0]);
    // Guide Whisper with realistic Marathi, Hindi & English kirana phrases, brand names, compound numbers and grams
    formData.append('prompt', 'मराठी किराणा बिल: १ किलो सरगम पत्ती चहा ५५० साडेपाचशे रुपये, पाव किलो २५० ग्रॅम सुपर डस्ट ७० सत्तर रुपये, sargam patti chaha, super dust chaha, १ किलो साखर ६० रुपये, २ किलो मैदा ५० रुपये, १ किलो रवा ५० रुपये, २ किलो शेंगदाणे १४० एकशे चाळीस रुपये, १ किलो काजू १३५ एकशे पस्तीस रुपये, १ किलो बदाम १९० एकशे नव्वद रुपये, १ किलो चारोळी ९८० नऊशे ऐंशी रुपये, २ बॉक्स साबण ५००० पाच हजार रुपये, २२२० दोन हजार दोनशे वीस रुपये, २२३० दोन हजार दोनशे तीस रुपये, १०००० दहा हजार रुपये, २५० ग्रॅम (250gm) चहा ११० रुपये, ५०० ग्रॅम (500gm) साखर २५ रुपये, १०० ग्रॅम (100gm), १० ग्रॅम (10gm) वेलची १ तोळा, 85, 95, 25, 55, 45, 98, 99, 70, 75, 65, 15, 135, 140, 190, 550, 650, 750, 950, 980, 2220, 2230, 5000, 10000, ekshe pastis, ekse pastis, ekshe chalis, ekse chalis, ekshe navvad, ekse navvad, sade pacahshe, sade pachshe, pachse pannas, naushe ayshi, navshe aishi, don hajar donshe vees, don hajar donshe tees, pach hajar, paach hajar, panch hazar, daha hajar, das hazar.');

    const whisperRes = await fetch('https://api.openai.com/v1/audio/transcriptions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.apiKey}` },
      body: formData,
    });

    if (!whisperRes.ok) {
      const err = await whisperRes.text();
      throw new Error(`OpenAI Whisper error: ${err}`);
    }

    const whisperData = await whisperRes.json();
    const rawTranscript = whisperData.text || '';
    if (!rawTranscript) {
      return { transcript: '', items: [], provider: 'openai' };
    }

    // Convert any misidentified Indic script (e.g. Gujarati chars) directly to Devanagari Marathi
    const transcript = convertIndicScriptToDevanagari(rawTranscript);
    const preNormalized = normalizeMarathiTranscript(transcript);

    // Fast-Path: Immediately run our local regex parser (takes 2ms, saves 2.5s GPT call!)
    const regexItems = parseBillWithRegex(transcript, { priceMode, language, outputLang });
    if (Array.isArray(regexItems) && regexItems.length > 0) {
      console.log(`[OpenAI Fast-Path HIT] Extracted ${regexItems.length} items in 2ms from: "${transcript}"`);
      return {
        transcript,
        items: sanitizeItems(regexItems, priceMode, language, outputLang),
        provider: 'openai-fastpath',
        model: 'whisper-1 + fastpath',
      };
    }

    // Step 2: Extract items using gpt-4o-mini
    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');
    const promptHint = isEnglishOutput
      ? `Language: English letters output. Spoken language is ${language}. Output all item names in simple PHONETIC ENGLISH matching exact Marathi spoken words (e.g. Sakhar, Maida, Rawa, Shengdane, Chaha, Gul, Shabu, Sarki Pend, Pohe, Godetel, Meeth, Dudh, Tup). DO NOT translate to dictionary words (do NOT output Sugar, Peanuts, Jaggery).\nSpoken Transcript: "${transcript}"\nNormalized Words: "${preNormalized}"`
      : `Language: Marathi (Pure Devanagari script only, NEVER Gujarati or English transliteration).\nSpoken Transcript: "${transcript}"\nNormalized Words: "${preNormalized}"`;

    const chatRes = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        temperature: 0,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: promptHint },
        ],
      }),
    });

    if (!chatRes.ok) {
      const err = await chatRes.text();
      throw new Error(`OpenAI Chat error: ${err}`);
    }

    const chatData = await chatRes.json();
    const content = chatData.choices?.[0]?.message?.content || '{}';
    const parsed = JSON.parse(content);
    const items = sanitizeItems(parsed.items, priceMode, language, outputLang);

    return {
      transcript: convertIndicScriptToDevanagari(parsed.transcript || transcript),
      items,
      provider: 'openai',
      model: 'whisper-1 + gpt-4o-mini',
    };
  }

  async parseTranscript({ transcript, language = 'mr-IN', priceMode = 'per_unit', outputLang = null }) {
    if (!this.apiKey) {
      throw new Error('OPENAI_API_KEY is not set in environment variables');
    }

    // Fast-Path: Run local regex parser in 2ms before calling OpenAI
    const regexItems = parseBillWithRegex(transcript, { priceMode, language, outputLang });
    if (Array.isArray(regexItems) && regexItems.length > 0) {
      console.log(`[OpenAI Fast-Path HIT] parseTranscript: ${regexItems.length} items in 2ms`);
      return {
        transcript,
        items: sanitizeItems(regexItems, priceMode, language, outputLang),
        provider: 'openai-fastpath',
        model: 'fastpath',
      };
    }

    const preNormalized = normalizeMarathiTranscript(transcript);
    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');

    const promptHint = isEnglishOutput
      ? `NOTE: User spoke in ${language}, BUT wants the final bill items written in simple PHONETIC ENGLISH matching their exact spoken Marathi words (e.g., Sakhar, Maida, Rawa, Shengdane, Chaha, Gul, Shabu, Sarki Pend, Pohe, Godetel, Meeth, Dudh, Tup). DO NOT translate to dictionary words (do NOT output Sugar, Peanuts, Jaggery).\nSpoken Transcript: "${transcript}"\nNormalized Words: "${preNormalized}"`
      : `Language: Marathi (Pure Devanagari script only, NEVER Gujarati or English transliteration).\nSpoken Transcript: "${transcript}"\nNormalized Words: "${preNormalized}"`;

    const chatRes = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        temperature: 0,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: SYSTEM_PROMPT },
          { role: 'user', content: promptHint },
        ],
      }),
    });

    if (!chatRes.ok) {
      const err = await chatRes.text();
      throw new Error(`OpenAI Chat error: ${err}`);
    }

    const chatData = await chatRes.json();
    const content = chatData.choices?.[0]?.message?.content || '{}';
    const parsed = JSON.parse(content);
    const rawItems = Array.isArray(parsed) ? parsed : (parsed.items || []);
    const items = sanitizeItems(rawItems, priceMode, language, outputLang);

    return {
      transcript: convertIndicScriptToDevanagari(parsed.transcript || transcript),
      items,
      provider: 'openai',
      model: 'gpt-4o-mini',
    };
  }
}

/**
 * Gemini speech-to-text only (audio -> transcript text).
 * Used when item extraction is delegated to another provider (e.g. Qwen/Ollama),
 * so the pipeline stays:  speech -> text -> LLM(extract) -> JSON items.
 */
async function geminiTranscribe({ audioBuffer, mimeType = 'audio/mp4', language = 'en-IN' }) {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey) throw new Error('GEMINI_API_KEY is not set in environment variables');
  const base64Audio = audioBuffer.toString('base64');
  // Try models in order: fast official models first, fallback to older
  const transcribeModels = ['gemini-2.5-flash', 'gemini-1.5-flash'];
  for (const tModel of transcribeModels) {
    try {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${tModel}:generateContent?key=${apiKey}`;
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 28000);
      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            contents: [
              {
                parts: [
                  { text: `Transcribe the following audio exactly as spoken. Language hint: ${language}. Output ONLY the transcribed text — no JSON, no formatting, no explanation.` },
                  { inlineData: { mimeType: mimeType || 'audio/mp4', data: base64Audio } },
                ],
              },
            ],
            generationConfig: { temperature: 0 },
          }),
        });
        if (!response.ok) {
          throw new Error(`Gemini transcribe error (${response.status}): ${await response.text()}`);
        }
        const data = await response.json();
        const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
        return String(text).trim();
      } finally {
        clearTimeout(timeout);
      }
    } catch (tErr) {
      if (tModel === transcribeModels[transcribeModels.length - 1]) throw tErr;
    }
  }
  return '';
}

/**
 * Groq Ultra-Fast Provider
 * Uses Groq LPU hardware:
 * - Whisper-large-v3-turbo (~200ms - 400ms speech-to-text)
 * - Llama-3.3-70b-versatile (~150ms - 250ms structured parsing)
 * Total end-to-end latency: < 0.8s
 */
class GroqProvider {
  constructor() {
    this.apiKey = process.env.GROQ_API_KEY;
    this.whisperUrl = 'https://api.groq.com/openai/v1/audio/transcriptions';
    this.chatUrl = 'https://api.groq.com/openai/v1/chat/completions';
  }

  async parseAudio({ audioBuffer, mimeType = 'audio/mp4', language = 'mr-IN', priceMode = 'per_unit', outputLang = null }) {
    if (!this.apiKey) {
      throw new Error('GROQ_API_KEY is not set in environment variables');
    }

    const formData = new FormData();
    const blob = new Blob([audioBuffer], { type: mimeType });
    formData.append('file', blob, 'audio.m4a');
    formData.append('model', 'whisper-large-v3-turbo');
    if (language) formData.append('language', language.split('-')[0]);
    formData.append('prompt', 'मराठी किराणा दुकान बिल: साखर, मैदा, रवा, पोहे, गोडेतेल, सोयाबीन तेल, फॉर्च्यून तेल, सरगम पत्ती चहा, सुपर डस्ट चहा, वाघ बकरी चहा, शेंगदाणे, काजू, बदाम, चारोळी, तूर डाळ, मूग डाळ, हरभरा डाळ, बेसन, आटा, गूळ, मीठ, हळद, जिरे, मोहरी, मसाला, मिरची पावडर, लक्स साबण, गोदरेज साबण, संतूर साबण, सर्फ, मॅगी, पारले जी बिस्कीट, दूध, तूप, ताक. १ किलो, २ किलो, पाव किलो, २५० ग्रॅम, ५०० ग्रॅम, १ लिटर, २ बॉक्स, १ पाकीट, १ पॅकेट. चाळीस, पन्नास, साठ, सत्तर, ऐंशी, नव्वद, शंभर, एकशे चाळीस, एकशे पस्तीस, एकशे नव्वद, दोनशे, अडीचशे, पाचशे, साडेपाचशे, हजार, ५००० रुपये.');

    const whisperRes = await fetch(this.whisperUrl, {
      method: 'POST',
      headers: { Authorization: `Bearer ${this.apiKey}` },
      body: formData,
    });

    if (!whisperRes.ok) {
      const err = await whisperRes.text();
      throw new Error(`Groq Whisper error: ${err}`);
    }

    const whisperData = await whisperRes.json();
    const rawTranscript = whisperData.text || '';
    if (!rawTranscript) {
      return { transcript: '', items: [], provider: 'groq' };
    }

    const transcript = convertIndicScriptToDevanagari(rawTranscript);

    // Fast-Path: Immediately run our local regex parser (takes 2ms)
    const regexItems = parseBillWithRegex(transcript, { priceMode, language, outputLang });
    if (Array.isArray(regexItems) && regexItems.length > 0) {
      console.log(`[Groq Fast-Path HIT] Extracted ${regexItems.length} items in 2ms from: "${transcript}"`);
      return {
        transcript,
        items: sanitizeItems(regexItems, priceMode, language, outputLang),
        provider: 'groq-fastpath',
        model: 'whisper-large-v3-turbo + fastpath',
      };
    }

    // Fallback to Groq Qwen/GPT (~400ms) for complex phrasing
    return this.parseTranscript({ transcript, language, priceMode, outputLang });
  }

  async parseTranscript({ transcript, language = 'mr-IN', priceMode = 'per_unit', outputLang = null }) {
    if (!this.apiKey) {
      throw new Error('GROQ_API_KEY is not set');
    }

    // Fast-Path check (2ms)
    const regexItems = parseBillWithRegex(transcript, { priceMode, language, outputLang });
    if (Array.isArray(regexItems) && regexItems.length > 0) {
      return {
        transcript,
        items: sanitizeItems(regexItems, priceMode, language, outputLang),
        provider: 'groq-fastpath',
        model: 'fastpath',
      };
    }

    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');
    const promptHint = isEnglishOutput
      ? `Language: English letters output. Spoken language is ${language}. Output all item names in simple PHONETIC ENGLISH matching exact Marathi spoken words (e.g. Sakhar, Maida, Rawa, Shengdane, Chaha, Gul, Shabu, Sarki Pend, Pohe, Godetel, Meeth, Dudh, Tup).\nSpoken Transcript: "${transcript}"`
      : `Language: Marathi (Pure Devanagari script only).\nSpoken Transcript: "${transcript}"`;

    const chatModels = ['qwen/qwen3.8-27b', 'openai/gpt-oss-120b'];
    let lastError = null;

    for (const model of chatModels) {
      try {
        const chatRes = await fetch(this.chatUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${this.apiKey}`,
          },
          body: JSON.stringify({
            model,
            temperature: 0,
            response_format: { type: 'json_object' },
            messages: [
              { role: 'system', content: SYSTEM_PROMPT },
              { role: 'user', content: promptHint },
            ],
          }),
        });

        if (!chatRes.ok) {
          const err = await chatRes.text();
          throw new Error(`Groq Chat error: ${err}`);
        }

        const chatData = await chatRes.json();
        const content = chatData.choices?.[0]?.message?.content || '{}';
        const parsed = JSON.parse(content);
        const rawList = Array.isArray(parsed) ? parsed : (parsed.items || []);
        const items = sanitizeItems(rawList, priceMode, language, outputLang);

        return {
          transcript: convertIndicScriptToDevanagari(parsed.transcript || transcript),
          items,
          provider: 'groq',
          model,
        };
      } catch (err) {
        lastError = err;
        console.warn(`[Groq Chat] Model ${model} failed, trying next:`, err.message);
      }
    }

    throw lastError || new Error('Groq models failed');
  }
}

/**
 * Ollama (Qwen) Provider — local/self-hosted LLM for item extraction from text.
 * Pipeline step: text -> JSON { items: [{ name, quantity, unit, price }] }.
 * Endpoint: {OLLAMA_BASE_URL}/api/generate  (format: 'json' forces JSON output).
 * NOTE: Render cannot reach an Ollama on your local PC — run the backend locally
 * (or host Ollama) to use this provider. Gemini works everywhere as the default.
 */
class OllamaQwenProvider {
  constructor() {
    this.baseUrl = (process.env.OLLAMA_BASE_URL || 'http://localhost:11434').replace(/\/+$/, '');
    this.model = process.env.OLLAMA_MODEL || 'qwen2.5:14b';
    this.apiKey = process.env.OLLAMA_API_KEY || ''; // optional, if Ollama sits behind an auth proxy
  }

  async parseTranscript({ transcript, language = 'mr-IN', priceMode = 'per_unit' }) {
    if (!transcript || !transcript.trim()) return { transcript: '', items: [], provider: 'qwen', model: this.model };

    const prompt = `You extract ALL bill items from a voice transcript of an Indian shopkeeper (English, Hindi, Marathi or Hinglish). The transcript contains MANY items, usually 2 to 50, often with no punctuation between them.
Item order may vary: '1 kg sugar 60 rs' or 'sugar 1 kg 60 rs'.
Return ONLY valid JSON, no markdown, no explanation:
{"items":[{"name":string,"quantity":number,"unit":string,"price":number}]}
Rules:
- Return EVERY item mentioned. Never stop after the first item.
- One object per item, in the order spoken.
- price = rate per unit in rupees (PRICE_MODE: "${priceMode}").
- Convert number words (ek, do, teen, one, two, half, aadha, dedh, pachas).
- Normalize names (rawa, rava, sooji -> Rava; cheeni -> Sugar).
- If quantity is missing, use 1. If price is missing, use 0.

Preferred language hint: ${language}
Transcript: "${transcript}"`;

    const headers = { 'Content-Type': 'application/json' };
    if (this.apiKey) headers['Authorization'] = `Bearer ${this.apiKey}`;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(`${this.baseUrl}/api/generate`, {
        method: 'POST',
        headers,
        signal: controller.signal,
        body: JSON.stringify({
          model: this.model,
          prompt,
          stream: false,
          format: 'json',
          options: { temperature: 0 },
        }),
      });
      if (!response.ok) {
        throw new Error(`Ollama error (${response.status}): ${await response.text()}`);
      }
      const data = await response.json();
      const textResponse = String(data?.response || '').trim();
      if (!textResponse) throw new Error('Empty response from Ollama');
      const cleanJson = textResponse.replace(/```(?:json)?/gi, '').replace(/```/g, '').trim();
      const parsed = JSON.parse(cleanJson);
      const rawItems = Array.isArray(parsed) ? parsed : (parsed.items || []);
      const items = sanitizeItems(rawItems, priceMode, language);
      return { transcript, items, provider: 'qwen', model: this.model };
    } finally {
      clearTimeout(timeout);
    }
  }
}

/**
 * Service Factory
 * LLM_PROVIDER: 'gemini' (default, cloud) | 'qwen'/'ollama' (local) | 'openai'
 */
function getLLMProvider(providerName = process.env.LLM_PROVIDER) {
  const p = (providerName || (process.env.GROQ_API_KEY ? 'groq' : (process.env.OPENAI_API_KEY ? 'openai' : 'gemini'))).toLowerCase();
  if (p === 'groq') {
    return new GroqProvider();
  }
  if (p === 'openai') {
    return new OpenAIProvider();
  }
  if (p === 'qwen' || p === 'ollama') {
    return new OllamaQwenProvider();
  }
  if (process.env.GROQ_API_KEY) return new GroqProvider();
  return process.env.OPENAI_API_KEY ? new OpenAIProvider() : new GeminiProvider();
}

module.exports = {
  getLLMProvider,
  GroqProvider,
  GeminiProvider,
  OpenAIProvider,
  OllamaQwenProvider,
  geminiTranscribe,
  sanitizeItems,
  canonicalizeUnit,
  normalizeItemName,
};

