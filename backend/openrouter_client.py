"""
OpenRouter client - secondary AI fallback when Gemini is unavailable.

Env vars:
  OPENROUTER_API_KEY   - required for OpenRouter calls
  OPENROUTER_MODEL     - optional, defaults to "openai/gpt-4o-mini"
"""

import logging
import os
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_APP_NAME = os.environ.get("OPENROUTER_APP_NAME", "EmergencyAI")
OPENROUTER_APP_URL = os.environ.get("OPENROUTER_APP_URL", "https://github.com/nikbhavsar/emergency-AI")

MAX_INPUT_LENGTH = 2000
MAX_RETRIES = 2
RETRY_BACKOFF = 1.0
REQUEST_TIMEOUT = 30

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_APP_URL,
            "X-Title": OPENROUTER_APP_NAME,
        })
    return _session


def _truncate(text: str, max_len: int = MAX_INPUT_LENGTH) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len]


def _call_openrouter(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1024,
    temperature: float = 0.4,
) -> Optional[str]:
    if not OPENROUTER_API_KEY:
        logger.debug("OPENROUTER_API_KEY not set, skipping")
        return None

    user_prompt = _truncate(user_prompt)

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }

    last_error: Optional[Exception] = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = _get_session().post(
                OPENROUTER_BASE_URL,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()

            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")
                if text.strip():
                    return text.strip()

            logger.warning("Empty or unexpected OpenRouter response")
            return None

        except requests.exceptions.Timeout:
            logger.warning("OpenRouter request timed out (attempt %d/%d)", attempt + 1, MAX_RETRIES + 1)
            last_error = None
        except requests.exceptions.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status and 400 <= status < 500:
                logger.error("OpenRouter client error %d - not retrying", status)
                return None
            logger.warning("OpenRouter server error (attempt %d/%d)", attempt + 1, MAX_RETRIES + 1)
            last_error = exc
        except requests.exceptions.RequestException as exc:
            logger.warning("OpenRouter request failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES + 1, exc)
            last_error = exc

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_BACKOFF * (2 ** attempt))

    if last_error:
        logger.error("OpenRouter all retries exhausted")
    return None


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


HAZARD_ALIASES = {
    "power outage": "power_outage",
    "snow": "snow_stuck",
    "general": "general_safety",
}


def classify_hazard_with_openrouter(user_text: str) -> Optional[str]:
    system_prompt = (
        "You are a hazard classifier. "
        "Return exactly one label from this list:\n"
        f"{ALLOWED_HAZARDS}\n"
        "If unsure, return 'general_safety'. "
        "Reply with ONLY the label, nothing else."
    )

    result = _call_openrouter(system_prompt, user_text, max_tokens=32, temperature=0.0)
    if result is None:
        return None

    raw = result.lower().strip()
    if raw in ALLOWED_HAZARDS:
        return raw
    return HAZARD_ALIASES.get(raw, None)


def generate_guidance_with_openrouter(user_text: str, hazard_label: str) -> Optional[str]:
    system_prompt = (
        "You are a safety assistant. "
        "Provide 5-8 short, numbered, general safety steps. "
        "No medical or legal advice. "
        "If danger is immediate, remind the user to call emergency services."
    )

    user_prompt = (
        f"User description:\n\"{user_text}\"\n\n"
        f"Hazard: {hazard_label}\n\n"
        "Give clear, actionable steps for the next minutes and hours.\n"
        "Do NOT give medical or legal advice.\n"
    )

    return _call_openrouter(system_prompt, user_prompt, max_tokens=1024)


def deep_guidance_with_openrouter(user_text: str, hazard_label: str, guide_key: str) -> Optional[str]:
    readable_guide = guide_key.replace("_", " ")

    system_prompt = (
        "You are a safety assistant. The user is referencing an official emergency "
        f"preparedness guide titled '{readable_guide}'. "
        "Use your training knowledge about this type of guide to provide relevant advice. "
        "Do not invent specific quotes or page numbers. No medical or legal advice. "
        "Keep the answer under 250 words."
    )

    user_prompt = (
        f"User description:\n\"{user_text}\"\n\n"
        f"Hazard: {hazard_label}\n\n"
        f"Guide key: {guide_key}\n\n"
        "Using your knowledge of emergency preparedness best practices related to "
        f"the '{readable_guide}' guide, summarize the most relevant steps and tips."
    )

    return _call_openrouter(system_prompt, user_prompt, max_tokens=512)