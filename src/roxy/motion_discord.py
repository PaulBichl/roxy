#!/usr/bin/env python3
import cv2
import numpy as np
import time
import requests
from picamera2 import Picamera2
from datetime import datetime

# === CONFIG ===
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1424760641645973524/YY--RI5wcTTlJhrG6yptX-bFKo0HwJX-kn-oPTa-ilMZ6B89T16htSNH_7KOshT7Zm-O"  # 👈 replace with yours
MOTION_THRESHOLD = 25
MIN_AREA = 500
CAPTURE_INTERVAL = 3  # seconds between motion triggers
IMAGE_PATH = "/tmp/motion.jpg"

# === CAMERA SETUP ===
picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()
time.sleep(2)  # warm-up

# === GLOBAL STATE ===
last_capture_time = 0
last_brightness = None
stable_frames = 0
last_exposure_change = 0


def send_to_discord(image_path):
    """Upload a captured image to the configured Discord webhook."""
    with open(image_path, "rb") as f:
        files = {"file": f}
        data = {"content": f"📸 Motion detected at {datetime.now().strftime('%H:%M:%S')}"}
        try:
            requests.post(DISCORD_WEBHOOK, data=data, files=files, timeout=10)
            print("✅ Sent image to Discord")
        except Exception as e:
            print(f"⚠️ Discord upload failed: {e}")


def capture_image():
    """Capture and save a still image."""
    picam2.capture_file(IMAGE_PATH)
    print(f"📷 Captured {IMAGE_PATH}")
    send_to_discord(IMAGE_PATH)


def adjust_exposure(frame):
    """Hybrid exposure control — automatic in daylight, manual in darkness."""
    global last_brightness, stable_frames, last_exposure_change

    brightness = frame.mean()
    now = time.time()

    if last_brightness is None:
        last_brightness = brightness
        return

    diff = abs(brightness - last_brightness)

    # Only reconsider exposure if lighting changed significantly
    if diff > 60 and now - last_exposure_change > 15:
        print(f"💡 Adjusting exposure (brightness {brightness:.1f})")
        stable_frames = 0
        last_exposure_change = now

        if brightness < 50:  # Dark → manual low-light mode
            picam2.set_controls({
                "AeEnable": False,
                "ExposureTime": 40000,  # 1/25 s
                "AnalogueGain": 6.0
            })
            print("🌙 Manual low-light mode")

        else:  # Normal or bright → auto exposure
            picam2.set_controls({
                "AeEnable": True,
                "AwbEnable": True
            })
            print("☀️ Auto-exposure mode")

        time.sleep(1.5)

    else:
        stable_frames += 1

    last_brightness = brightness


def detect_motion():
    """Main loop: monitor frames for motion and brightness changes."""
    global last_capture_time
    prev_frame = None

    while True:
        frame = picam2.capture_array()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        adjust_exposure(gray)

        if prev_frame is None:
            prev_frame = gray
            continue

        frame_delta = cv2.absdiff(prev_frame, gray)
        thresh = cv2.threshold(frame_delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        motion_detected = any(cv2.contourArea(c) > MIN_AREA for c in contours)

        if motion_detected:
            now = time.time()
            if now - last_capture_time > CAPTURE_INTERVAL:
                capture_image()
                last_capture_time = now

        prev_frame = gray
        time.sleep(0.3)


if __name__ == "__main__":
    print("🚀 Motion detector with auto day/night exposure started...")
    detect_motion()
