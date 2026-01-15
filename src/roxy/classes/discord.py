import datetime
import logging
import os
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


Discord_Webhook = _load_secret("discord_webhook", "/run/secrets/discord_webhook")


class Discord:
    def send_to_discord(self, image_path: str, label: str, conf: float = 0.0, is_startup: bool = False) -> None:
        """
        Send notification to discord webhook with image attachment
        if is_startup, send startup message instead of classification
        """
        if not Discord_Webhook:
            return
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        if is_startup:
            msg = f"start up at {timestamp} | Picamera2 Mode"
        else:
            msg = f"**{label.upper()}** detected | Conf: {conf:.2f} | {timestamp}"

        try:
            with open(image_path, "rb") as f:
                files = {"file": f}
                data = {"content": msg}
                requests.post(Discord_Webhook, data=data, files=files, timeout=5)
                logging.debug("Discord notification sent")
        except Exception as e:
            logging.error(f"Failed to send Discord notification: {e!s}")
            msg = "Failed to send Discord notification"
            raise Exception(msg) from e
