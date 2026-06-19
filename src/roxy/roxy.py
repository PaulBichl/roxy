#!/usr/bin/env python3
import logging
import os
import time

import cv2

try:
    from .helpers import (
        camera,
        detection_logic,
        discord,
        flaplock,
        immich,
        load_config,
        machine_learning_model,
    )
except ImportError:
    # fallback when running this file directly
    from helpers import (
        camera,
        detection_logic,
        discord,
        flaplock,
        immich,
        load_config,
        machine_learning_model,
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info("Log entry inside container")
IMAGE_PATH = "/tmp/motion.jpg"
UNLOCK_DURATION = 5  # seconds to keep flap unlocked after safe class

# Support both legacy and new model label names.
SAFE_CLASSES = ["cat", "cat_close", "cat_far", "olivia", "roxy", "uncertain_cat"]
PREY_CLASSES = ["cat+prey", "prey"]
IGNORED_CLASSES = ["background", "uncertain_background"]


# === HARDWARE ===


class Roxy:
    def __init__(self) -> None:
        self.model = None
        self.notify_cooldown = 1.0  # seconds
        self.discord_webhook = ""
        self.conf_threshold = 0.75
        self.lock_override = True
        self.last_notify_time = 0.0
        self.model_size = (320, 320)
        self.main_loop_delay = 0.05
        self.unlock_poll_interval = 0.15
        self.ignored_reset_count = 3
        self.jpeg_quality = 75
        self.opencv_threads = 2
        self.model_path = "./tmp/models/model_ncnn_model"
        self.immich_client = immich.ImmichUploader()
        self.discord_client = discord.Discord()
        self._flaplock = flaplock.FlapLock()
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

    def send_picture(
        self,
        image_path: str,
        label: str = "",
        conf: float = 0.0,
        is_startup: bool = False,
    ) -> None:
        current_time = time.time()
        if (current_time - self.last_notify_time) < self.notify_cooldown:
            logging.debug("Skipping notification due to cooldown")
            return

        self.last_notify_time = current_time

        if not is_startup:
            try:
                self.immich_client.upload_to_immich(image_path, label, conf)
            except Exception as exc:  # log but do not stop notifications
                logging.error("Immich upload failed: %s", exc)
        try:
            self.discord_client.send_to_discord(
                image_path,
                label,
                conf,
                is_startup=is_startup,
            )
        except Exception as exc:
            logging.error("Discord notification failed: %s", exc)

    def lock(self) -> None:
        if self.lock_override:
            # logging.info("Lock override active, skipping lock command")
            return
        self._flaplock.lock()

    def unlock(self) -> None:
        if self.lock_override:
            # logging.info("Lock override active, skipping unlock command")
            return
        self._flaplock.unlock()


if __name__ == "__main__":
    logging.info("Starting Roxy application")
    roxy = Roxy()
    load_config.Config().load_config(roxy, "./config.json")
    cv2.setNumThreads(roxy.opencv_threads)
    camera.Camera.__init__(roxy)
    camera.Camera.initialize_camera(roxy, roxy.model_size)
    machine_learning_model.initialize_model(roxy.model_path)

    roxy.start_up()

    logging.info("Roxy application initialized successfully")
    while True:
        logging.debug("in loop")
        loop_start = time.time()
        try:
            frame = camera.Camera.capture_frame(roxy, roxy.model_size)
            label, conf = roxy.classify_frame(frame)
            detection_logic.handle_detection(
                roxy,
                label,
                conf,
                frame,
                roxy.model_size,
                IMAGE_PATH,
                UNLOCK_DURATION,
            )
        except Exception as e:
            logging.error(f"Error in main loop: {e!s}")

        if roxy.main_loop_delay > 0.0:
            remaining = roxy.main_loop_delay - (time.time() - loop_start)
            if remaining > 0.0:
                time.sleep(remaining)
