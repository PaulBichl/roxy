#!/usr/bin/env python3
import cv2
import numpy as np
import time
import requests
from datetime import datetime
from picamera2 import Picamera2

# === CONFIGURATION ===
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1424760641645973524/YY--RI5wcTTlJhrG6yptX-bFKo0HwJX-kn-oPTa-ilMZ6B89T16htSNH_7KOshT7Zm-O"
MOTION_THRESHOLD = 25          # Sensitivity of motion detection
MIN_AREA = 1000                # Ignore small movements
CAPTURE_INTERVAL = 3           # Seconds between motion triggers
RECALIBRATION_INTERVAL = 1800  # Auto recalibration every 30 minutes
IMAGE_PATH = "/tmp/motion.jpg"

# === CAMERA SETUP ===
picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (1280, 960)})
picam2.configure(config)
picam2.start()
time.sleep(2)  # allow camera to stabilize

print("📷 Starting up camera...")

# === STATE ===
last_frame = None
last_capture_time = 0
last_recalibration = time.time()


# === FUNCTIONS ===
def sendToDiscord(image_path, startup=False):
    """Send an image to the Discord webhook."""
    with open(image_path, "rb") as f:
        files = {"file": f}
        label = "📸 Startup image" if startup else f"📸 Motion detected at {datetime.now().strftime('%H:%M:%S')}"
        data = {"content": label}
        try:
            requests.post(DISCORD_WEBHOOK, data=data, files=files, timeout=10)
            print("✅ Image sent to Discord")
        except Exception as e:
            print(f"❌ Discord upload failed: {e}")


def captureGrayscaleImage():
    """Capture and save a grayscale image."""
    frame = picam2.capture_array()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(IMAGE_PATH, gray)
    return IMAGE_PATH


def recalibrateExposure():
    """Re-enable auto exposure briefly, let camera adjust, then lock new settings."""
    print("🔁 Recalibrating exposure...")
    try:
        picam2.set_controls({"AeEnable": True})
        time.sleep(2)  # allow auto-exposure to stabilize
        meta = picam2.capture_metadata()
        print(meta["ExposureTime"])
        picam2.set_controls({
            "AeEnable": False,
            "ExposureTime": meta["ExposureTime"],
            "AnalogueGain": meta["AnalogueGain"]
        })
        if (meta["ExposureTime"] > 10000):
            MOTION_THRESHOLD = 25
            MIN_AREA = 1000
            CAPTURE_INTERVAL = 2  # seconds between motion triggers
        else:
	        MOTION_THRESHOLD = 45
            MIN_AREA = 1000
            CAPTURE_INTERVAL = 3  # seconds between motion triggers
    
        print(f"✅ Exposure locked: {meta['ExposureTime']} μs, Gain {meta['AnalogueGain']:.2f}")
    except Exception as e:
        print(f"⚠️ Exposure recalibration failed: {e}")


# === INITIAL AUTO EXPOSURE LOCK ===
recalibrateExposure()

# === STARTUP CAPTURE ===
print("📸 Sending startup image...")
startup_image = captureGrayscaleImage()
sendToDiscord(startup_image, startup=True)
print("✅ Startup image sent. Starting motion detection...")

# === MAIN LOOP ===
while True:
    frame = picam2.capture_array()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    if last_frame is None:
        last_frame = gray
        continue

    # --- Motion detection ---
    frame_delta = cv2.absdiff(last_frame, gray)
    thresh = cv2.threshold(frame_delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = any(cv2.contourArea(c) >= MIN_AREA for c in contours)

    if motion_detected and (time.time() - last_capture_time > CAPTURE_INTERVAL):
        print("⚠️ Motion detected!")
        image_path = captureGrayscaleImage()
        sendToDiscord(image_path)
        last_capture_time = time.time()

    # --- Periodic exposure recalibration ---
    if time.time() - last_recalibration > RECALIBRATION_INTERVAL:
        recalibrateExposure()
        last_recalibration = time.time()

    last_frame = gray
    time.sleep(0.5)
