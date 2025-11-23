import json
import os
from pathlib import Path
from google import genai

BASE_DIR = Path(__file__).parent
GUIDES_MAP_PATH = BASE_DIR / "guides_map.json"


def format_bytes(size):
    if size is None:
        return "unknown"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    if not GUIDES_MAP_PATH.exists():
        print("guides_map.json not found! Run your upload script first.")
        return

    guides_map = json.loads(GUIDES_MAP_PATH.read_text())
    client = genai.Client(api_key=api_key)

    print("Listing uploaded guides:")
    print("=" * 60)

    for guide_key, info in guides_map.items():
        file_id = info.get("file_name")

        print(f"{guide_key} -> {file_id}")

        try:
            file_obj = client.files.get(name=file_id)
        except Exception as e:
            print(f"Could not fetch file: {e}")
            print("-" * 60)
            continue

        display_name = getattr(file_obj, "display_name", None)
        mime_type = getattr(file_obj, "mime_type", None)
        create_time = getattr(file_obj, "create_time", None)
        size_bytes = getattr(file_obj, "size_bytes", None)
        state = getattr(file_obj, "state", None)

        print(f"Display Name: {display_name}")
        print(f"MIME Type:    {mime_type}")
        print(f"Size:         {format_bytes(size_bytes)}")
        print(f"Created:      {create_time}")
        print(f"State:        {state}")

        if state != "ACTIVE":
            print("WARNING: File is not active (may be expired).")

        print("-" * 60)

    print("Done!")


if __name__ == "__main__":
    main()
