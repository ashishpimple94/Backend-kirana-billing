"""
models_schema.py
Pydantic schemas for Kirana Bill, Bill Items, and Voice Payloads.
"""

from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class BillItemModel(BaseModel):
    name: str = Field(..., description="Item Name")
    quantity: float = Field(default=1.0, ge=0)
    unit: str = Field(default="piece")
    price: float = Field(default=0.0, ge=0)
    amount: float = Field(default=0.0, ge=0)
    spoken_pronunciation: Optional[str] = None


class BillCreateModel(BaseModel):
    billNumber: str
    customerName: Optional[str] = "Walk-in Customer"
    customerMobile: Optional[str] = ""
    items: List[BillItemModel]
    subtotal: Optional[float] = None
    gstRate: Optional[float] = 0.0
    gstAmount: Optional[float] = 0.0
    grandTotal: Optional[float] = None
    paymentMode: Optional[str] = "Cash"
    storeName: Optional[str] = "किराणा स्टोअर्स"
    transcript: Optional[str] = ""
    source: Optional[str] = "voice"


class ParseBillRequest(BaseModel):
    transcript: str
    language: Optional[str] = "mr-IN"
    priceMode: Optional[str] = "per_unit"
    outputLang: Optional[str] = None


class NumberToWordsRequest(BaseModel):
    number: Optional[int] = None
    line: Optional[str] = None
