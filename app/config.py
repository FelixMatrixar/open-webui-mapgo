import os
from dotenv import load_dotenv

load_dotenv()

BACKEND_MAPS_KEY = os.getenv("BACKEND_MAPS_KEY")
FRONTEND_MAPS_KEY = os.getenv("FRONTEND_MAPS_KEY")

if not BACKEND_MAPS_KEY or not FRONTEND_MAPS_KEY:
    raise ValueError("Missing Map API keys. Check your .env file for BACKEND_MAPS_KEY and FRONTEND_MAPS_KEY.")

MAPGO_API_SECRET = os.getenv("MAPGO_API_SECRET")
if not MAPGO_API_SECRET:
    raise ValueError("Missing MAPGO_API_SECRET in .env")