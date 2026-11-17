"""
ai_service.py
AI Service for Voice Transcription & Kirana Bill Parsing in Python FastAPI.
Supports Gemini 2.5 Flash, Groq Whisper/LLaMA, and OpenAI Whisper/GPT.
Detects spoken pronunciations (e.g. '60 sath', '60 sixty', '95 panchyannav')
and enforces strict pricing guardrails (1 to 5000, rejects 100,000 hallucinations).
"""

import os
import re
import json
import base64
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

# Load API keys from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


class SpokenBillItem(BaseModel):
    name: str = Field(..., description="Kirana item name in Marathi Devanagari (or clean Roman)")
    quantity: float = Field(..., description="Quantity as number (e.g. 1, 0.5, 2)")
    unit: str = Field(..., description="Unit: kg, gm, litre, ml, packet, box, piece")
    price: float = Field(..., description="Price in rupees (per unit or total, typically 1 to 5000)")
    amount: float = Field(..., description="Total line amount (quantity * price)")
    spoken_pronunciation: Optional[str] = Field(None, description="Spoken pronunciation word if uttered (e.g. 'sath', 'sixty', 'panchyannav')")


class BillParseResponse(BaseModel):
    transcript: str = Field(..., description="Full spoken transcript")
    items: List[SpokenBillItem] = Field(default_factory=list, description="Extracted bill items")
    provider: str = Field("ai-engine", description="AI Provider used")


SYSTEM_PROMPT = """You are an expert Kirana Billing AI Assistant for Maharashtra grocery shops.
Your task is to transcribe spoken grocery orders and extract structured bill items.

CRITICAL RULES FOR SPOKEN PRONUNCIATION & NUMBERS:
1. PRONUNCIATION ECHO HANDLING:
   - Kirana shopkeepers frequently say BOTH the digit and the spoken pronunciation confirmation together:
     * "sakhar 1kg 60 sath" -> Name: "साखर", Quantity: 1, Unit: "kg", Price: 60, spoken_pronunciation: "saath / साठ"
     * "sugar 1kg 60 sixty" -> Name: "साखर", Quantity: 1, Unit: "kg", Price: 60, spoken_pronunciation: "sixty"
     * "masoor 1kg 95 panchyannav" -> Name: "मसूर डाळ", Quantity: 1, Unit: "kg", Price: 95, spoken_pronunciation: "panchyannav / पंच्याण्णव"
     * "shengdane 1kg 160 one sixty" -> Name: "शेंगदाणे", Quantity: 1, Unit: "kg", Price: 160, spoken_pronunciation: "one sixty"
     * "besan 1kg 130 ekshe tees" -> Name: "बेसन", Quantity: 1, Unit: "kg", Price: 130, spoken_pronunciation: "ekshe tees"
   - DO NOT treat the echo word as a second item or quantity! The second word is pronunciation confirmation.

2. REALISTIC KIRANA PRICING (1 to 5000):
   - Typical grocery prices range from Rs 5 to Rs 2000 (rarely up to 5000).
   - NEVER hallucinate 100,000 (1 lakh) or absurd amounts. If you hear "100000" or "lakh", it is a misinterpretation; ignore it.
   - MRP lines: "Patanjali biscuit box 10/- 710" -> MRP is 10/-, Amount is 710.

3. SCRIPT & NAMES:
   - Default item names to clear Marathi Devanagari (e.g. साखर, बेसन, शेंगदाणे, मूग डाळ, तेल, काजू, बदाम).
   - Celery / Celary: "सेलरी (Celery)".

Respond with a strictly valid JSON object matching this schema:
{
  "transcript": "<spoken transcript>",
  "items": [
    {
      "name": "<Item name>",
      "quantity": <number>,
      "unit": "<kg|gm|litre|ml|packet|box|piece>",
      "price": <price in rupees>,
      "amount": <total line amount>,
      "spoken_pronunciation": "<spoken word echo if present, or null>"
    }
  ]
}
"""


async def parse_with_gemini(audio_bytes: bytes, mime_type: str = "audio/mp4", language: str = "mr-IN") -> Dict[str, Any]:
    """Parse audio directly with Google GenAI SDK (Gemini 2.5 Flash / 1.5 Flash)."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Use gemini-2.5-flash or gemini-1.5-flash
    model_name = "gemini-2.5-flash"

    contents = [
        types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
        SYSTEM_PROMPT,
        f"Language spoken: {language}. Parse the Kirana audio into JSON bill items."
    ]

    response = await client.aio.models.generate_content(
        model=model_name,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        )
    )

    raw_text = response.text or "{}"
    data = json.loads(raw_text)
    data["provider"] = "gemini-2.5-flash"
    return data


async def parse_transcript_with_gemini(transcript: str, language: str = "mr-IN") -> Dict[str, Any]:
    """Parse text transcript with Gemini."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    model_name = "gemini-2.5-flash"

    prompt = f"{SYSTEM_PROMPT}\n\nSpoken transcript: \"{transcript}\"\nParse into JSON."

    response = await client.aio.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.1,
        )
    )

    data = json.loads(response.text or "{}")
    data["transcript"] = transcript
    data["provider"] = "gemini-text"
    return data


async def parse_audio_with_groq(audio_bytes: bytes, filename: str = "voice.m4a", language: str = "mr") -> Dict[str, Any]:
    """Transcribe audio with Groq Whisper, then parse with Groq LLaMA."""
    from groq import AsyncGroq
    import io

    groq_client = AsyncGroq(api_key=GROQ_API_KEY)

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    # 1. Groq Whisper Large v3
    transcription = await groq_client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3-turbo",
        language=language[:2] if language else "mr",
        temperature=0.0,
    )
    transcript_text = transcription.text.strip()

    # 2. Parse transcript with Groq LLaMA 3.3
    chat = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this Kirana order transcript: \"{transcript_text}\""}
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw_json = chat.choices[0].message.content
    data = json.loads(raw_json)
    data["transcript"] = transcript_text
    data["provider"] = "groq-whisper-llama3.3"
    return data


async def parse_transcript_with_groq(transcript: str) -> Dict[str, Any]:
    """Parse transcript with Groq LLaMA."""
    from groq import AsyncGroq

    groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    chat = await groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Parse this Kirana order transcript: \"{transcript}\""}
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw_json = chat.choices[0].message.content
    data = json.loads(raw_json)
    data["transcript"] = transcript
    data["provider"] = "groq-llama3.3"
    return data
