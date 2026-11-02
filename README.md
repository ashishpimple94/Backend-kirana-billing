# Kirana Voice-to-Bill Backend API

Scalable Node.js & Express backend for Kirana POS Voice Billing, powered by Google Gemini 2.5 Flash Audio LLM and MongoDB Atlas.

## Features
- **Continuous Voice-to-Bill:** Extracts grocery items, quantities, units, and rates from continuous multilingual audio transcripts (English, Hindi, Marathi, Hinglish).
- **Gemini 2.5 Flash Audio:** Processes recorded audio as inline data with strict JSON schema validation.
- **MongoDB Atlas Integration:** Stores bills with items, subtotal, GST, grand total, and payment details.
- **Rate Limiting & Security:** 60 requests/minute rate limiter, 10MB file limit, and CORS enabled.

## Setup Instructions

1. Clone the repository:
   ```bash
   git clone https://github.com/ashishpimple94/Backend-kirana-billing.git
   cd Backend-kirana-billing
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Create `.env` file from `.env.example`:
   ```bash
   cp .env.example .env
   ```
   Fill in your `GEMINI_API_KEY` and `MONGODB_URI`.

4. Start the server:
   ```bash
   npm start
   ```
   Server runs on `http://0.0.0.0:5000`.

## API Endpoints
- `GET /api/health` - Server & MongoDB status check
- `POST /api/voice-to-bill` - Multipart audio upload endpoint
- `POST /api/bills` - Save bill to MongoDB
- `GET /api/bills` - Fetch bill history from MongoDB
- `GET /api/bills/:id` - Fetch single bill
- `DELETE /api/bills/:id` - Delete bill
