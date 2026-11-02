const express = require('express');
const multer = require('multer');
const { getLLMProvider } = require('../services/llmService');

const router = express.Router();

// Configure Multer for in-memory storage, 10MB limit
const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: 10 * 1024 * 1024, // 10 MB
  },
  fileFilter: (req, file, cb) => {
    // Allow audio files (m4a, aac, mp4, wav, webm, 3gp, ogg)
    if (
      file.mimetype.startsWith('audio/') ||
      file.mimetype === 'video/mp4' ||
      file.originalname.match(/\.(m4a|aac|mp4|wav|webm|3gp|ogg)$/i)
    ) {
      cb(null, true);
    } else {
      cb(new Error('Invalid file format. Only audio recordings (m4a, aac, wav, mp4) are allowed.'));
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

  // 1 Retry on transient failure
  let attempts = 0;
  const maxAttempts = 2;
  let lastErr = null;

  while (attempts < maxAttempts) {
    attempts++;
    try {
      const provider = getLLMProvider();
      const result = await provider.parseAudio({
        audioBuffer: file.buffer,
        mimeType: file.mimetype || 'audio/mp4',
        language,
        priceMode,
      });

      console.log(`[POST /api/voice-to-bill] Success! Detected ${result.items.length} items. Transcript: "${result.transcript}"`);

      // T6: Silence or noise only -> show "No items detected", no crash
      return res.json({
        success: true,
        transcript: result.transcript || '',
        items: result.items || [],
        priceMode,
        provider: result.provider,
      });
    } catch (err) {
      lastErr = err;
      console.warn(`[POST /api/voice-to-bill] Attempt ${attempts} failed:`, err.message);
      if (attempts < maxAttempts) {
        // Short pause before retry
        await new Promise((resolve) => setTimeout(resolve, 800));
      }
    }
  }

  console.error('[POST /api/voice-to-bill] All attempts failed:', lastErr);
  return res.status(500).json({
    error: 'आवाज प्रक्रिया करताना त्रुटी आली. कृपया पुन्हा प्रयत्न करा (Retry).',
    details: lastErr?.message || 'Failed to process voice audio with AI',
  });
});

module.exports = router;

