"""
main.py
FastAPI Kirana Voice Billing Server
Provides:
- /api/health
- /api/voice-to-bill
- /api/parse-bill
- /api/number-to-words
- /api/bills (CRUD with MongoDB)
"""

import os
import io
import time
import base64
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from services.marathi_normalizer import (
    number_to_marathi_words,
    convert_bill_line_to_speech,
)
from services.regex_parser import parse_bill_with_regex
from services.ai_service import (
    parse_with_gemini,
    parse_transcript_with_gemini,
    parse_audio_with_groq,
    parse_transcript_with_groq,
    GEMINI_API_KEY,
    GROQ_API_KEY,
)
from models_schema import (
    BillCreateModel,
    ParseBillRequest,
    NumberToWordsRequest,
)
from db import get_database

app = FastAPI(
    title="Bilzy Kirana Voice Billing API",
    description="Python FastAPI engine for Kirana Voice-to-Bill with spoken pronunciation recognition and accurate 1-5000 pricing.",
    version="2.0.0",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    db = get_database()
    db_status = "connected" if db is not None else "disconnected"
    return {
        "status": "ok",
        "service": "bilzy-kirana-fastapi",
        "database": {"status": db_status},
        "providers": {
            "gemini": bool(GEMINI_API_KEY),
            "groq": bool(GROQ_API_KEY),
        },
        "version": "2.0.0",
    }


@app.post("/api/number-to-words")
async def api_number_to_words(req: NumberToWordsRequest):
    """
    Converts numbers or complete bill lines into Marathi spoken words.
    Example:
    Input: line="Patanjali biscuit box 10/- 710"
    Output: "Patanjali biscuit box 10/- satshey daha rupaye 710"
    """
    if req.line:
        speech_line = convert_bill_line_to_speech(req.line)
        return {"line": req.line, "speech": speech_line}
    if req.number is not None:
        words = number_to_marathi_words(req.number)
        return {"number": req.number, "words": f"{words} rupaye"}
    raise HTTPException(status_code=400, detail="Either 'number' or 'line' must be provided.")


@app.post("/api/parse-bill")
async def api_parse_bill(req: ParseBillRequest):
    """
    Parses a Kirana spoken order transcript into structured line items.
    Tries instantaneous Fast-Path Regex Parser (<5ms), then falls back to Groq/Gemini.
    """
    t_start = time.time()
    transcript = req.transcript.strip()
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript text is required.")

    # 1. Fast-path local regex parser (<5ms)
    fast_items = parse_bill_with_regex(
        transcript,
        {"priceMode": req.priceMode, "language": req.language}
    )
    if fast_items:
        elapsed_ms = round((time.time() - t_start) * 1000, 2)
        return {
            "success": True,
            "transcript": transcript,
            "items": fast_items,
            "priceMode": req.priceMode,
            "provider": "fastpath-regex",
            "elapsedMs": elapsed_ms,
        }

    # 2. AI Provider: Groq LLaMA 3.3 (fastest ~200ms) or Gemini Flash
    if GROQ_API_KEY:
        try:
            groq_res = await parse_transcript_with_groq(transcript)
            if groq_res and groq_res.get("items"):
                return {
                    "success": True,
                    "transcript": transcript,
                    "items": groq_res["items"],
                    "priceMode": req.priceMode,
                    "provider": "groq-llama3.3",
                }
        except Exception as e:
            print(f"[FastAPI parse-bill] Groq fallback failed: {e}")

    if GEMINI_API_KEY:
        try:
            gemini_res = await parse_transcript_with_gemini(transcript, req.language)
            return {
                "success": True,
                "transcript": transcript,
                "items": gemini_res.get("items", []),
                "priceMode": req.priceMode,
                "provider": "gemini-2.5-flash",
            }
        except Exception as e:
            print(f"[FastAPI parse-bill] Gemini fallback failed: {e}")

    # Fallback to regex results
    return {
        "success": True,
        "transcript": transcript,
        "items": fast_items,
        "priceMode": req.priceMode,
        "provider": "regex-fallback",
    }


@app.post("/api/voice-to-bill")
async def api_voice_to_bill(
    request: Request,
    audio: Optional[UploadFile] = File(None),
    language: Optional[str] = Form("mr-IN"),
    priceMode: Optional[str] = Form("per_unit"),
):
    """
    Receives voice audio (file upload, binary body, or JSON with base64)
    and converts it into bill items with spoken pronunciations.
    """
    audio_bytes = None
    mime_type = "audio/mp4"

    # Check multipart file
    if audio is not None:
        audio_bytes = await audio.read()
        mime_type = audio.content_type or "audio/mp4"

    # Check raw binary or base64 JSON
    if not audio_bytes:
        ct = (request.headers.get("content-type") or "").lower()
        if "application/json" in ct:
            try:
                body = await request.json()
                if "audioBase64" in body:
                    audio_bytes = base64.b64decode(body["audioBase64"])
                    mime_type = body.get("mimeType", "audio/mp4")
                    language = body.get("language", language)
                    priceMode = body.get("priceMode", priceMode)
            except Exception:
                pass
        elif "audio/" in ct or "video/" in ct or "octet-stream" in ct:
            audio_bytes = await request.body()
            mime_type = ct

    if not audio_bytes or len(audio_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail="Audio data is required. Please upload an audio file or base64 audio."
        )

    # 1. Cascade: Groq Whisper (ultra fast ~300ms) -> Gemini 2.5 Flash
    if GROQ_API_KEY:
        try:
            res = await parse_audio_with_groq(audio_bytes, "recording.m4a", language)
            return {
                "success": True,
                "transcript": res.get("transcript", ""),
                "items": res.get("items", []),
                "priceMode": priceMode,
                "provider": "groq-whisper",
            }
        except Exception as e:
            print(f"[FastAPI voice-to-bill] Groq failed: {e}")

    if GEMINI_API_KEY:
        try:
            res = await parse_with_gemini(audio_bytes, mime_type, language)
            return {
                "success": True,
                "transcript": res.get("transcript", ""),
                "items": res.get("items", []),
                "priceMode": priceMode,
                "provider": "gemini-2.5-flash",
            }
        except Exception as e:
            print(f"[FastAPI voice-to-bill] Gemini failed: {e}")

    raise HTTPException(
        status_code=500,
        detail="Audio processing failed. Please check your API keys or network connection."
    )


# ── MongoDB Bills CRUD Routes ──

@app.post("/api/bills")
async def create_bill(bill_in: BillCreateModel):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    items_dicts = [it.dict() for it in bill_in.items]
    subtotal = bill_in.subtotal or sum(it["amount"] or (it["quantity"] * it["price"]) for it in items_dicts)
    gst_amt = bill_in.gstAmount or round((subtotal * (bill_in.gstRate or 0)) / 100, 2)
    grand_total = bill_in.grandTotal or round(subtotal + gst_amt, 2)

    bill_doc = bill_in.dict()
    bill_doc["items"] = items_dicts
    bill_doc["subtotal"] = subtotal
    bill_doc["gstAmount"] = gst_amt
    bill_doc["grandTotal"] = grand_total
    bill_doc["created_at"] = time.time()

    res = await db.bills.insert_one(bill_doc)
    bill_doc["_id"] = str(res.inserted_id)

    return {
        "success": True,
        "message": "पावती डेटाबेसमध्ये यशस्वीरीत्या जतन केली!",
        "bill": bill_doc,
    }


@app.get("/api/bills")
async def list_bills(limit: int = 50, page: int = 1):
    db = get_database()
    if db is None:
        return {"success": True, "total": 0, "page": page, "limit": limit, "bills": []}

    skip = (page - 1) * limit
    cursor = db.bills.find().sort("created_at", -1).skip(skip).limit(limit)
    bills = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        bills.append(doc)

    total = await db.bills.count_documents({})
    return {
        "success": True,
        "total": total,
        "page": page,
        "limit": limit,
        "bills": bills,
    }


@app.get("/api/bills/{bill_id}")
async def get_bill(bill_id: str):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    doc = await db.bills.find_one({"billNumber": bill_id})
    if not doc:
        try:
            from bson import ObjectId
            doc = await db.bills.find_one({"_id": ObjectId(bill_id)})
        except Exception:
            pass

    if not doc:
        raise HTTPException(status_code=404, detail="Bill not found")

    doc["_id"] = str(doc["_id"])
    return {"success": True, "bill": doc}


@app.delete("/api/bills/{bill_id}")
async def delete_bill(bill_id: str):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    res = await db.bills.delete_one({"billNumber": bill_id})
    if res.deleted_count == 0:
        try:
            from bson import ObjectId
            res = await db.bills.delete_one({"_id": ObjectId(bill_id)})
        except Exception:
            pass

    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Bill not found")

    return {"success": True, "message": "पावती डेटाबेसमधून हटवली."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 5000)), reload=True)
