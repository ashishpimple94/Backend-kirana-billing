const express = require('express');
const multer = require('multer');
const { getLLMProvider, geminiTranscribe, GeminiProvider, OpenAIProvider } = require('../services/llmService');
const { parseBillWithRegex } = require('../services/regexParser');
const redis = require('../config/redis');

const router = express.Router();

// ── Multer: kept for backwards-compat if any client still sends multipart ──
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 10 * 1024 * 1024 },
  fileFilter: (req, file, cb) => {
    const mime = (file.mimetype || '').toLowerCase();
    const name = (file.originalname || '').toLowerCase();
    const mimeOk = mime.startsWith('audio/') || mime.startsWith('video/') ||
      mime === 'application/octet-stream' || mime === 'application/x-m4a';
    const extOk = /\.(m4a|aac|mp4|wav|webm|3gp|ogg|caf|flac|opus|mp3)$/i.test(name);
    if (mimeOk || extOk) cb(null, true);
    else cb(new Error(`Unsupported audio format: mime=${file.mimetype}, name=${file.originalname}`));
  },
});

/**
 * Middleware: accept BOTH multipart/form-data AND raw binary audio bodies.
 * React Native fetch with { uri, name, type } FormData is unreliable across
 * Expo versions — raw binary (Content-Type: audio/mp4) is always reliable.
 */
function audioUploadMiddleware(req, res, next) {
  // Support Base64 in JSON body (fastest & most reliable across all React Native/Expo versions)
  if (req.body && req.body.audioBase64) {
    const buffer = Buffer.from(req.body.audioBase64, 'base64');
    req.file = {
      buffer,
      size: buffer.length,
      mimetype: req.body.mimeType || 'audio/mp4',
      originalname: 'voice_order.m4a',
    };
    next();
    return;
  }

  const ct = (req.headers['content-type'] || '').toLowerCase();

  if (ct.startsWith('multipart/form-data')) {
    // Legacy path: multipart FormData
    upload.single('audio')(req, res, next);
    return;
  }

  if (ct.startsWith('audio/') || ct.startsWith('video/') ||
      ct === 'application/octet-stream' || ct === 'application/x-m4a') {
    // New path: raw binary body — read into buffer and fake req.file
    const chunks = [];
    req.on('data', (chunk) => chunks.push(chunk));
    req.on('end', () => {
      const buffer = Buffer.concat(chunks);
      // language and priceMode come from query params when using raw binary
      req.file = {
        buffer,
        size: buffer.length,
        mimetype: ct,
        originalname: `voice_order.${ct.split('/')[1]?.split(';')[0] || 'm4a'}`,
      };
      next();
    });
    req.on('error', next);
    return;
  }

  // Unknown content-type — let multer try (will likely produce a friendly error)
  upload.single('audio')(req, res, next);
}

/**
 * POST /api/voice-to-bill
 * Receives multipart/form-data:
 *  - audio: audio file buffer
 *  - language: 'mr-IN' | 'hi-IN' | 'en-IN' (optional)
 *  - priceMode: 'per_unit' | 'line_total' (optional)
 */
router.post('/voice-to-bill', audioUploadMiddleware, async (req, res) => {
  const file = req.file;
  if (!file || !file.buffer || file.buffer.length === 0) {
    return res.status(400).json({
      error: 'Audio file is required. Please record audio before uploading.',
    });
  }

  const language = req.body?.language || req.query?.language || 'mr-IN';
  const outputLang = req.body?.outputLang || req.query?.outputLang || req.body?.billLanguage || req.query?.billLanguage || null;
  const priceMode = req.body?.priceMode || req.query?.priceMode || process.env.PRICE_MODE || 'per_unit';

  console.log(`[POST /api/voice-to-bill] Received audio: ${file.originalname || 'recording.m4a'} (${file.size} bytes), mime: ${file.mimetype}, lang: ${language}, outputLang: ${outputLang || 'default'}`);

  // Provider cascade: OpenAI (lightning fast ~2s) -> Gemini (fallback)
  const audioArgs = { audioBuffer: file.buffer, mimeType: file.mimetype || 'audio/mp4', language, priceMode, outputLang };

  const providers = [
    { name: 'openai', getInstance: () => process.env.OPENAI_API_KEY ? new OpenAIProvider() : null },
    { name: 'gemini', getInstance: () => new GeminiProvider() },
  ];

  // If LLM_PROVIDER is explicitly set, prioritize it; otherwise default to OpenAI first
  const explicitProvider = process.env.LLM_PROVIDER;
  let providerList = providers;
  if (explicitProvider === 'qwen' || explicitProvider === 'ollama') {
    providerList = [{ name: explicitProvider, getInstance: () => getLLMProvider() }];
  } else if (explicitProvider === 'gemini' && !process.env.OPENAI_API_KEY) {
    providerList = [{ name: 'gemini', getInstance: () => new GeminiProvider() }];
  } else {
    providerList = providers;
  }

  let lastErr = null;

  for (const { name, getInstance } of providerList) {
    const provider = getInstance();
    if (!provider) continue;

    for (let attempt = 1; attempt <= 2; attempt++) {
      try {
        let result;
        if (typeof provider.parseAudio === 'function') {
          result = await provider.parseAudio(audioArgs);
        } else {
          const transcript = await geminiTranscribe(audioArgs);
          result = await provider.parseTranscript({ transcript, language, priceMode, outputLang });
        }
        console.log(`[POST /api/voice-to-bill] ${name} attempt ${attempt}: ${result.items.length} items. Transcript: "${result.transcript}"`);
        return res.json({
          success: true,
          transcript: result.transcript || '',
          items: result.items || [],
          priceMode,
          provider: result.provider || name,
        });
      } catch (err) {
        lastErr = err;
        console.warn(`[POST /api/voice-to-bill] ${name} attempt ${attempt} failed:`, err.message);
        if (attempt < 2) await new Promise((r) => setTimeout(r, 800));
      }
    }
    console.warn(`[POST /api/voice-to-bill] ${name} exhausted — trying next provider`);
  }

  console.error('[POST /api/voice-to-bill] All attempts failed:', lastErr);
  return res.status(500).json({
    error: 'आवाज प्रक्रिया करताना त्रुटी आली. कृपया पुन्हा प्रयत्न करा (Retry).',
    details: lastErr?.message || 'Failed to process voice audio with AI',
  });
});

/**
 * POST /api/parse-bill
 * Receives JSON:
 *  - transcript: string (full recognized speech text)
 *  - language: 'mr-IN' | 'hi-IN' | 'en-IN' (optional)
 *  - priceMode: 'per_unit' | 'line_total' (optional)
 */
router.post('/parse-bill', async (req, res) => {
  const { transcript, language = 'mr-IN', priceMode = process.env.PRICE_MODE || 'per_unit', outputLang = null, billLanguage = null } = req.body || {};
  const targetOutputLang = outputLang || billLanguage || null;

  if (!transcript || typeof transcript !== 'string' || !transcript.trim()) {
    return res.status(400).json({
      error: 'Transcript text is required in request body.',
    });
  }

  const cleanText = transcript.trim();
  console.log(`[POST /api/parse-bill] Parsing transcript (${cleanText.length} chars): "${cleanText}", outputLang: ${targetOutputLang || 'default'}`);

  // Fast-path: Check Redis cache for identical spoken order transcript
  const cacheKey = `parse:${language}:${targetOutputLang || 'def'}:${priceMode}:${Buffer.from(cleanText.toLowerCase()).toString('base64').slice(0, 60)}`;
  const cachedResult = await redis.get(cacheKey);
  if (cachedResult && Array.isArray(cachedResult.items) && cachedResult.items.length > 0) {
    console.log(`[POST /api/parse-bill] Redis Cache HIT for "${cleanText}" (${cachedResult.items.length} items)`);
    res.set('X-Cache', 'HIT');
    return res.json(cachedResult);
  }

  // Provider cascade: OpenAI (lightning fast ~1-2s) -> Gemini (fallback) -> Regex (offline)
  const textProviders = [
    { name: 'openai', getInstance: () => process.env.OPENAI_API_KEY ? new OpenAIProvider() : null },
    { name: 'gemini', getInstance: () => new GeminiProvider() },
  ];
  const explicitTextProvider = process.env.LLM_PROVIDER;
  let textProviderList = textProviders;
  if (explicitTextProvider === 'qwen' || explicitTextProvider === 'ollama') {
    textProviderList = [{ name: explicitTextProvider, getInstance: () => getLLMProvider() }];
  } else if (explicitTextProvider === 'gemini' && !process.env.OPENAI_API_KEY) {
    textProviderList = [{ name: 'gemini', getInstance: () => new GeminiProvider() }];
  } else {
    textProviderList = textProviders;
  }

  for (const { name, getInstance } of textProviderList) {
    const provider = getInstance();
    if (!provider || typeof provider.parseTranscript !== 'function') continue;
    try {
      const result = await provider.parseTranscript({ transcript: cleanText, language, priceMode, outputLang: targetOutputLang });
      console.log(`[POST /api/parse-bill] ${name} extracted ${result.items?.length || 0} items.`);
      const responseData = {
        success: true,
        transcript: cleanText,
        items: result.items || [],
        priceMode,
        provider: result.provider || name,
      };
      if (Array.isArray(result.items) && result.items.length > 0) {
        redis.set(cacheKey, responseData, 86400).catch(() => {});
      }
      res.set('X-Cache', 'MISS');
      return res.json(responseData);
    } catch (err) {
      console.warn(`[POST /api/parse-bill] ${name} failed, trying next:`, err.message);
    }
  }

  // Final fallback: Global Regex Parser (0ms, offline)
  const regexItems = parseBillWithRegex(cleanText, { priceMode, language, outputLang: targetOutputLang });
  console.log(`[POST /api/parse-bill] Regex fallback extracted ${regexItems.length} items.`);
  return res.json({
    success: true,
    transcript: cleanText,
    items: regexItems,
    priceMode,
    provider: 'regex-fallback',
  });
});

module.exports = router;

