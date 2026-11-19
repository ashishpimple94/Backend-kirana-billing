"""
ai_service.py
AI Service for Voice Transcription & Kirana Bill Parsing in Python FastAPI.
Supports:
- Groq Whisper Large v3 Turbo (speech-to-text) + FastPath Regex (<5ms)
- Groq LLaMA models: 'llama-3.1-8b-instant', 'llama3-70b-8192'
- Gemini models: 'gemini-2.0-flash', 'gemini-1.5-flash'
- Fast-Path Regex parsing for instant response
"""

import os
import re
import json
import io
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from services.regex_parser import parse_bill_with_regex
from services.llm_service import MARATHI_WHISPER_PROMPT

# Load API keys from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """You are an expert Kirana Billing Assistant specialized in Indian retail grocery billing (Marathi, Hindi, English).
Extract every single grocery item with its quantity, unit, price, and amount.

CRITICAL RULES:
1. PRONUNCIATION ECHO HANDLING:
   - Kirana shopkeepers frequently say BOTH the digit and spoken pronunciation confirmation together:
     * "sakhar 1kg 60 sath" -> Name: "साखर", Quantity: 1, Unit: "kg", Price: 60, spoken_pronunciation: "sath"
     * "sugar 1kg 60 sixty" -> Name: "साखर", Quantity: 1, Unit: "kg", Price: 60, spoken_pronunciation: "sixty"
     * "masoor 1kg 95 panchyannav" -> Name: "मसूर डाळ", Quantity: 1, Unit: "kg", Price: 95, spoken_pronunciation: "panchyannav"
   - DO NOT treat the echo word as a second item or quantity! It is confirmation of the price.

2. REALISTIC KIRANA PRICING (1 to 5000):
   - Kirana grocery retail prices are strictly between 1 to 5000 rupees.
   - NEVER output 100000 (one lakh) or large numbers.

3. SCRIPT:
   - Item names in Marathi Devanagari (साखर, बेसन, शेंगदाणे, मूग डाळ, तेल, काजू, बदाम, मैदा, पोहे, चहा पावडर).
   - Celery / Celary: "सेलरी (Celery)".

Respond with strictly valid JSON:
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
    """Parse audio with Google GenAI SDK using available Gemini models."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)

    # Candidate models in order of availability
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]
    last_err = None

    for model_name in candidate_models:
        try:
            contents = [
                types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                SYSTEM_PROMPT,
                f"Language: {language}. Parse this Kirana audio into JSON bill items."
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
            data["provider"] = f"gemini ({model_name})"
            return data
        except Exception as e:
            last_err = e
            print(f"[Gemini] Model {model_name} failed: {e}")

    raise last_err or Exception("All Gemini models failed")


async def parse_transcript_with_gemini(transcript: str, language: str = "mr-IN") -> Dict[str, Any]:
    """Parse transcript with Gemini."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=GEMINI_API_KEY)
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = None

    for model_name in candidate_models:
        try:
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
            data["provider"] = f"gemini ({model_name})"
            return data
        except Exception as e:
            last_err = e
            print(f"[Gemini text] Model {model_name} failed: {e}")

    raise last_err or Exception("All Gemini text models failed")


async def parse_audio_with_groq(audio_bytes: bytes, filename: str = "voice.m4a", language: str = "mr") -> Dict[str, Any]:
    """
    1. Transcribe audio with Groq Whisper Large v3 Turbo (~300ms)
    2. Try Fast-Path Regex Parser instantly (<2ms)
    3. Fallback to active Groq chat model if needed
    """
    from groq import AsyncGroq

    groq_client = AsyncGroq(api_key=GROQ_API_KEY)

    # 1. Transcribe with Whisper
    transcription = await groq_client.audio.transcriptions.create(
        file=(filename, audio_bytes),
        model="whisper-large-v3-turbo",
        language=language[:2] if language else "mr",
        temperature=0.0,
        prompt=MARATHI_WHISPER_PROMPT,
    )
    transcript_text = (transcription.text or "").strip()

    # 2. Instant Fast-Path Regex Check (<2ms)
    regex_items = parse_bill_with_regex(transcript_text, {"language": language})
    if regex_items:
        return {
            "transcript": transcript_text,
            "items": regex_items,
            "provider": "groq-whisper + fastpath-regex",
        }

    # 3. If complex sentence, parse with active Groq chat model
    groq_models = ["llama-3.1-8b-instant", "llama3-70b-8192", "mixtral-8x7b-32768"]
    for model in groq_models:
        try:
            chat = await groq_client.chat.completions.create(
                model=model,
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
            data["provider"] = f"groq-whisper + {model}"
            return data
        except Exception as e:
            print(f"[Groq chat] Model {model} failed: {e}")

    # Fallback to whatever regex could extract
    return {
        "transcript": transcript_text,
        "items": regex_items,
        "provider": "groq-whisper-fallback",
    }


async def parse_transcript_with_groq(transcript: str) -> Dict[str, Any]:
    """Parse text transcript with Groq."""
    from groq import AsyncGroq

    groq_client = AsyncGroq(api_key=GROQ_API_KEY)
    groq_models = ["llama-3.1-8b-instant", "llama3-70b-8192", "mixtral-8x7b-32768"]

    for model in groq_models:
        try:
            chat = await groq_client.chat.completions.create(
                model=model,
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
            data["provider"] = f"groq ({model})"
            return data
        except Exception as e:
            print(f"[Groq text] Model {model} failed: {e}")

    raise Exception("All Groq chat models failed")
