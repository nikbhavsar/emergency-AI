import json
import os
from pathlib import Path

import boto3
from google import genai

BASE_DIR = Path(__file__).parent
GUIDES_DIR = BASE_DIR / "guides"

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
        raise RuntimeError("GEMINI_API_KEY is not set")

    bucket = os.environ.get("S3_GUIDES_BUCKET")
    key = os.environ.get("S3_GUIDES_KEY", "guides/guides_map.json")
    region = os.environ.get("AWS_REGION", "us-west-2")

    if not bucket:
        raise RuntimeError("S3_GUIDES_BUCKET is not set")

    # Gemini & S3 clients
    client = genai.Client(api_key=api_key)
    s3 = boto3.client("s3", region_name=region)

    guides_map: dict[str, dict[str, str]] = {}

    # Upload each PDF to Gemini Files API
    for guide_key, info in GUIDE_CONFIG.items():
        path = GUIDES_DIR / info["filename"]

        if not path.exists():
            print(f"[WARN] Missing file: {path}")
            continue

        print(f"[INFO] Uploading {guide_key} → Gemini...")

        uploaded = client.files.upload(
            file=path,
            config={
                "mime_type": "application/pdf",
                "display_name": info["display_name"],
            },
        )

        guides_map[guide_key] = {
            "display_name": info["display_name"],
            "original_filename": info["filename"],
            "file_name": uploaded.name,
            "file_uri": uploaded.uri,
            "mime_type": uploaded.mime_type,
        }

        print(f"[OK] {guide_key} uploaded as {uploaded.name}")

    # Convert to JSON for S3
    json_body = json.dumps(guides_map, indent=2)

    print(f"[INFO] Uploading guides_map.json to s3://{bucket}/{key}")

    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json_body.encode("utf-8"),
        ContentType="application/json",
    )

    print(f"[DONE] Uploaded guides_map.json with {len(guides_map)} guides.")


if __name__ == "__main__":
    main()
