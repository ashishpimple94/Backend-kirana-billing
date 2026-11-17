"""
db.py
Async MongoDB connection using motor.
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGODB_URI = os.getenv("MONGODB_URI", "")
client = None
db = None

def get_database():
    global client, db
    if db is not None:
        return db
    if not MONGODB_URI:
        return None
    try:
        client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client.get_default_database()
        return db
    except Exception as e:
        print(f"⚠️ MongoDB connection failed: {e}")
        return None
