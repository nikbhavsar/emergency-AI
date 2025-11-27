import os
import json
from typing import Any, Dict, List

from flask import Flask, request, jsonify
from flask_cors import CORS

from gemini_client import (
    classify_hazard_with_gemini,
    generate_guidance_with_gemini,
    deep_guidance_with_pdf,
)

app = Flask(__name__)

CORS(
    app,
    resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000", "*"]}},
    supports_credentials=False,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "situations_seed.json"), "r") as f:
    SITUATIONS: List[Dict[str, Any]] = json.load(f)

with open(os.path.join(BASE_DIR, "guides_map.json"), "r") as f:
    GUIDES_MAP: Dict[str, Dict[str, str]] = json.load(f)

MEDICAL_KEYWORDS = [
    "unconscious",
    "not breathing",
    "can't breathe",
    "cannot breathe",
    "chest pain",
    "heart attack",
    "stroke",
    "seizure",
    "bleeding a lot",
    "heavy bleeding",
    "spurting blood",
    "passed out",
]


def is_possible_medical_emergency(user_text: str) -> bool:
    """
    Simple keyword check for obvious medical emergencies.
    If this triggers, we DO NOT use AI - we just tell the user to call emergency services.
    """
    lowered = user_text.lower()
    return any(keyword in lowered for keyword in MEDICAL_KEYWORDS)


def detect_hazard_by_rules(user_text: str) -> str:
    """
    Rule-based hazard detection.
    Returns 'unknown' if nothing clearly matches.
    """
    t = user_text.lower()

    if any(word in t for word in ["fire", "smoke", "burning", "flames"]):
        return "fire"

    if any(phrase in t for phrase in [
        "power out",
        "power outage",
        "no electricity",
        "blackout",
        "lost power",
    ]):
        return "power_outage"

    if any(phrase in t for phrase in [
        "gas leak",
        "smell of gas",
        "gas smell",
    ]):
        return "gas_leak"

    if any(phrase in t for phrase in [
        "water leak",
        "pipe burst",
        "burst pipe",
        "water coming from ceiling",
        "water leaking inside",
    ]):
        return "water_leak"

    # Weather & natural hazards
    if any(phrase in t for phrase in [
        "flood",
        "water is rising",
        "basement flooded",
        "river overflow",
    ]):
        return "flood"

    if any(phrase in t for phrase in [
        "wildfire",
        "forest fire",
        "heavy smoke from fire",
    ]):
        return "wildfire"

    if any(word in t for word in ["earthquake", "tremor", "shaking", "aftershock"]):
        return "earthquake"

    if any(phrase in t for phrase in [
        "storm",
        "thunderstorm",
        "high winds",
        "hurricane",
        "tornado",
        "blizzard",
    ]):
        return "storm"

    if any(phrase in t for phrase in [
        "stuck in snow",
        "car stuck",
        "snowed in",
        "snowbank",
    ]):
        return "snow_stuck"

    # Neighbourhood safety
    if any(phrase in t for phrase in [
        "suspicious person",
        "suspicious activity",
        "someone is following me",
        "strange person outside",
    ]):
        return "suspicious_activity"

    if any(phrase in t for phrase in [
        "break in",
        "broken into",
        "window broken",
        "door forced",
        "car broken into",
        "car break in",
    ]):
        return "break_in"

    if any(phrase in t for phrase in [
        "loud music",
        "loud party",
        "noise complaint",
        "noisy neighbours",
        "noisy neighbors",
    ]):
        return "noise_issue"

    # Everyday problems
    if any(phrase in t for phrase in [
        "lost my phone",
        "phone is missing",
        "stolen phone",
        "my phone was stolen",
    ]):
        return "lost_phone"

    if any(phrase in t for phrase in [
        "lost my wallet",
        "wallet is missing",
        "wallet stolen",
        "lost my card",
        "credit card stolen",
        "debit card stolen",
    ]):
        return "lost_wallet"

    return "unknown"


HAZARD_TO_GUIDES = {
    # Home safety
    "fire": ["fema_are_you_ready", "household_preparedness"],
    "power_outage": ["canada_power_outage", "bc_power_outage", "ont_power_outage"],
    "gas_leak": ["fema_are_you_ready", "household_preparedness"],
    "water_leak": ["flood_preparedness", "household_preparedness"],

    # Weather & natural hazards
    "flood": ["flood_preparedness", "fema_are_you_ready"],
    "wildfire": ["wildfire_preparedness", "wildfire_toolkit"],
    "earthquake": ["earthquake_tsunami_guide", "household_preparedness"],
    "storm": ["winter_storm_guide", "fema_are_you_ready"],
    "snow_stuck": ["winter_storm_guide"],

    # Neighbourhood safety
    "suspicious_activity": ["household_preparedness"],
    "break_in": ["household_preparedness"],
    "noise_issue": ["household_preparedness"],

    # Everyday problems
    "lost_phone": ["household_preparedness"],
    "lost_wallet": ["household_preparedness"],

    # Fallback
    "general_safety": ["fema_are_you_ready", "household_preparedness"],
}


def choose_guides_for_hazard(hazard_label: str) -> List[str]:
    """
    Convert a hazard label into a list of guide *keys*.

    We only return the logical keys like "flood_preparedness" so the frontend
    can show them and the deep helper can use them.
    """
    guide_keys = HAZARD_TO_GUIDES.get(hazard_label, ["fema_are_you_ready"])

    # Only keep keys that actually exist in GUIDES_MAP
    valid_keys: List[str] = [key for key in guide_keys if key in GUIDES_MAP]
    return valid_keys


# -------- ROUTES --------

@app.get("/health")
def health() -> Any:
    return jsonify({"status": "ok"})


@app.get("/api/situations")
def get_situations() -> Any:
    """
    Exposes your structured list of situations and triage questions.
    Useful if your React app wants to show categories.
    """
    return jsonify(SITUATIONS)


@app.route("/api/help", methods=["POST", "OPTIONS"])
def get_help() -> Any:
    """
    Normal mode:
    Request body:
    {
      "situationText": "My basement is flooding and water is rising quickly."
    }
    """

    if request.method == "OPTIONS":
        return ("", 200)

    body = request.get_json() or {}
    situation_text = (body.get("situationText") or "").strip()

    if not situation_text:
        return jsonify({"error": "situationText is required"}), 400

    if is_possible_medical_emergency(situation_text):
        return jsonify({
            "hazard": "medical_emergency",
            "hazardSource": "rules",
            "guidesUsed": [],
            "canDeepDive": False,
            "guidance": (
                "It sounds like there might be a medical emergency. "
                "This app cannot give medical advice. Please call emergency services "
                "(911 or your local emergency number) immediately or seek urgent medical help."
            ),
            "mode": "normal",
        })

    hazard_label = detect_hazard_by_rules(situation_text)
    hazard_source = "rules"

    if hazard_label == "unknown":
        hazard_label = classify_hazard_with_gemini(situation_text)
        hazard_source = "ai"

    guides_used_keys = choose_guides_for_hazard(hazard_label)

    guidance_text = generate_guidance_with_gemini(
        user_text=situation_text,
        hazard_label=hazard_label,
    )

    return jsonify({
        "hazard": hazard_label,
        "hazardSource": hazard_source,
        "guidesUsed": guides_used_keys,
        "canDeepDive": bool(guides_used_keys),
        "guidance": guidance_text,
        "mode": "normal",
    })


@app.route("/api/help/deep", methods=["POST", "OPTIONS"])
def get_help_deep() -> Any:
    """
    Deep mode used by React:
    Request body:
    {
      "situationText": "My basement is flooding and water is rising quickly."
    }

    Logic:
    - Same as /api/help, but:
      * Always lets Gemini classify if needed
      * Uses deep_guidance_with_pdf when there's at least one matching guide
    """

    if request.method == "OPTIONS":
        return ("", 200)

    body = request.get_json() or {}
    situation_text = (body.get("situationText") or "").strip()

    if not situation_text:
        return jsonify({"error": "situationText is required"}), 400

    if is_possible_medical_emergency(situation_text):
        return jsonify({
            "hazard": "medical_emergency",
            "hazardSource": "rules",
            "guidesUsed": [],
            "canDeepDive": False,
            "guidance": (
                "It sounds like there might be a medical emergency. "
                "This app cannot give medical advice. Please call emergency services "
                "(911 or your local emergency number) immediately or seek urgent medical help."
            ),
            "mode": "deep",
        })

    # Rule-based first
    hazard_label = detect_hazard_by_rules(situation_text)
    hazard_source = "rules"

    # If unknown or we want more accuracy, ask Gemini
    if hazard_label == "unknown":
        hazard_label = classify_hazard_with_gemini(situation_text)
        hazard_source = "ai"

    guides_used_keys = choose_guides_for_hazard(hazard_label)

    # If we have at least one matching guide, use deep guidance with PDF
    if guides_used_keys:
        primary_guide_key = guides_used_keys[0]
        deep_answer = deep_guidance_with_pdf(
            user_text=situation_text,
            hazard_label=hazard_label,
            guide_key=primary_guide_key,
        )
        guidance_text = deep_answer
    else:
        # Fallback to regular guidance if no guide is available
        guidance_text = generate_guidance_with_gemini(
            user_text=situation_text,
            hazard_label=hazard_label,
        )

    return jsonify({
        "hazard": hazard_label,
        "hazardSource": hazard_source,
        "guidesUsed": guides_used_keys,
        "canDeepDive": bool(guides_used_keys),
        "guidance": guidance_text,
        "mode": "deep",
    })


@app.post("/api/deep-guidance")
def deep_guidance() -> Any:
    """
    (Optional) Original deep endpoint if you still want to use it somewhere else.

    Request body:
    {
      "situationText": "My basement is flooding and water is rising quickly.",
      "hazard": "flood",
      "guideKey": "flood_preparedness"
    }
    """
    body = request.get_json() or {}
    situation_text = (body.get("situationText") or "").strip()
    hazard = (body.get("hazard") or "").strip() or "general_safety"
    guide_key = (body.get("guideKey") or "").strip()

    if not situation_text or not guide_key:
        return jsonify({"error": "situationText and guideKey are required"}), 400

    deep_answer = deep_guidance_with_pdf(
        user_text=situation_text,
        hazard_label=hazard,
        guide_key=guide_key,
    )

    return jsonify({
        "hazard": hazard,
        "guideKey": guide_key,
        "deepGuidance": deep_answer,
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
