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
from services.llm_service import (
    GroqProvider,
    GeminiProvider,
    OpenAIProvider,
    get_llm_provider,
    sanitize_items,
)
from models.bill import Bill, BillItem, BillCreateRequest
from models_schema import (
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
            "gemini": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
            "groq": bool(os.getenv("GROQ_API_KEY")),
            "openai": bool(os.getenv("OPENAI_API_KEY")),
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
    Tries instantaneous Fast-Path Regex Parser (<5ms), then falls back to Groq -> OpenAI -> Gemini.
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

    # 2. AI Provider cascade: Groq -> OpenAI -> Gemini
    providers = []
    if os.getenv("GROQ_API_KEY"):
        providers.append(("groq", GroqProvider()))
    if os.getenv("OPENAI_API_KEY"):
        providers.append(("openai", OpenAIProvider()))
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        providers.append(("gemini", GeminiProvider()))

    for name, prov in providers:
        try:
            res = await prov.parse_transcript(
                transcript=transcript,
                language=req.language or "mr-IN",
                price_mode=req.priceMode or "per_unit",
            )
            if res and res.get("items"):
                return {
                    "success": True,
                    "transcript": res.get("transcript") or transcript,
                    "items": res.get("items", []),
                    "priceMode": req.priceMode,
                    "provider": res.get("provider", name),
                }
        except Exception as e:
            print(f"[FastAPI parse-bill] {name} fallback failed: {e}")

    # Fallback to regex results
    return {
        "success": True,
        "transcript": transcript,
        "items": fast_items or [],
        "priceMode": req.priceMode,
        "provider": "regex-fallback",
    }


@app.post("/api/voice-to-bill")
async def api_voice_to_bill(
    request: Request,
    audio: Optional[UploadFile] = File(None),
):
    """
    Receives voice audio (file upload, binary body, or JSON with base64)
    and converts it into bill items with spoken pronunciations.
    Provider cascade: Groq Whisper Large v3 Turbo -> OpenAI -> Gemini.
    """
    qp = request.query_params
    language = qp.get("language", "mr-IN")
    priceMode = qp.get("priceMode", "per_unit")
    outputLang = qp.get("outputLang", None)

    audio_bytes = None
    mime_type = "audio/mp4"

    # Check multipart form
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
                    outputLang = body.get("outputLang", outputLang)
            except Exception:
                pass
        elif "multipart/form-data" in ct:
            try:
                form = await request.form()
                form_file = form.get("audio")
                if form_file and hasattr(form_file, "read"):
                    audio_bytes = await form_file.read()
                    mime_type = getattr(form_file, "content_type", "audio/mp4")
                language = form.get("language", language)
                priceMode = form.get("priceMode", priceMode)
                outputLang = form.get("outputLang", outputLang)
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

    # Provider cascade: Groq -> OpenAI -> Gemini
    providers = []
    if os.getenv("GROQ_API_KEY"):
        providers.append(("groq", GroqProvider()))
    if os.getenv("OPENAI_API_KEY"):
        providers.append(("openai", OpenAIProvider()))
    if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        providers.append(("gemini", GeminiProvider()))

    last_err = None
    for name, prov in providers:
        for attempt in range(1, 3):
            try:
                res = await prov.parse_audio(
                    audio_bytes=audio_bytes,
                    mime_type=mime_type,
                    language=language,
                    price_mode=priceMode,
                    output_lang=outputLang,
                )
                print(f"[FastAPI voice-to-bill] {name} attempt {attempt}: {len(res.get('items', []))} items. Transcript: \"{res.get('transcript')}\"")
                return {
                    "success": True,
                    "transcript": res.get("transcript", ""),
                    "items": res.get("items", []),
                    "priceMode": priceMode,
                    "provider": res.get("provider", name),
                }
            except Exception as e:
                last_err = e
                print(f"[FastAPI voice-to-bill] {name} attempt {attempt} failed: {e}")

    raise HTTPException(
        status_code=500,
        detail=f"Audio processing failed: {str(last_err)}"
    )


# ── MongoDB Bills CRUD Routes ──

@app.post("/api/bills")
async def create_bill(bill_in: BillCreateRequest):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")

    # Generate unique billNumber if not supplied or if it already exists
    final_bill_number = bill_in.billNumber or f"BILL-{int(time.time())}"
    existing = await db.bills.find_one({"billNumber": final_bill_number})
    if existing:
        final_bill_number = f"{final_bill_number}-{int(time.time() * 1000) % 10000}"
        while await db.bills.find_one({"billNumber": final_bill_number}):
            final_bill_number = f"{bill_in.billNumber or 'BILL'}-{int(time.time() * 1000) % 100000}"

    # Build Bill model instance with computed totals
    bill_obj = Bill(
        billNumber=final_bill_number,
        customerName=bill_in.customerName or "Walk-in Customer",
        customerMobile=bill_in.customerMobile or "",
        items=bill_in.items,
        gstRate=bill_in.gstRate or 0.0,
        paymentMode=bill_in.paymentMode or "Cash",
        storeName=bill_in.storeName or "Bilzy Store",
        transcript=bill_in.transcript or "",
        source=bill_in.source or "voice",
    )
    bill_obj.compute_totals()
    if bill_in.grandTotal is not None:
        bill_obj.grandTotal = bill_in.grandTotal
    if bill_in.subtotal is not None:
        bill_obj.subtotal = bill_in.subtotal

    bill_doc = bill_obj.to_mongo()
    try:
        res = await db.bills.insert_one(bill_doc)
    except Exception as e:
        if "duplicate key" in str(e).lower() or "11000" in str(e):
            final_bill_number = f"{bill_in.billNumber or 'BILL'}-{int(time.time() * 1000) % 100000}"
            bill_obj.billNumber = final_bill_number
            bill_doc = bill_obj.to_mongo()
            res = await db.bills.insert_one(bill_doc)
        else:
            raise

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
