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

# Global values (use lowercase keys from defaults/data.json)
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


# === HELPERS ===
def send_to_discord(image_path, label="", conf=0.0, is_startup=False) -> None:
    if not DISCORD_WEBHOOK:
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
            requests.post(DISCORD_WEBHOOK, data=data, files=files, timeout=5)
            print("✅ Discord sent")
    except Exception as e:
        print(f"❌ Discord fail: {e}")


def classify_frame(model, frame) -> tuple[str, float]:
    # Run inference directly on the BGR image from Picamera2
    results = model(frame, verbose=False, conf=CONF_THRESHOLD)
    top1_index = results[0].probs.top1
    conf = results[0].probs.top1conf.item()
    label = results[0].names[top1_index]
    return label, conf


# === MAIN ===
def main() -> None:
    print("Loading AI Model...")
    try:
        model = YOLO("./tmp/models/model.pt")
    except Exception:
        print("Failed to load the model")
        return

    lock = FlapLock()
    if lock.lock_state == "UNLOCKED":
        pass
    else:
        lock.lock()

    print("Initializing Picamera2")
    try:
        picam = Picamera2()
        config = picam.create_preview_configuration(main={"size": MODEL_SIZE, "format": "XBGR8888"})
        picam.configure(config)
        picam.start()
    except Exception:
        print("Camera Init Failed")
        return

    print("Camera Active")

    # Startup Notification
    try:
        # Grab first frame
        # capture_array() is INSTANT. No buffer lag.
        frame_raw = picam.capture_array()
        # Drop the Alpha channel (4th channel) to make it standard BGR for OpenCV/YOLO
        frame_bgr = frame_raw[:, :, :3]
        # enforce model input size
        frame_bgr = cv2.resize(frame_bgr, MODEL_SIZE, interpolation=cv2.INTER_LINEAR)

        cv2.imwrite(IMAGE_PATH, frame_bgr)
        send_to_discord(IMAGE_PATH, is_startup=True)
    except Exception as e:
        print(f"⚠️ Startup frame error: {e}")

    last_notify_time = 0

    # State variables for the "Verification Loop"
    verify_start_time = 0

    try:
        while True:
            # 1. Capture Frame (Zero Copy, Zero Latency)
            # This grabs the sensor data directly into RAM
            frame_raw = picam.capture_array()

            # Remove Alpha channel (XBGR -> BGR)
            # YOLO expects 3 channels (Blue, Green, Red)
            frame = frame_raw[:, :, :3]
            # ensure we feed the model a fixed-size image matching MODEL_SIZE
            if (frame.shape[1], frame.shape[0]) != MODEL_SIZE:
                frame = cv2.resize(frame, MODEL_SIZE, interpolation=cv2.INTER_LINEAR)

            current_time = time.time()

            # 2. Run AI
            # We do NOT use sleep() here. We run as fast as the AI can process.
            # This ensures we are always looking at the "now".
            label, conf = classify_frame(model, frame)

            if (current_time - verify_start_time) >= VERIFY_DURATION:
                if label in PREY_CLASSES:
                    if (current_time - last_notify_time) > NOTIFY_COOLDOWN:
                        last_notify_time = current_time
                        cv2.imwrite(IMAGE_PATH, frame)
                        send_to_discord(IMAGE_PATH, label, conf)

                    if conf >= CONF_THRESHOLD:
                        # locking door
                        lock.lock()

                elif label in SAFE_CLASSES:
                    if (current_time - last_notify_time) > NOTIFY_COOLDOWN:
                        last_notify_time = current_time
                        cv2.imwrite(IMAGE_PATH, frame)
                        send_to_discord(IMAGE_PATH, label, conf)

                    if conf >= CONF_THRESHOLD:
                        lock.unlock()

                else:
                    # background detected — ensure locked
                    if (current_time - LAST_ACTION_TIME) > ACTION_DEBOUNCE:
                        lock.lock()

    except KeyboardInterrupt:
        print("\n👋 Exiting...")
    finally:
        picam.stop()
        lock.motor.close()


if __name__ == "__main__":
    main()
