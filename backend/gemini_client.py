import json
import os
from pathlib import Path
from typing import List, Dict, Optional

import boto3
from google import genai
from google.genai import types


# CONFIG

BASE_DIR = Path(__file__).parent
GUIDES_MAP_PATH = BASE_DIR / "guides_map.json" 

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
S3_GUIDES_BUCKET = os.environ.get("S3_GUIDES_BUCKET")
S3_GUIDES_KEY = os.environ.get("S3_GUIDES_KEY", "guides/guides_map.json")

# S3 client & in-memory cache for guides_map
_s3_client = boto3.client("s3", region_name=AWS_REGION) if S3_GUIDES_BUCKET else None
_guides_cache: Optional[Dict[str, Dict[str, str]]] = None

ALLOWED_HAZARDS = [
    "fire",
    "power_outage",
    "gas_leak",
    "water_leak",
    "flood",
    "earthquake",
    "wildfire",
    "storm",
    "snow_stuck",
    "suspicious_activity",
    "break_in",
    "noise_issue",
    "lost_phone",
    "lost_wallet",
    "general_safety",
]

HAZARD_GUIDE_MAP: Dict[str, List[str]] = {
    "fire": ["fema_are_you_ready", "household_preparedness", "wildfire_toolkit"],
    "wildfire": ["wildfire_preparedness", "wildfire_toolkit", "fema_are_you_ready"],
    "flood": ["flood_preparedness", "household_preparedness"],
    "earthquake": ["earthquake_tsunami_guide", "fema_are_you_ready"],
    "storm": ["winter_storm_guide", "household_preparedness"],
    "snow_stuck": ["winter_storm_guide", "household_preparedness"],
    "power_outage": ["bc_power_outage", "canada_power_outage", "ont_power_outage"],
    "suspicious_activity": ["household_preparedness"],
    "break_in": ["household_preparedness"],
    "noise_issue": ["household_preparedness"],
    "lost_phone": ["household_preparedness"],
    "lost_wallet": ["household_preparedness"],
    "gas_leak": ["fema_are_you_ready", "household_preparedness"],
    "water_leak": ["household_preparedness"],
    "general_safety": ["fema_are_you_ready", "household_preparedness"],
}


def get_client() -> Optional[genai.Client]:
    if not GEMINI_API_KEY:
        print("[gemini] No GEMINI_API_KEY set")
        return None
    return genai.Client(api_key=GEMINI_API_KEY)


# GUIDE MAP HELPERS

def load_guides_map(force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
    """
    Load guides_map.json, preferring S3 if configured.
    Uses an in-memory cache unless force_refresh=True.
    """
    global _guides_cache

    if _guides_cache is not None and not force_refresh:
        return _guides_cache

    if _s3_client and S3_GUIDES_BUCKET:
        try:
            print(f"[gemini] Loading guides_map.json from S3: s3://{S3_GUIDES_BUCKET}/{S3_GUIDES_KEY}")
            resp = _s3_client.get_object(Bucket=S3_GUIDES_BUCKET, Key=S3_GUIDES_KEY)
            data = resp["Body"].read()
            _guides_cache = json.loads(data.decode("utf-8"))
            return _guides_cache
        except Exception as e:
            print("[gemini] Error loading guides_map.json from S3:", repr(e))

    if GUIDES_MAP_PATH.exists():
        try:
            print(f"[gemini] Loading guides_map.json from local file: {GUIDES_MAP_PATH}")
            _guides_cache = json.loads(GUIDES_MAP_PATH.read_text())
            return _guides_cache
        except Exception as e:
            print("[gemini] Error reading local guides_map.json:", repr(e))

    print("[gemini] No guides_map.json found in S3 or local file")
    _guides_cache = {}
    return _guides_cache


def get_guides_for_hazard(hazard_label: str) -> List[str]:
    """
    Returns a list of guide KEYS (strings) for UI / guidesUsed.
    No Files API here. This is cheap metadata only.
    """
    guides_map = load_guides_map()
    guide_keys = HAZARD_GUIDE_MAP.get(hazard_label, []) or HAZARD_GUIDE_MAP["general_safety"]

    valid: List[str] = []
    for key in guide_keys:
        if key in guides_map:
            valid.append(key)
        else:
            print(f"[gemini] guide key '{key}' not found in guides_map")
    return valid


def get_guide_file_uri(guide_key: str) -> Optional[tuple[str, str]]:
    """
    Returns (file_uri, mime_type) for a given guide_key
    using the guides_map structure loaded from S3 (or local fallback).
    """
    guides_map = load_guides_map()
    entry = guides_map.get(guide_key)
    if not entry:
        print(f"[gemini] No guides_map entry for '{guide_key}'")
        return None

    file_uri = entry.get("file_uri")
    mime_type = entry.get("mime_type", "application/pdf")

    if not file_uri:
        print(f"[gemini] guides_map entry for '{guide_key}' missing file_uri")
        return None

    return file_uri, mime_type


def classify_hazard_with_gemini(user_text: str) -> str:
    client = get_client()
    if client is None:
        return "general_safety"

    system_prompt = (
        "You are a hazard classifier. "
        "Return exactly one label from this list:\n"
        f"{ALLOWED_HAZARDS}\n"
        "If unsure, return 'general_safety'."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            ),
        )
    except Exception as e:
        print("[gemini] Error in classification:", repr(e))
        return "general_safety"

    raw = (response.text or "").strip().lower()
    print("[gemini] classifier raw =", raw)

    if raw in ALLOWED_HAZARDS:
        return raw

    aliases = {
        "power outage": "power_outage",
        "snow": "snow_stuck",
        "general": "general_safety",
    }
    return aliases.get(raw, "general_safety")


def generate_guidance_with_gemini(
    user_text: str,
    hazard_label: str,
) -> str:
    client = get_client()
    if client is None:
        return fallback_guidance(user_text, hazard_label)

    system_prompt = (
        "You are a safety assistant. "
        "Provide 5–8 short, numbered, general safety steps. "
        "No medical or legal advice. "
        "If danger is immediate, remind the user to call emergency services."
    )

    user_prompt = (
        f"User description:\n\"{user_text}\"\n\n"
        f"Hazard: {hazard_label}\n\n"
        "Give clear, actionable steps for the next minutes and hours.\n"
        "Do NOT give medical or legal advice.\n"
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            ),
        )
        text = (response.text or "").strip()
        if not text:
            print("[gemini] Empty model text → fallback")
            return fallback_guidance(user_text, hazard_label)
        return text
    except Exception as e:
        print("[gemini] Error in generate_guidance_with_gemini:", repr(e))
        return fallback_guidance(user_text, hazard_label)


def deep_guidance_with_pdf(
    user_text: str,
    hazard_label: str,
    guide_key: str,
) -> str:
    client = get_client()
    if client is None:
        return "Gemini API key not configured."

    result = get_guide_file_uri(guide_key)
    if not result:
        return f"Guide '{guide_key}' is not available."

    file_uri, mime_type = result

    system_prompt = (
        "You are a safety assistant. Use ONLY the attached PDF as your source. "
        "Do not invent information. No medical or legal advice. "
        "Keep the answer under 250 words."
    )

    user_prompt = (
        f"User description:\n\"{user_text}\"\n\n"
        f"Hazard: {hazard_label}\n\n"
        f"Guide key: {guide_key}\n\n"
        "Using ONLY the attached guide, summarize the most relevant steps and tips."
    )

    parts = [
        types.Part(text=user_prompt),
        types.Part(
            file_data={
                "file_uri": file_uri,
                "mime_type": mime_type,
            }
        ),
    ]

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=parts,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt
            ),
        )
        text = (response.text or "").strip()
        if not text:
            return "Got an empty response from Gemini when using the PDF."
        return text
    except Exception as e:
        print("[gemini] Error in deep_guidance_with_pdf:", repr(e))
        return f"There was an error using Gemini Files API for this guide: {e}"


def fallback_guidance(user_text: str, hazard_label: str) -> str:
    readable = hazard_label.replace("_", " ")
    return (
        "We couldn’t find a closely matching situation or specific guide for this, "
        "so here are general, non-medical safety steps you can consider "
        f"(interpreting this as '{readable}'):\n\n"
        "1. Make sure you and anyone with you are safe. If you ever feel in danger or this "
        "seems life-threatening, call emergency services (911 or your local number) immediately.\n"
        "2. Look around and identify any obvious hazards related to the situation. Stay away "
        "from fire, rising water, damaged electrical lines, unstable structures, or unsafe roads.\n"
        "3. If it is safe to move, go to a safer location (for example, higher ground in a flood, "
        "outside away from smoke in a fire, or away from windows during a storm).\n"
        "4. If local authorities or official sources (emergency alerts, government websites, "
        "trusted news) are giving guidance, follow that advice first.\n"
        "5. Let a trusted friend, neighbour, or family member know what is happening if you can.\n"
        "6. Keep your phone charged if possible and be ready to call emergency services if "
        "the situation gets worse.\n\n"
        f"Your description was:\n\"{user_text}\"\n"
    )
