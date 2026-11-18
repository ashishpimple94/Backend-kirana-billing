"""
bill.py
Python Pydantic model for MongoDB 'Bill' and 'BillItem' documents.
Converted directly from Mongoose models/Bill.js.
"""

from datetime import datetime, timezone
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict


class BillItem(BaseModel):
    name: str = Field(..., min_length=1, description="Item name (required, trimmed)")
    quantity: float = Field(default=1.0, ge=0.0, description="Quantity (min 0, default 1)")
    unit: str = Field(default="piece", description="Unit of measurement: kg, gm, litre, packet, piece, box")
    price: float = Field(default=0.0, ge=0.0, description="Unit price in rupees (min 0)")
    amount: float = Field(default=0.0, ge=0.0, description="Total line amount (quantity * price)")
    spoken_pronunciation: Optional[str] = Field(None, description="Spoken pronunciation echo confirmation")

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    @property
    def item_amount(self) -> float:
        return round(self.amount if self.amount > 0 else (self.quantity * self.price), 2)

    def calculate_amount(self) -> float:
        """Helper to compute line total."""
        if self.amount <= 0:
            self.amount = round(self.quantity * self.price, 2)
        return self.amount


class Bill(BaseModel):
    id: Optional[str] = Field(None, alias="_id", description="MongoDB ObjectId string")
    billNumber: str = Field(..., min_length=1, description="Unique bill number (indexed)")
    customerName: str = Field(default="Walk-in Customer", description="Customer full name")
    customerMobile: str = Field(default="", description="Customer contact number")
    items: List[BillItem] = Field(default_factory=list, description="Array of billed items")
    subtotal: float = Field(default=0.0, ge=0.0, description="Sum of all item amounts")
    gstRate: float = Field(default=0.0, ge=0.0, description="GST rate percentage (e.g. 5, 12, 18)")
    gstAmount: float = Field(default=0.0, ge=0.0, description="Calculated GST in rupees")
    grandTotal: float = Field(default=0.0, ge=0.0, description="Subtotal + GST amount")
    paymentMode: Literal["Cash", "UPI", "Credit", "Pending"] = Field(
        default="Cash", description="Payment method"
    )
    storeName: str = Field(default="Bilzy Store", description="Store or shop name")
    transcript: str = Field(default="", description="Original audio transcript text")
    source: Literal["voice", "manual", "scanner"] = Field(
        default="voice", description="Order capture source"
    )
    createdAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp"
    )
    updatedAt: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp"
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    def compute_totals(self) -> None:
        """Computes subtotal, gstAmount, and grandTotal accurately."""
        for it in self.items:
            it.calculate_amount()
        self.subtotal = round(sum(it.amount for it in self.items), 2)
        self.gstAmount = round((self.subtotal * (self.gstRate or 0.0)) / 100.0, 2)
        self.grandTotal = round(self.subtotal + self.gstAmount, 2)

    def to_mongo(self) -> dict:
        """Converts model to dictionary suitable for MongoDB collection insertion."""
        self.compute_totals()
        doc = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in doc and not doc["_id"]:
            del doc["_id"]
        return doc

    @classmethod
    def from_mongo(cls, doc: dict) -> "Bill":
        """Constructs a Bill instance from a raw MongoDB document."""
        if not doc:
            return None
        doc_copy = dict(doc)
        if "_id" in doc_copy:
            doc_copy["_id"] = str(doc_copy["_id"])
        return cls(**doc_copy)


class BillCreateRequest(BaseModel):
    """Payload schema when creating a bill from the app."""
    billNumber: Optional[str] = None
    customerName: Optional[str] = "Walk-in Customer"
    customerMobile: Optional[str] = ""
    items: List[BillItem]
    subtotal: Optional[float] = None
    gstRate: Optional[float] = 0.0
    gstAmount: Optional[float] = None
    grandTotal: Optional[float] = None
    paymentMode: Optional[Literal["Cash", "UPI", "Credit", "Pending"]] = "Cash"
    storeName: Optional[str] = "Bilzy Store"
    transcript: Optional[str] = ""
    source: Optional[Literal["voice", "manual", "scanner"]] = "voice"
