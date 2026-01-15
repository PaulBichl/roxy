#!/usr/bin/env python3
import logging
import os
import time

import cv2

from roxy.classes import camera, detection_logic, discord, flaplock, immich, load_config, machine_learning_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info("Log entry inside container")
# Global values (use lowercase keys from defaults/data.json) TODO refctor
MODEL_SIZE = [640, 640]  # change to IMAGE_SIZE ?
IMAGE_PATH = "/tmp/motion.jpg"
UNLOCK_DURATION = 5  # seconds to keep flap unlocked after safe class

SAFE_CLASSES = ["cat"]
# treat background as a locking condition as requested
PREY_CLASSES = ["cat+prey"]
IGNORED_CLASSES = ["background"]


# === HARDWARE ===


class Roxy:
    def __init__(self) -> None:
        self.model = None
        self.notify_cooldown = 1.0  # seconds
        self.discord_webhook = ""
        self.conf_threshold = 0.75
        self.lock_override = True
        self.last_notify_time = 0.0
        self.immich_client = immich.ImmichUploader()
        self.discord_client = discord.Discord()
        self.background_counter = 0
        self.prey_latched = False
        # expose class-level constants for helpers
        self.SAFE_CLASSES = SAFE_CLASSES
        self.PREY_CLASSES = PREY_CLASSES
        self.IGNORED_CLASSES = IGNORED_CLASSES

    def classify_frame(self, frame) -> tuple[str, float]:
        """Proxy classification to the shared ML model."""
        return machine_learning_model.classify_frame(frame)

    def start_up(self) -> None:
        """
        Perform startup routine to check if all systems are operational.
        """
        module_dir = os.path.dirname(os.path.abspath(__file__))
        img_path = os.path.join(module_dir, "test.jpg")
        dummy_frame = cv2.imread(img_path)
        label, conf = self.classify_frame(dummy_frame)
        self.send_picture(img_path, label, conf, is_startup=True)

    def send_picture(self, image_path: str, label: str = "", conf: float = 0.0, is_startup: bool = False) -> None:
        current_time = time.time()
        if (current_time - self.last_notify_time) < self.notify_cooldown:
            logging.debug("Skipping notification due to cooldown")
            return

        self.last_notify_time = current_time

        try:
            self.immich_client.upload_to_immich(image_path, label, conf)
        except Exception as exc:  # log but do not stop notifications
            logging.error("Immich upload failed: %s", exc)

        try:
            self.discord_client.send_to_discord(image_path, label, conf, is_startup=is_startup)
        except Exception as exc:
            logging.error("Discord notification failed: %s", exc)

    def lock(self) -> None:
        if self.lock_override:
            logging.info("Lock override active, skipping lock command")
            return
        flaplock.lock()

    def unlock(self) -> None:
        if self.lock_override:
            logging.info("Lock override active, skipping unlock command")
            return
        flaplock.unlock()


if __name__ == "__main__":
    logging.info("Starting Roxy application")
    roxy = Roxy()
    load_config.Config().load_config(roxy, "./config.json")
    camera.Camera.__init__(roxy)
    camera.Camera.initialize_camera(roxy, MODEL_SIZE)
    machine_learning_model.initialize_model("./tmp/models/model_ncnn_model")

    roxy.start_up()

    logging.info("Roxy application initialized successfully")
    while True:
        logging.debug("in loop")
        try:
            frame = camera.Camera.capture_frame(roxy, MODEL_SIZE)
            label, conf = roxy.classify_frame(frame)
            detection_logic.handle_detection(roxy, label, conf, frame, MODEL_SIZE, IMAGE_PATH, UNLOCK_DURATION)

        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received, shutting down.")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e!s}")
