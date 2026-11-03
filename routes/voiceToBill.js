const express = require('express');
const multer = require('multer');
const { getLLMProvider, geminiTranscribe, GeminiProvider, OpenAIProvider } = require('../services/llmService');
const { parseBillWithRegex } = require('../services/regexParser');

const router = express.Router();

// Configure Multer for in-memory storage, 10MB limit
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024, // 10 MB
  },
  fileFilter: (req, file, cb) => {
    const mime = (file.mimetype || '').toLowerCase();
    const name = (file.originalname || '').toLowerCase();

    // Accept any audio or video MIME (covers audio/mp4, audio/m4a, audio/aac,
    // audio/wav, audio/webm, audio/x-m4a, video/mp4, etc.)
    const mimeOk =
      mime.startsWith('audio/') ||
      mime.startsWith('video/') ||
      // React Native FormData sometimes sends application/octet-stream
      // when it can't determine the MIME type — allow it and trust the extension.
      mime === 'application/octet-stream' ||
      mime === 'application/x-m4a';

    const extOk = /\.(m4a|aac|mp4|wav|webm|3gp|ogg|caf|flac|opus|mp3)$/i.test(name);

    if (mimeOk || extOk) {
      cb(null, true);
    } else {
      cb(new Error(`Unsupported audio format: mime=${file.mimetype}, name=${file.originalname}. Use m4a/aac/wav/mp4.`));
    }
  },
});

/**
 * POST /api/voice-to-bill
 * Receives multipart/form-data:
 *  - audio: audio file buffer
 *  - language: 'mr-IN' | 'hi-IN' | 'en-IN' (optional)
 *  - priceMode: 'per_unit' | 'line_total' (optional)
 */
router.post('/voice-to-bill', upload.single('audio'), async (req, res) => {
  const file = req.file;
  if (!file || !file.buffer || file.buffer.length === 0) {
    return res.status(400).json({
      error: 'Audio file is required. Please record audio before uploading.',
    });
  }

  const language = req.body.language || 'mr-IN';
  const priceMode = req.body.priceMode || process.env.PRICE_MODE || 'per_unit';

  console.log(`[POST /api/voice-to-bill] Received audio: ${file.originalname || 'recording.m4a'} (${file.size} bytes), mime: ${file.mimetype}, lang: ${language}`);

  // Provider cascade: Gemini (primary) → OpenAI (automatic fallback)
  // Each provider gets 2 attempts; if both fail we return an error.
  const audioArgs = { audioBuffer: file.buffer, mimeType: file.mimetype || 'audio/mp4', language, priceMode };

  const providers = [
    { name: 'gemini', getInstance: () => new GeminiProvider() },
    { name: 'openai', getInstance: () => process.env.OPENAI_API_KEY ? new OpenAIProvider() : null },
  ];

  // If LLM_PROVIDER is explicitly set to openai or qwen, respect that (skip auto-cascade)
  const explicitProvider = process.env.LLM_PROVIDER;
  const providerList = (explicitProvider && explicitProvider !== 'gemini')
    ? [{ name: explicitProvider, getInstance: () => getLLMProvider() }]
    : providers;

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
          result = await provider.parseTranscript({ transcript, language, priceMode });
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
  const { transcript, language = 'mr-IN', priceMode = process.env.PRICE_MODE || 'per_unit' } = req.body || {};

  if (!transcript || typeof transcript !== 'string' || !transcript.trim()) {
    return res.status(400).json({
      error: 'Transcript text is required in request body.',
    });
  }

  const cleanText = transcript.trim();
  console.log(`[POST /api/parse-bill] Parsing transcript (${cleanText.length} chars): "${cleanText}"`);

  // Provider cascade: Gemini (primary) → OpenAI (automatic fallback) → Regex (offline)
  const textProviders = [
    { name: 'gemini', getInstance: () => new GeminiProvider() },
    { name: 'openai', getInstance: () => process.env.OPENAI_API_KEY ? new OpenAIProvider() : null },
  ];
  const explicitTextProvider = process.env.LLM_PROVIDER;
  const textProviderList = (explicitTextProvider && explicitTextProvider !== 'gemini')
    ? [{ name: explicitTextProvider, getInstance: () => getLLMProvider() }]
    : textProviders;

  for (const { name, getInstance } of textProviderList) {
    const provider = getInstance();
    if (!provider || typeof provider.parseTranscript !== 'function') continue;
    try {
      const result = await provider.parseTranscript({ transcript: cleanText, language, priceMode });
      console.log(`[POST /api/parse-bill] ${name} extracted ${result.items?.length || 0} items.`);
      return res.json({
        success: true,
        transcript: cleanText,
        items: result.items || [],
        priceMode,
        provider: result.provider || name,
      });
    } catch (err) {
      console.warn(`[POST /api/parse-bill] ${name} failed, trying next:`, err.message);
    }
  }

  // Final fallback: Global Regex Parser (0ms, offline)
  const regexItems = parseBillWithRegex(cleanText, { priceMode });
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

