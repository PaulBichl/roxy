#!/usr/bin/env python3
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import cv2
import requests
from gpiozero import Motor

try:
    from picamera2 import Picamera2  # no import on non-raspberry pi systems for testing
except ModuleNotFoundError:
    pass
from ultralytics import YOLO


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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info("Log entry inside container")
# Global values (use lowercase keys from defaults/data.json) TODO refctor
LOCK_OVERRIDE = True  # for testing without engaging hardware => remove ?
MODEL_SIZE = [640, 640]  # change to IMAGE_SIZE ?
IMAGE_PATH = "/tmp/motion.jpg"

SAFE_CLASSES = ["cat"]
# treat background as a locking condition as requested
PREY_CLASSES = ["cat+prey"]
IGNORED_CLASSES = ["background"]


# === HARDWARE ===
class FlapLock:
    """
    class ton control motorized lock for cat flap
    """

    def __init__(self) -> None:
        self.motor = Motor(forward=6, backward=5)
        self.lock_state = ""
        self.action_duration = 0.5  # time the motor runs to fully lock/unlock

    def lock(self) -> None:
        logging.debug("Locking flap")
        if LOCK_OVERRIDE:
            logging.debug("Lock override active, skipping lock action")
            return
        if self.lock_state == "LOCKED":  # avoid redundant locking
            return
        self.motor.forward()
        time.sleep(self.action_duration)
        self.motor.stop()
        self.lock_state = "LOCKED"

    def unlock(self) -> None:
        logging.debug("Unlocking flap")
        if LOCK_OVERRIDE:
            logging.debug("Lock override active, skipping unlock action")
            return
        if self.lock_state == "UNLOCKED":  # avoid redundant locking
            return
        self.motor.backward()
        time.sleep(self.action_duration)
        self.motor.stop()
        self.lock_state = "UNLOCKED"


class Roxy:
    def __init__(self) -> None:
        try:
            self.picam = Picamera2()
            self.lock = FlapLock()
            self.lock.lock()
        except Exception:
            logging.error("hardware initialization failed, if simulating, ignore this.")
        self.model = None
        self._sim = False
        self.notify_cooldown = 1.0  # seconds
        self.discord_webhook = ""

    def config(
        self,
        simulate: bool = False,
        discord_webhook: str = "",
        conf_threshold: float = 0.75,
        lock_override: bool = True,
        lock_state: str = "LOCKED",
    ) -> None:
        """
        lock_state: "LOCKED" or "UNLOCKED" used to set the lock state at start up
        """
        self._sim = simulate
        self.discord_webhook = discord_webhook  # no default webhook possible
        self.conf_threshold = conf_threshold
        global LOCK_OVERRIDE  # noqa: PLW0603
        if not self._sim:
            if lock_override != LOCK_OVERRIDE:  # this should only be engaged after changing the config via webinterface
                LOCK_OVERRIDE = lock_override
            if lock_state == "LOCKED":
                self.lock.lock()
            elif lock_state == "UNLOCKED":
                self.lock.unlock()

    def load_config(self, config_path: str = "./config.json") -> None:
        """
        Extract info from config file and call config(), missing values are set to defaults
        """
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        defaults = {
            "simulate": False,
            "discord_webhook": "",
            "conf_threshold": 0.75,
            "lock_override": True,
            "lock_state": "locked",
        }

        merged = {**defaults, **cfg}
        self.config(**merged)

    def initialize_model(self, model_path: str) -> None:
        """
        loads model from given path
        supports .pt and ncnn models
        """
        logging.info(f"Loading model from {model_path}")
        try:
            if model_path.endswith((".pt", "_ncnn_model")):
                self.model = YOLO(model_path, task="classify")
            else:
                msg = "Unsupported model format"
                raise ValueError(msg)
        except Exception as e:
            logging.error("Model Init Failed")
            msg = "Model Init Failed"
            raise Exception(msg) from e

    def initialize_camera(self) -> None:
        try:
            config = self.picam.create_preview_configuration(
                main={"size": MODEL_SIZE, "format": "XBGR8888"},
            )  # configure camera size and colour format
            self.picam.configure(config)
            self.picam.start()
            logging.info("Camera initialized")
        except Exception as e:
            logging.error("Camera Init Failed")
            msg = "Camera Init Failed"
            raise Exception(msg) from e

    def upload_to_immich(self, image_path: str, label: str = "", conf: float = 0.0) -> None:
        if not IMMICH_API_KEY or not Immich_URL:
            logging.warning("Immich URL or API key not set, skipping upload")
            return

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"roxy_{timestamp}_{label}_{conf:.2f}.jpg" if label else f"roxy_{timestamp}.jpg"
            os.stat(image_path)

            with open(image_path, "rb") as f:
                # 1. Key must be 'assetData'
                files = {"assetData": (filename, f, "image/jpeg")}

                # 2. Add required tracking metadata
                data = {
                    "deviceAssetId": f"roxy-{timestamp}-{filename}",
                    "deviceId": "raspberry-pi-roxy",
                    # Change these lines:
                    "fileCreatedAt": datetime.now().strftime("%H:%M:%S"),
                    "fileModifiedAt": datetime.now().strftime("%H:%M:%S"),
                    "isFavorite": "false",
                    "description": f"Detection: {label} | Confidence: {conf:.2f}" if label else "Roxy capture",
                }

                headers = {"x-api-key": IMMICH_API_KEY, "Accept": "application/json"}

                # 3. Use the /api/assets endpoint
                response = requests.post(
                    f"{Immich_URL.rstrip('/')}/api/assets",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=15,
                )
                response.raise_for_status()
                logging.info(f"Image uploaded to Immich as {filename}")

        except Exception as e:
            logging.error(f"Failed to upload image to Immich: {e!s}")

    def send_to_discord(self, image_path: str, label: str, conf: float = 0.0, is_startup: bool = False) -> None:
        """
        Send notification to discord webhook with image attachment
        if is_startup, send startup message instead of classification
        """
        if not self.discord_webhook:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")

        if is_startup:
            msg = f"start up at {timestamp} | Picamera2 Mode"
        else:
            msg = f"**{label.upper()}** detected | Conf: {conf:.2f} | {timestamp}"

        if self._sim:
            msg = "[SIMULATION] " + msg
            image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.jpg")
        try:
            with open(image_path, "rb") as f:
                files = {"file": f}
                data = {"content": msg}
                requests.post(self.discord_webhook, data=data, files=files, timeout=5)
                logging.debug("Discord notification sent")
        except Exception as e:
            logging.error(f"Failed to send Discord notification: {e!s}")
            msg = "Failed to send Discord notification"
            raise Exception(msg) from e

    def capture_frame(self) -> str:
        """
        Capture frame from camera and prepare for classification, if in sim mode return test image
        """
        if self._sim:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            img_path = os.path.join(module_dir, "test.jpg")
            return cv2.imread(img_path)
        frame_raw = self.picam.capture_array()
        frame = frame_raw[:, :, :3]  # Remove alpha channel if present to get BGR format for better yolo compatibility
        if (frame.shape[1], frame.shape[0]) != MODEL_SIZE:
            frame = cv2.resize(frame, MODEL_SIZE, interpolation=cv2.INTER_LINEAR)
        return frame

    def classify_frame(self, frame) -> tuple[str, float]:
        """
        Classify frame using loaded model
        returns label and confidence
        """
        start_time = time.time()
        results = self.model(frame, verbose=False)
        top1_index = results[0].probs.top1
        conf = results[0].probs.top1conf.item()
        label = results[0].names[top1_index]
        logging.debug(f"Classification: {label} ({conf:.2f}) in {time.time() - start_time:.2f}s")
        return label, conf

    def start_up(self) -> None:
        """
        Perform startup routine to check if all systems are operational.
        """
        if not self._sim:
            self.lock.lock()
            self.lock.unlock()
        module_dir = os.path.dirname(os.path.abspath(__file__))
        img_path = os.path.join(module_dir, "test.jpg")
        dummy_frame = cv2.imread(img_path)
        label, conf = self.classify_frame(dummy_frame)
        self.send_to_discord(img_path, label, conf, is_startup=True)

    def close(self) -> None:
        """
        stops camera and unlocks flap on exit
        """
        logging.info("Closing Roxy application")
        self.picam.stop()
        # close motor??
        self.lock.unlock()  # make suree that lock is open on exit


if __name__ == "__main__":
    logging.info("Starting Roxy application")
    roxy = Roxy()
    roxy.load_config("./config.json")
    roxy.initialize_camera()
    roxy.initialize_model("./tmp/models/model_ncnn_model")
    roxy.start_up()
    roxy.lock.lock()
    last_notify_time = time.time()
    last_unlock_time = time.time()
    unlock_time = 5  # seconds to keep flap unlocked after safe class has been detected
    background_counter = 0
    prey_latched = False
    logging.info("Roxy application initialized successfully")
    while True:
        logging.debug("in loop")
        try:
            frame = roxy.capture_frame()
            label, conf = roxy.classify_frame(frame)

            if label not in IGNORED_CLASSES and (time.time() - last_notify_time) > roxy.notify_cooldown:
                last_notify_time = time.time()
                cv2.imwrite(IMAGE_PATH, frame)
                roxy.send_to_discord(IMAGE_PATH, label, conf)
                roxy.upload_to_immich(IMAGE_PATH, label, conf)
                logging.info(f"Notification sent for {label} with confidence {conf:.2f}")

            # locking logic, default: locked
            if label in PREY_CLASSES and conf >= roxy.conf_threshold:
                roxy.lock.lock()
                prey_latched = True  # Used to prevent model from seeing cat if it comes to close to flap
                logging.info("Flap locked due to prey class detected")

            elif label in IGNORED_CLASSES and conf >= roxy.conf_threshold:
                roxy.lock.lock()

                # Add background counter to avoid issues with misclassification
                background_counter += 1
                if background_counter >= 3:
                    prey_latched = False
                    background_counter = 0

            elif label in SAFE_CLASSES and conf >= roxy.conf_threshold:
                if prey_latched:
                    roxy.lock.lock()

                else:
                    roxy.lock.unlock()
                    last_unlock_time = time.time()
                    logging.info("Safe class detected")

                    # Remain unlocked for unlock_time seconds unless prey is detected
                    while (time.time() - last_unlock_time) < unlock_time:
                        frame = roxy.capture_frame()
                        label, conf = roxy.classify_frame(frame)

                        if label in PREY_CLASSES and conf >= roxy.conf_threshold:
                            roxy.lock.lock()
                            # Save image of the prey that caused the lock
                            cv2.imwrite(IMAGE_PATH, frame)
                            roxy.send_to_discord(IMAGE_PATH, label, conf)
                            roxy.upload_to_immich(IMAGE_PATH, label, conf)
                            prey_latched = True
                            logging.info("Flap re-locked due to prey class detected during unlock period")
                            break  # exit while loop

                        elif label in SAFE_CLASSES and conf >= roxy.conf_threshold:
                            last_unlock_time = time.time()
                            time.sleep(0.1)  # small delay to avoid busy waiting

                        else:
                            time.sleep(0.1)  # small delay to avoid busy waiting

                    roxy.lock.lock()  # go back to default locked state

            else:  # Fail safe for unknown classes, should not happen
                roxy.lock.lock()
                logging.info("Flap locked due to unknown class detected")

        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received, shutting down.")
            roxy.close()
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e!s}")
