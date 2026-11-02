/**
 * Unified LLM Audio Parser Service
 * Supports Gemini (gemini-2.5-flash inline audio) as default,
 * and OpenAI (Whisper / gpt-4o-mini-transcribe + gpt-4o-mini) as alternative.
 */

const SYSTEM_PROMPT = `You are a billing assistant for an Indian shop. Listen to this audio (English, Hindi, Marathi or Hinglish). The shopkeeper speaks MANY items, usually 2 to 50, with or without pauses between them.
Extract EVERY item mentioned. Never stop after the first item.
Item order may vary: '1 kg sugar 60 rs' or 'sugar 1 kg 60 rs'.
Convert number words (ek, do, teen, one, two, half, aadha, dedh, pachas) to numbers. Normalize names (rawa, rava, sooji -> Rava; cheeni -> Sugar). Units: kg, g, litre, ml, piece, packet, dozen.
If quantity is missing use 1. If price is missing use 0.
price = rate per unit in rupees.
Return ONLY JSON:
{"transcript": string,
 "items": [{"name": string, "quantity": number,
             "unit": string, "price": number}]}
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
  if (['kg', 'kgs', 'kilo', 'kilos', 'kilogram', 'kilograms', 'किलो'].includes(u)) return 'kg';
  if (['g', 'gm', 'gms', 'gram', 'grams', 'ग्रॅम', 'ग्राम'].includes(u)) return 'g';
  if (['l', 'ltr', 'ltrs', 'litre', 'litres', 'liter', 'liters', 'लिटर', 'लीटर'].includes(u)) return 'litre';
  if (['ml', 'mls', 'millilitre', 'मिली'].includes(u)) return 'ml';
  if (['packet', 'packets', 'pkt', 'pkts', 'puda', 'pude', 'पुडा', 'पाकीट'].includes(u)) return 'packet';
  if (['box', 'boxes', 'carton', 'cartons', 'बॉक्स', 'खोके', 'खोका'].includes(u)) return 'box';
  if (['dozen', 'dozens', 'डझन', 'दर्जन'].includes(u)) return 'dozen';
  if (['piece', 'pieces', 'pcs', 'pc', 'item', 'items', 'nag', 'पीस', 'नग'].includes(u)) return 'piece';
  return u;
}

/**
 * Normalizes item names (e.g. Cheeni -> Sugar, Sooji -> Rava)
 */
function normalizeItemName(rawName) {
  if (!rawName) return '';
  const clean = rawName.trim().toLowerCase();
  const map = {
    cheeni: 'Sugar', sakhar: 'Sugar', sugar: 'Sugar', 'साखर': 'Sugar', 'चीनी': 'Sugar',
    rawa: 'Rava', rava: 'Rava', sooji: 'Rava', suji: 'Rava', 'रवा': 'Rava', 'सुजी': 'Rava',
    maida: 'Maida', 'मैदा': 'Maida',
    tel: 'Oil', oil: 'Oil', 'तेल': 'Oil',
    tandul: 'Rice', chawal: 'Rice', rice: 'Rice', 'तांदूळ': 'Rice', 'चावल': 'Rice',
    atta: 'Atta', pith: 'Atta', 'आटा': 'Atta',
    chaha: 'Tea', chai: 'Tea', tea: 'Tea', 'चहा': 'Tea', 'चाय': 'Tea',
    doodh: 'Milk', dudh: 'Milk', milk: 'Milk', 'दूध': 'Milk',
    saban: 'Soap', soap: 'Soap', 'साबण': 'Soap',
    salt: 'Salt', meeth: 'Salt', 'मीठ': 'Salt', 'नमक': 'Salt',
    maggi: 'Maggi', 'मॅगी': 'Maggi',
    parle: 'Parle', parle_g: 'Parle-G',
  };
  if (map[clean]) return map[clean];
  // Title Case
  return clean.replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Validates parsed items:
 * name not empty, quantity > 0, price >= 0
 */
function sanitizeItems(rawItems, priceMode = 'per_unit') {
  if (!Array.isArray(rawItems)) return [];
  const valid = [];

  for (const item of rawItems) {
    if (!item) continue;
    const name = normalizeItemName(String(item.name || item.item || '').trim());
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
    const amount = Math.round(quantity * price * 100) / 100;

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

  async parseAudio({ audioBuffer, mimeType = 'audio/mp4', language = 'en-IN', priceMode = 'per_unit' }) {
    if (!this.apiKey) {
      throw new Error('GEMINI_API_KEY is not set in environment variables');
    }

    const base64Audio = audioBuffer.toString('base64');
    const models = ['gemini-2.5-flash', 'gemini-flash-latest', 'gemini-flash-lite-latest'];

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
                  { text: `${SYSTEM_PROMPT}\nUser preferred language hint: ${language}. Audio input follows.` },
                  {
                    inlineData: {
                      mimeType: mimeType || 'audio/mp4',
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

        const transcript = String(parsed.transcript || '').trim();
        const items = sanitizeItems(parsed.items, priceMode);

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
}

/**
 * OpenAI Provider implementation (Alternative swappable provider):
 * Uses Whisper / gpt-4o-mini-transcribe + gpt-4o-mini.
 */
class OpenAIProvider {
  constructor(apiKey) {
    this.apiKey = apiKey || process.env.OPENAI_API_KEY;
  }

  async parseAudio({ audioBuffer, mimeType = 'audio/mp4', language = 'en', priceMode = 'per_unit' }) {
    if (!this.apiKey) {
      throw new Error('OPENAI_API_KEY is not set in environment variables');
    }

    // Step 1: Transcribe using Whisper
    const formData = new FormData();
    const blob = new Blob([audioBuffer], { type: mimeType });
    formData.append('file', blob, 'audio.m4a');
    formData.append('model', 'whisper-1');
    if (language) formData.append('language', language.split('-')[0]);

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
    const transcript = whisperData.text || '';
    if (!transcript) {
      return { transcript: '', items: [], provider: 'openai' };
    }

    // Step 2: Extract items using gpt-4o-mini
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
          { role: 'user', content: `Transcript: "${transcript}"` },
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
    const items = sanitizeItems(parsed.items, priceMode);

    return {
      transcript: parsed.transcript || transcript,
      items,
      provider: 'openai',
    };
  }
}

/**
 * Service Factory
 */
function getLLMProvider(providerName = process.env.LLM_PROVIDER) {
  const p = (providerName || 'gemini').toLowerCase();
  if (p === 'openai') {
    return new OpenAIProvider();
  }
  return new GeminiProvider();
}

module.exports = {
  getLLMProvider,
  GeminiProvider,
  OpenAIProvider,
  sanitizeItems,
  canonicalizeUnit,
  normalizeItemName,
};

