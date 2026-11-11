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
- Single numbers: एक=1, दोन=2, तीन=3, चार=4, पाच=5, सहा=6, सात=7, आठ=8, नऊ=9, दहा=10, अकरा=11, बारा=12, तेरा=13, चौदा=14, पंधरा=15, सोळा=16, सतरा=17, अठरा=18, एकोणीस=19, वीस=20, पंचवीस=25, तीस=30, चाळीस=40, पन्नास=50, साठ=60, सत्तर=70, ऐंशी=80, नव्वद=90.
- Hundreds: शंभर/एकशे=100, दोनशे=200, तीनशे=300, चारशे=400, पाचशे=500, सहाशे=600, सातशे=700, आठशे=800, नऊशे=900, एक हजार=1000.
- Colloquial half-hundreds: साडेपाचशे=550, साडेचारशे=450, साडेतीनशे=350, अडीचशे=250, दीडशे=150.
- Compound hundreds & prices (MUST align exactly with spoken price!):
  "एकशे चाळीस" (ekshe chalis) = 140
  "एकशे दहा" (ekshe daha) = 110
  "एकशे आठ" (ekshe aath) = 108
  "पाचशे अडुसष्ट" / "पाचशे अडसठ" = 568
  "सातशे एकोणनव्वद" = 789
  "पाचशे पन्नास" / "साडेपाचशे" = 550
  "पाचशे" = 500
  "नऊशे" = 900
  "साठ" = 60, "पन्नास" = 50, "नव्वद" = 90, "ऐंशी" = 80, "चाळीस" = 40, "दहा" = 10, "पाच" = 5.

4. EXACT NUMBER & PRICING ALIGNMENT:
- Extract the exact numbers spoken.
- "दोन किलो साखर एकशे चाळीस रुपये" -> name: "साखर", quantity: 2, unit: "kg", price: 140
- "एक किलो साखर पाचशे अडुसष्ट रुपये" -> name: "साखर", quantity: 1, unit: "kg", price: 568
- "दोन किलो साखर सातशे एकोणनव्वद रुपये" -> name: "साखर", quantity: 2, unit: "kg", price: 789
- "दोन किलो साखर पाचशे पन्नास रुपये" -> name: "साखर", quantity: 2, unit: "kg", price: 550
- "एकशे दहा रुपयांचे तेल" -> name: "तेल", quantity: 1, unit: "litre", price: 110
- "एकशे आठ रुपयांची साखर" -> name: "साखर", quantity: 1, unit: "packet", price: 108
- "अर्धा किलो पोहे तीस रुपये" -> name: "पोहे", quantity: 0.5, unit: "kg", price: 30
- "पाव किलो चहा पन्नास रुपये" -> name: "चहा", quantity: 0.25, unit: "kg", price: 50
- "दीड लिटर तेल दोनशे रुपये" -> name: "तेल", quantity: 1.5, unit: "litre", price: 200
- If quantity is missing use 1. If price is missing use 0.

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
    const name = normalizeItemName(String(item.name || item.item || '').trim(), language, outputLang);
    if (!name) continue;

    let quantity = parseFloat(item.quantity || item.qty);
    if (isNaN(quantity) || quantity <= 0) {
      quantity = 1;
    }

    let price = parseFloat(item.price || item.rate || 0);
    if (isNaN(price) || price < 0) {
      price = 0;
    }

    // Handle priceMode: if line_total was spoken and qty > 0, convert to per-unit rate
    if (priceMode === 'line_total' && quantity > 0) {
      price = parseFloat((price / quantity).toFixed(2));
    }

    const unit = canonicalizeUnit(item.unit);
    let amount = Math.round(quantity * price * 100) / 100;
    if ((unit === 'g' || unit === 'gm') && quantity >= 50 && price > 20) {
      amount = Math.round(((quantity * price) / 1000) * 100) / 100;
    } else if (unit === 'ml' && quantity >= 50 && price > 30) {
      amount = Math.round(((quantity * price) / 1000) * 100) / 100;
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
    const models = ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash-8b'];

    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');
    const langPrompt = isEnglishOutput
      ? `${SYSTEM_PROMPT}\nNOTE: User spoke in ${language}, BUT wants the final bill items in clean ENGLISH (e.g., Sugar, Tea, Cooking Oil, Toor Dal, Poha, Peanuts, Milk). Translate Marathi/Hindi spoken items into standard English grocery names.\nAudio input follows.`
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
${isEnglishOutput ? 'NOTE: Output all item names in clean ENGLISH (e.g. Sugar, Tea, Cooking Oil, Toor Dal, Poha, Peanuts, Milk). Translate Marathi/Hindi item names to English grocery names.' : ''}

Extract items from this counter billing transcript:
Spoken Transcript: "${transcript}"
Normalized Words: "${preNormalized}"
Language: ${language}
Price Mode: "${priceMode}"`;

    const models = ['gemini-1.5-flash', 'gemini-2.0-flash', 'gemini-1.5-flash-8b'];
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
    // Guide Whisper to transcribe in pure Marathi Devanagari (avoid Gujarati hallucination)
    formData.append('prompt', 'मराठी किराणा बिल: चहा, साखर, तूर डाळ, पोहे, तेल, गहू, तांदूळ, गव्हाचे पीठ, साबण, कांदे, बटाटे, दूध, बिस्कीट, रुपये, किलो, ग्रॅम, लिटर, १००, ५००, ५२०, १४०, ६०, ५०, ९०, ८०, ४०, १०, ५, ९००, ५६८, ७८९, ५५०, ११०, १०८');

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

    // Step 2: Extract items using gpt-4o-mini
    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');
    const promptHint = isEnglishOutput
      ? `Language: English items output. Spoken language is ${language}. Output all item names in clean standard ENGLISH (e.g. Sugar, Tea, Cooking Oil, Toor Dal, Poha, Peanuts, Milk). Translate Marathi/Hindi spoken items into standard English grocery names.\nSpoken Transcript: "${transcript}"\nNormalized Words: "${preNormalized}"`
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

    const preNormalized = normalizeMarathiTranscript(transcript);
    const isEnglishOutput = String(outputLang || '').toLowerCase().startsWith('en');

    const promptHint = isEnglishOutput
      ? `NOTE: User spoke in ${language}, BUT wants the final bill items in clean ENGLISH (e.g., Sugar, Tea, Cooking Oil, Toor Dal, Poha, Peanuts, Milk). Translate Marathi/Hindi spoken items into standard English grocery names.\nSpoken Transcript: "${transcript}"\nNormalized Words: "${preNormalized}"`
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
  const transcribeModels = ['gemini-1.5-flash', 'gemini-2.0-flash'];
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
  const p = (providerName || (process.env.OPENAI_API_KEY ? 'openai' : 'gemini')).toLowerCase();
  if (p === 'openai') {
    return new OpenAIProvider();
  }
  if (p === 'qwen' || p === 'ollama') {
    return new OllamaQwenProvider();
  }
  return process.env.OPENAI_API_KEY ? new OpenAIProvider() : new GeminiProvider();
}

module.exports = {
  getLLMProvider,
  GeminiProvider,
  OpenAIProvider,
  OllamaQwenProvider,
  geminiTranscribe,
  sanitizeItems,
  canonicalizeUnit,
  normalizeItemName,
};

