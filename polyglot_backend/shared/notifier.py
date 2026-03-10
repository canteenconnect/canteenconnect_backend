import os

import httpx
from dotenv import load_dotenv

load_dotenv()

FLASK_SERVICE_URL = os.getenv("FLASK_SERVICE_URL", "http://flask:8002")
INTERNAL_EVENT_TOKEN = os.getenv("INTERNAL_EVENT_TOKEN", "internal-token")


async def emit_event(event_name: str, payload: dict):
    url = f"{FLASK_SERVICE_URL.rstrip('/')}/internal/events/{event_name}"
    headers = {"x-internal-token": INTERNAL_EVENT_TOKEN}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(url, json=payload, headers=headers)
    except Exception:
        # Eventing failures should not fail core transactions.
        return