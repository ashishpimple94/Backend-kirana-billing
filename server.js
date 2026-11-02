require('dotenv').config();
const express = require('express');
const cors = require('cors');
const mongoose = require('mongoose');
const rateLimit = require('express-rate-limit');
const connectDB = require('./config/db');
const voiceToBillRoute = require('./routes/voiceToBill');
const billsRoute = require('./routes/bills');

const app = express();
const PORT = process.env.PORT || 5000;

// Connect to MongoDB
connectDB();

// Enable CORS for mobile app & web client
app.use(cors());

// Parse JSON bodies
app.use(express.json());

// Rate Limiting: 60 requests per minute
const limiter = rateLimit({
  windowMs: 60 * 1000,
  max: 60,
  message: {
    error: 'खूप जास्त विनंत्या पाठवल्या आहेत. कृपया एका मिनिटानंतर पुन्हा प्रयत्न करा. (Rate limit reached)',
  },
  standardHeaders: true,
  legacyHeaders: false,
});
app.use('/api/', limiter);

// Health check with MongoDB status
app.get('/api/health', (req, res) => {
  const mongoStates = ['disconnected', 'connected', 'connecting', 'disconnecting'];
  const stateCode = mongoose.connection.readyState;
  res.json({
    status: 'ok',
    service: 'kirana-voice-billing-backend',
    database: {
      status: mongoStates[stateCode] || 'unknown',
      connected: stateCode === 1,
      name: mongoose.connection.name || 'kirana_billing',
    },
    provider: process.env.LLM_PROVIDER || 'gemini',
    priceMode: process.env.PRICE_MODE || 'per_unit',
    timestamp: new Date().toISOString(),
  });
});

// API Routes
app.use('/api', voiceToBillRoute);
app.use('/api/bills', billsRoute);

// Global Error Handler
app.use((err, req, res, next) => {
  console.error('[Server Error]', err);
  if (err.code === 'LIMIT_FILE_SIZE') {
    return res.status(413).json({
      error: 'ऑडिओ फाईल खूप मोठी आहे. (Max file size 10MB)',
    });
  }
  res.status(500).json({
    error: err.message || 'Internal Server Error',
  });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`🚀 Kirana Voice Billing Server running on http://0.0.0.0:${PORT}`);
  console.log(`📡 Voice-to-Bill API: POST http://localhost:${PORT}/api/voice-to-bill`);
  console.log(`📦 MongoDB Bills API: http://localhost:${PORT}/api/bills`);
});
