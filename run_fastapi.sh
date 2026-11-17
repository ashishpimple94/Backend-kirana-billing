#!/bin/bash
# Bilzy FastAPI Server Launcher for Ubuntu / EC2
echo "Starting Bilzy FastAPI Kirana Voice Billing Server on port 5000..."
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 5000 --workers 4
