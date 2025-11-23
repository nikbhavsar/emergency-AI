import json
import os
from pathlib import Path
from typing import List, Dict, Optional

from google import genai
from google.genai import types


# CONFIG

BASE_DIR = Path(__file__).parent
GUIDES_MAP_PATH = BASE_DIR / "guides_map.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

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

def load_guides_map() -> Dict[str, Dict[str, str]]:
    if not GUIDES_MAP_PATH.exists():
        print("[gemini] guides_map.json not found")
        return {}
    try:
        return json.loads(GUIDES_MAP_PATH.read_text())
    except Exception as e:
        print("[gemini] Error reading guides_map.json:", repr(e))
        return {}


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
            print(f"[gemini] guide key '{key}' not found in guides_map.json")
    return valid


def get_guide_file_uri(guide_key: str) -> Optional[tuple[str, str]]:
    """
    Returns (file_uri, mime_type) for a given guide_key
    using the new guides_map.json structure.
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
        f"General non-medical safety steps ({readable}):\n\n"
        "1. Ensure your immediate safety. If this feels life-threatening, call emergency services.\n"
        "2. Avoid obvious hazards (fire, water, electrical, gas, unstable structures, unsafe roads).\n"
        "3. Move to a safer location if possible.\n"
        "4. Follow official alerts or local authority instructions.\n"
        "5. Inform a trusted neighbour or family member.\n"
        "6. Keep your phone charged and monitor conditions.\n\n"
        f"Your description:\n\"{user_text}\"\n"
    )
