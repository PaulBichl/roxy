import logging
import os
from datetime import UTC, datetime
from pathlib import Path

import requests


def _load_secret(env_name: str, fallback_path: str) -> str:
    """Get a value from env, otherwise from a file; return empty string if missing."""
    val = os.getenv(env_name)
    if val:
        return val.strip()
    try:
        return Path(fallback_path).read_text().strip()
    except Exception:
        logging.warning("%s not set and file %s missing", env_name, fallback_path)
        return ""


Immich_URL = _load_secret("IMMICH_URL", "/run/immich_url")
IMMICH_API_KEY = _load_secret("IMMICH_API_KEY", "/run/secrets/immich_api_key")


class ImmichUploader:
    def upload_to_immich(self, image_path: str, label: str = "", conf: float = 0.0) -> None:
        if not IMMICH_API_KEY or not Immich_URL:
            logging.warning("Immich URL or API key not set, skipping upload")
            return

        try:
            # Use a higher resolution timestamp for the ID to ensure uniqueness
            timestamp_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

            filename = f"roxy_{timestamp_iso}_{label}_{conf}.jpg"

            with open(image_path, "rb") as f:
                files = {"assetData": (filename, f, "image/jpeg")}

                # Immich 400 errors usually happen here:
                data = {
                    "deviceAssetId": f"roxy-{timestamp_iso}",  # Must be unique
                    "deviceId": "raspberry-pi-roxy",
                    "fileCreatedAt": timestamp_iso,
                    "fileModifiedAt": timestamp_iso,
                    "isFavorite": "false",
                    "description": f"Detection: {label} ({conf:.2f})" if label else "Roxy capture",
                }

                headers = {"x-api-key": IMMICH_API_KEY, "Accept": "application/json"}

                response = requests.post(
                    f"{Immich_URL.rstrip('/')}/api/assets",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=15,
                )

                # This will print the actual error message from Immich's server
                if response.status_code != 201:
                    logging.error(f"Immich Error Response: {response.text}")

                response.raise_for_status()
                logging.info(f"Image uploaded to Immich as {filename}")

        except Exception as e:
            logging.error(f"Failed to upload image to Immich: {e!s}")
