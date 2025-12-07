#!/usr/bin/env python3
import json
import logging
import os
import time
from datetime import datetime

import cv2
import requests
from gpiozero import Motor

try:
    from picamera2 import Picamera2  # no import on non-raspberry pi systems for testing
except ModuleNotFoundError:
    pass
from ultralytics import YOLO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

logging.info("Log entry inside container")
# Global values (use lowercase keys from defaults/data.json) TODO refctor
LOCK_OVERRIDE = False  # for testing without hardware => remove ?
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
        self.lock_state = ""  # TODO replace with enum
        self.last_action_time = 0.0
        self.action_duration = 0.5

    def lock(self) -> None:
        logging.info("Locking flap")
        if LOCK_OVERRIDE:
            return
        # avoid redundant locking
        if self.lock_state == "LOCKED":
            # no action required
            return
        self.motor.forward()
        time.sleep(self.action_duration)
        self.motor.stop()
        self.lock_state = "LOCKED"
        self.last_action_time = time.time()

    def unlock(self) -> None:
        logging.info("Unlocking flap")
        if LOCK_OVERRIDE:
            return
        # avoid redundant locking
        if self.lock_state == "UNLOCKED":
            # no action required
            return
        self.motor.backward()
        time.sleep(self.action_duration)
        self.motor.stop()
        self.lock_state = "UNLOCKED"
        self.last_action_time = time.time()


class Roxy:
    def __init__(self) -> None:
        try:
            self.picam = Picamera2()
            self.lock = FlapLock()
            self.lock.lock()
        except Exception:
            logging.error("hardware initialization failed, if simulating, ignore this.")
        self.model = None
        self._sim = False  # TODO implement

        self.last_notify_time = 0.0
        self.verify_start_time = 0.0  # needed?
        self.notify_cooldown = 10.0  # seconds

        self.discord_webhook = ""

    def config(self, simulate: bool = False, discord_webhook: str = "", conf_threshold: float = 0.5) -> None:
        self._sim = simulate
        self.discord_webhook = discord_webhook
        self.conf_threshold = conf_threshold

    def load_config(self, config_path: str) -> None:
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        # Safely extract with error visibility
        try:
            self.config(
                simulate=cfg["simulate"],
                discord_webhook=cfg["discord_webhook"],
                conf_threshold=cfg["conf_threshold"],
            )
        except KeyError as e:
            missing = str(e).replace("'", "")
            msg = f"Missing required config key: '{missing}' in {config_path}"
            raise Exception(msg) from e

    def initialize_model(self, model_path: str) -> bool:
        logging.info(f"Loading model from {model_path}")
        try:
            if model_path.endswith((".pt", "_ncnn_model")):
                self.model = YOLO(model_path, task="classify")
            else:
                msg = "Unsupported model format"
                raise ValueError(msg)
            return True
        except Exception as e:
            logging.error("Model Init Failed")
            msg = "Model Init Failed"
            raise Exception(msg) from e

    def initialize_camera(self) -> bool:
        try:
            config = self.picam.create_preview_configuration(
                main={"size": MODEL_SIZE, "format": "XBGR8888"},
            )  # i dont understand this, @Isabell pls explain
            self.picam.configure(config)
            self.picam.start()
            logging.info("Camera initialized")
            return True

        except Exception as e:
            logging.error("Camera Init Failed")
            msg = "Camera Init Failed"
            raise Exception(msg) from e

    def send_to_discord(self, image_path: str, label: str, conf: float = 0.0, is_startup: bool = False) -> None:
        if not self.discord_webhook:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")

        if is_startup:
            msg = f"🚀 **System Online** at {timestamp} | Picamera2 Mode"
        else:
            emoji = "🛑" if label in PREY_CLASSES else "😺"
            msg = f"{emoji} **{label.upper()}** detected | Conf: {conf:.2f} | 🕒 {timestamp}"

        if self._sim:
            msg = "[SIMULATION] " + msg
            image_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test.jpg")
        try:
            with open(image_path, "rb") as f:
                files = {"file": f}
                data = {"content": msg}
                requests.post(self.discord_webhook, data=data, files=files, timeout=5)
                logging.info("Discord notification sent")
        except Exception as e:
            logging.error(f"Failed to send Discord notification: {e!s}")
            msg = "Failed to send Discord notification"
            raise Exception(msg) from e

    def capture_frame(self) -> str:  # cursed
        if self._sim:
            module_dir = os.path.dirname(os.path.abspath(__file__))
            img_path = os.path.join(module_dir, "test.jpg")
            return cv2.imread(img_path)
        frame_raw = self.picam.capture_array()
        frame = frame_raw[:, :, :3]
        if (frame.shape[1], frame.shape[0]) != MODEL_SIZE:
            frame = cv2.resize(frame, MODEL_SIZE, interpolation=cv2.INTER_LINEAR)
        return frame

    def classify_frame(self, frame) -> tuple[str, float]:
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
        msg = "startup test"
        data = {"content": msg}
        requests.post(self.discord_webhook, json=data, timeout=5)  # use json=, not data=
        logging.debug("response from discord webhook: {response!s}")
        if not self._sim:
            self.lock.lock()
            self.lock.unlock()
        module_dir = os.path.dirname(os.path.abspath(__file__))
        img_path = os.path.join(module_dir, "test.jpg")
        dummy_frame = cv2.imread(img_path)  # TODO consider os
        label, conf = self.classify_frame(dummy_frame)
        self.send_to_discord(img_path, label, conf, is_startup=True)

    def close(self) -> None:
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
    # roxy.lock.lock()
    last_notify_time = time.time()
    logging.info("Roxy application initialized successfully")
    while True:
        logging.debug("in loop")
        try:
            frame = roxy.capture_frame()
            label, conf = roxy.classify_frame(frame)
            if (time.time() - last_notify_time) > roxy.notify_cooldown:
                last_notify_time = time.time()
                cv2.imwrite(IMAGE_PATH, frame)
                if label not in IGNORED_CLASSES:
                    roxy.send_to_discord(IMAGE_PATH, label, conf)

            if conf >= roxy.conf_threshold and label in SAFE_CLASSES:
                roxy.lock.unlock()
                logging.info("Flap unlocked for safe class")
                time.sleep(30)  # keep unlocked for 30 seconds so cats can get inside
                roxy.lock.lock()

        except KeyboardInterrupt:
            logging.info("Keyboard interrupt received, shutting down.")
            roxy.close()
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e!s}")
            time.sleep(5)
