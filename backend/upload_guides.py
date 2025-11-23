# upload_guides.py (updated)

import json
import os
from pathlib import Path

from google import genai

BASE_DIR = Path(__file__).parent
GUIDES_DIR = BASE_DIR / "guides"
GUIDES_MAP_PATH = BASE_DIR / "guides_map.json"

GUIDE_CONFIG = {
    "fema_are_you_ready": {
        "filename": "fema_are_you_ready.pdf",
        "display_name": "FEMA - Are You Ready? Citizen Preparedness",
    },
    "household_preparedness": {
        "filename": "household_preparedness.pdf",
        "display_name": "Household Emergency Plan",
    },
    "flood_preparedness": {
        "filename": "flood_preparedness.pdf",
        "display_name": "Flood Preparedness Guide",
    },
    "wildfire_preparedness": {
        "filename": "wildfire_preparedness.pdf",
        "display_name": "Wildfire Preparedness Guide",
    },
    "wildfire_toolkit": {
        "filename": "wildfire_toolkit.pdf",
        "display_name": "Emergency Wildfire Preparedness Checklist",
    },
    "earthquake_tsunami_guide": {
        "filename": "earthquake_tsunami_guide.pdf",
        "display_name": "Earthquake & Tsunami Preparedness",
    },
    "winter_storm_guide": {
        "filename": "winter_storm_guide.pdf",
        "display_name": "Winter Storm & Severe Weather Preparedness",
    },
    "canada_power_outage": {
        "filename": "canada_power_outage.pdf",
        "display_name": "Power Outages - Government of Canada",
    },
    "bc_power_outage": {
        "filename": "bc_power_outage.pdf",
        "display_name": "Prepare your home for a power outage (BC Hydro)",
    },
    "ont_power_outage": {
        "filename": "ont_power_outage.pdf",
        "display_name": "Power Outage Safety (Ontario)",
    },
}

def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")

    client = genai.Client(api_key=api_key)

    guides_map: dict[str, dict[str, str]] = {}

    for guide_key, info in GUIDE_CONFIG.items():
        path = GUIDES_DIR / info["filename"]

        if not path.exists():
            print(f"Skipping {guide_key}: file not found at {path}")
            continue

        print(f"Uploading {guide_key} from {path} ...")

        uploaded = client.files.upload(
            file=path,
            config={
                "mime_type": "application/pdf",
                "display_name": info["display_name"],
            },
        )

        guides_map[guide_key] = {
            "file_name": uploaded.name,       
            "file_uri": uploaded.uri,         
            "mime_type": uploaded.mime_type, 
        }

    GUIDES_MAP_PATH.write_text(json.dumps(guides_map, indent=2))
    print(f"Wrote {GUIDES_MAP_PATH} with {len(guides_map)} guides.")


if __name__ == "__main__":
    main()
