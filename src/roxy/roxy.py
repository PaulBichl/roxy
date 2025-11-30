#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime

import cv2
import requests
from gpiozero import Motor
from picamera2 import Picamera2  # only works on raspberry pi OS with picamera2 installed
from ultralytics import YOLO

# === CONFIGURATION ===
CONFIG_FILE = "data.json"
config = {
    "discord_webhook": "",
    "conf_threshold": 0.5,
    "verify_duration": 1,
    "notify_cooldown": 2,
    "image_path": "/tmp/motion.jpg",
    "lock_state": "UNLOCKED",
    "lock_override": False,
}

if os.path.exists(CONFIG_FILE):
    try:
        with open(CONFIG_FILE) as f:
            config.update(json.load(f))
    except Exception as e:
        print(f"⚠️ Error reading config: {e}")

# Global values (use lowercase keys from defaults/data.json) TODO refctor
DISCORD_WEBHOOK = config.get("discord_webhook", "")
CONF_THRESHOLD = config.get("conf_threshold", 0.5)
VERIFY_DURATION = config.get("verify_duration", 1)
NOTIFY_COOLDOWN = config.get("notify_cooldown", 2)
IMAGE_PATH = config.get("image_path", "/tmp/motion.jpg")
LOCK_STATE = config.get("lock_state", "UNLOCKED").upper()
LOCK_OVERRIDE = config.get("lock_override", False)

ACTION_DEBOUNCE = 1.0
ACTUATION_DURATION = 0.5
MODEL_SIZE = [640, 640]  # change to IMAGE_SIZE ?
# track current lock state in runtime to avoid redundant motor commands
CURRENT_LOCK_STATE = LOCK_STATE

# track last attempted motor action to debounce attempts
LAST_ACTION_TIME = 0.0

SAFE_CLASSES = ["cat"]
# treat background as a locking condition as requested
PREY_CLASSES = ["cat+prey"]
IGNORED_CLASSES = ["background"]


# === HARDWARE ===
class FlapLock:
    def __init__(self) -> None:
        self.motor = Motor(forward=6, backward=5)
        self.lock_state = ""  # TODO replace with enum
        self.last_action_time = 0.0

    def lock(self) -> None:
        if LOCK_OVERRIDE:
            return
        # avoid redundant locking
        if self.lock_state == "LOCKED":
            # no action required
            return
        self.motor.forward()
        time.sleep(ACTUATION_DURATION)
        self.motor.stop()
        self.lock_state = "LOCKED"
        self.last_action_time = time.time()

    def unlock(self) -> None:
        if LOCK_OVERRIDE:
            return
        # avoid redundant locking
        if self.lock_state == "UNLOCKED":
            # no action required
            return
        self.motor.backward()
        time.sleep(ACTUATION_DURATION)
        self.motor.stop()
        self.lock_state = "UNLOCKED"
        self.last_action_time = time.time()


class Roxy:
    def __init__(self) -> None:
        self.lock = FlapLock()
        self.picam = Picamera2()
        self.model = None
        self._sim = False  # TODO implement

        self.last_notify_time = 0.0
        self.verify_start_time = 0.0  # needed?

        self.discord_webhook = DISCORD_WEBHOOK
        self.lock.lock()

    def initialize_model(self, model_path: str) -> bool:
        try:
            self.model = YOLO(model_path)
            return True
        except Exception:
            print("Failed to load the model")
            return False

    def initialize_camera(self) -> bool:
        try:
            config = self.picam.create_preview_configuration(
                main={"size": MODEL_SIZE, "format": "XBGR8888"},
            )  # i dont understand this, @Isabell pls explain
            self.picam.configure(config)
            self.picam.start()
        except Exception:
            print("Camera Init Failed")
            return False

    def send_to_discord(self, image_path, label="", conf=0.0, is_startup=False) -> None:
        if not self.discord_webhook:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")

        if is_startup:
            msg = f"🚀 **System Online** at {timestamp} | Picamera2 Mode"
        else:
            emoji = "🛑" if label in PREY_CLASSES else "😺"
            msg = f"{emoji} **{label.upper()}** detected | Conf: {conf:.2f} | 🕒 {timestamp}"

        try:
            with open(image_path, "rb") as f:
                files = {"file": f}
                data = {"content": msg}
                requests.post(self.discord_webhook, data=data, files=files, timeout=5)
                print("✅ Discord sent")
        except Exception as e:
            print(f"❌ Discord fail: {e}")

    def capture_frame(self) -> str:  # cursed
        frame_raw = self.picam.capture_array()
        frame = frame_raw[:, :, :3]
        if (frame.shape[1], frame.shape[0]) != MODEL_SIZE:
            frame = cv2.resize(frame, MODEL_SIZE, interpolation=cv2.INTER_LINEAR)
        return frame

    def classify_frame(self, frame) -> tuple[str, float]:
        results = self.model(frame, verbose=False, conf=CONF_THRESHOLD)
        top1_index = results[0].probs.top1
        conf = results[0].probs.top1conf.item()
        label = results[0].names[top1_index]
        return label, conf

    def start_up(self) -> None:
        """
        Perform startup routine to check if all systems are operational.
        """
        self.lock.lock()
        self.lock.unlock()
        dummy_frame = cv2.imread("./test.jpg")
        label, conf = self.classify_frame(dummy_frame)
        self.send_to_discord("./test.jpg", label, conf, is_startup=True)

    def close(self) -> None:
        self.picam.stop()
        # close motor??
        self.lock.motor.close()


if __name__ == "__main__":
    roxy = Roxy()

    roxy.initialize_camera()
    roxy.initialize_model("./tmp/models/model.pt")
    roxy.start_up()
    last_notify_time = time.time()

    while True:
        try:
            frame = roxy.capture_frame()
            label, conf = roxy.classify_frame(frame)
            if (time.time() - last_notify_time) > NOTIFY_COOLDOWN:
                last_notify_time = time.time()
                cv2.imwrite(IMAGE_PATH, frame)
                roxy.send_to_discord(IMAGE_PATH, label, conf)

            if conf >= CONF_THRESHOLD and label in SAFE_CLASSES:
                roxy.lock.unlock()
                time.sleep(30)  # keep unlocked for 30 seconds so cats can get inside
                roxy.lock.lock()

        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            roxy.close()
            break
        except Exception as e:
            print(f"⚠️ Runtime error: {e}")
