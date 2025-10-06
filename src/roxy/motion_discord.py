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
# Use a much higher resolution for the saved image
config = picam2.create_still_configuration(main={"size": (1920, 1080)})
picam2.configure(config)
picam2.start()
time.sleep(2)  # allow camera to stabilize

# === STATE VARIABLES ===
last_capture_time = 0
last_brightness = None
last_exposure_change = 0


def send_to_discord(image_path):
    """Send an image to the Discord webhook."""
    with open(image_path, "rb") as f:
        files = {"file": f}
        data = {"content": f"📸 Motion detected at {datetime.now().strftime('%H:%M:%S')}"}
        try:
            requests.post(DISCORD_WEBHOOK, data=data, files=files, timeout=10)
            print("✅ Sent image to Discord")
        except Exception as e:
            print(f"⚠️ Discord upload failed: {e}")


def capture_grayscale_image():
    """Capture, enhance, and save a grayscale image."""
    print("📸 Capturing high-quality image...")
    # Capture a full-resolution color image first
    frame = picam2.capture_array()
    
    # Convert to grayscale for processing
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # === Simplified Enhancement ===
    # 1. (Optional) Use CLAHE for better contrast, especially in mixed lighting.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced_gray = clahe.apply(gray)
    
    # Save the improved grayscale image
    cv2.imwrite(IMAGE_PATH, enhanced_gray)

    # --- For a COLOR image instead, uncomment these lines ---
    # color_filename = "/tmp/motion_color.jpg"
    # cv2.imwrite(color_filename, frame)
    # send_to_discord(color_filename)
    # print(f"✅ Captured + sent COLOR image to Discord")
    # return # Exit early if sending color

    print(f"✅ Captured + enhanced grayscale image at {IMAGE_PATH}")
    send_to_discord(IMAGE_PATH)


def adjust_exposure(gray_frame):
    """Adaptive exposure: auto in bright conditions, manual in low light."""
    global last_brightness, last_exposure_change
    brightness = gray_frame.mean()
    now = time.time()

    if last_brightness is None:
        last_brightness = brightness
        return

    diff = abs(brightness - last_brightness)

    # Re-adjust only if brightness changed significantly
    if diff > 60 and now - last_exposure_change > 15:
        print(f"💡 Adjusting exposure (brightness {brightness:.1f})")
        last_exposure_change = now

        if brightness < 50:  # dark
            picam2.set_controls({
                "AeEnable": False,
                "ExposureTime": 40000,
                "AnalogueGain": 6.0
            })
            print("🌙 Manual low-light mode")
        else:  # bright
            picam2.set_controls({
                "AeEnable": True,
                "AwbEnable": True
            })
            print("☀️ Auto-exposure mode")

        time.sleep(1.5)

    last_brightness = brightness


def detect_motion():
    """Continuously capture frames and detect motion in grayscale."""
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
                capture_grayscale_image()
                last_capture_time = now

        prev_frame = gray
        time.sleep(0.3)


if __name__ == "__main__":
    print("🚀 Motion detector (grayscale, auto exposure) started...")
    detect_motion()
