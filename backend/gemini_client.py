import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Optional

import boto3
from google import genai
from google.genai import types

from openrouter_client import (
    ALLOWED_HAZARDS,
    HAZARD_ALIASES,
    classify_hazard_with_openrouter,
    generate_guidance_with_openrouter,
    deep_guidance_with_openrouter,
)

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
GUIDES_MAP_PATH = BASE_DIR / "guides_map.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
MAX_INPUT_LENGTH = 2000

AWS_REGION = os.environ.get("AWS_REGION", "us-west-2")
S3_GUIDES_BUCKET = os.environ.get("S3_GUIDES_BUCKET")
S3_GUIDES_KEY = os.environ.get("S3_GUIDES_KEY", "guides/guides_map.json")

_s3_client = boto3.client("s3", region_name=AWS_REGION) if S3_GUIDES_BUCKET else None
_guides_cache: Optional[Dict[str, Dict[str, str]]] = None
_gemini_client: Optional[genai.Client] = None
_last_provider: str = "none"

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


def get_last_provider() -> str:
    return _last_provider


def _truncate(text: str, max_len: int = MAX_INPUT_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _get_client() -> Optional[genai.Client]:
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set")
        return None
    _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client


def load_guides_map(force_refresh: bool = False) -> Dict[str, Dict[str, str]]:
    global _guides_cache

    if _guides_cache is not None and not force_refresh:
        return _guides_cache

    if _s3_client and S3_GUIDES_BUCKET:
        try:
            resp = _s3_client.get_object(Bucket=S3_GUIDES_BUCKET, Key=S3_GUIDES_KEY)
            _guides_cache = json.loads(resp["Body"].read().decode("utf-8"))
            logger.info("Loaded guides_map from S3")
            return _guides_cache
        except Exception:
            logger.warning("Failed to load guides_map from S3, falling back to local")

    if GUIDES_MAP_PATH.exists():
        try:
            _guides_cache = json.loads(GUIDES_MAP_PATH.read_text())
            logger.info("Loaded guides_map from local file")
            return _guides_cache
        except Exception:
            logger.error("Failed to load local guides_map.json")

    _guides_cache = {}
    return _guides_cache


def get_guides_for_hazard(hazard_label: str) -> List[str]:
    guides_map = load_guides_map()
    guide_keys = HAZARD_GUIDE_MAP.get(hazard_label, []) or HAZARD_GUIDE_MAP["general_safety"]

    valid: List[str] = []
    for key in guide_keys:
        if key in guides_map:
            valid.append(key)
        else:
            logger.debug("Guide key '%s' not found in guides_map", key)
    return valid


def get_guide_file_uri(guide_key: str) -> Optional[tuple[str, str]]:
    guides_map = load_guides_map()
    entry = guides_map.get(guide_key)
    if not entry or not entry.get("file_uri"):
        return None
    return entry["file_uri"], entry.get("mime_type", "application/pdf")


def classify_hazard_with_gemini(user_text: str) -> str:
    global _last_provider
    client = _get_client()
    if client is None:
        or_result = classify_hazard_with_openrouter(user_text)
        if or_result is not None:
            _last_provider = "openrouter"
            return or_result
        _last_provider = "fallback"
        return "general_safety"

    system_prompt = (
        "You are a hazard classifier. "
        "Return exactly one label from this list:\n"
        f"{ALLOWED_HAZARDS}\n"
        "If unsure, return 'general_safety'."
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_truncate(user_text),
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
    except Exception:
        logger.exception("Gemini classification failed")
        or_result = classify_hazard_with_openrouter(user_text)
        if or_result is not None:
            _last_provider = "openrouter"
            return or_result
        _last_provider = "fallback"
        return "general_safety"

    _last_provider = "gemini"

    raw = (response.text or "").strip().lower()
    logger.debug("Gemini classifier raw = %s", raw)

    if raw in ALLOWED_HAZARDS:
        return raw
    return HAZARD_ALIASES.get(raw, "general_safety")


def generate_guidance_with_gemini(user_text: str, hazard_label: str) -> str:
    global _last_provider
    client = _get_client()
    if client is None:
        or_text = generate_guidance_with_openrouter(user_text, hazard_label)
        if or_text:
            _last_provider = "openrouter"
            return or_text
        _last_provider = "fallback"
        return fallback_guidance(user_text, hazard_label)

    system_prompt = (
        "You are a safety assistant. "
        "Provide 5-8 short, numbered, general safety steps. "
        "No medical or legal advice. "
        "If danger is immediate, remind the user to call emergency services."
    )

    user_prompt = (
        f"User description:\n\"{_truncate(user_text)}\"\n\n"
        f"Hazard: {hazard_label}\n\n"
        "Give clear, actionable steps for the next minutes and hours.\n"
        "Do NOT give medical or legal advice.\n"
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        text = (response.text or "").strip()
        if text:
            _last_provider = "gemini"
            return text
        logger.warning("Gemini returned empty text")
    except Exception:
        logger.exception("Gemini guidance generation failed")

    or_text = generate_guidance_with_openrouter(user_text, hazard_label)
    if or_text:
        _last_provider = "openrouter"
        return or_text
    _last_provider = "fallback"
    return fallback_guidance(user_text, hazard_label)


def deep_guidance_with_pdf(user_text: str, hazard_label: str, guide_key: str) -> str:
    global _last_provider
    client = _get_client()
    if client is None:
        or_text = deep_guidance_with_openrouter(user_text, hazard_label, guide_key)
        if or_text:
            _last_provider = "openrouter"
            return or_text
        _last_provider = "fallback"
        return "AI service is currently unavailable. Please try again later."

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
        f"User description:\n\"{_truncate(user_text)}\"\n\n"
        f"Hazard: {hazard_label}\n\n"
        f"Guide key: {guide_key}\n\n"
        "Using ONLY the attached guide, summarize the most relevant steps and tips."
    )

    parts = [
        types.Part(text=user_prompt),
        types.Part(file_data={"file_uri": file_uri, "mime_type": mime_type}),
    ]

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=parts,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        text = (response.text or "").strip()
        if text:
            _last_provider = "gemini"
            return text
        logger.warning("Gemini returned empty text for deep guidance")
    except Exception:
        logger.exception("Gemini deep guidance failed")

    or_text = deep_guidance_with_openrouter(user_text, hazard_label, guide_key)
    if or_text:
        _last_provider = "openrouter"
        return or_text
    _last_provider = "fallback"
    return "AI service is currently unavailable. Please try again later."


def fallback_guidance(user_text: str, hazard_label: str) -> str:
    readable = hazard_label.replace("_", " ")
    return (
        "We couldn't find a closely matching situation or specific guide for this, "
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