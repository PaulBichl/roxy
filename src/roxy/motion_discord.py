#!/usr/bin/env python3
import cv2
import time
import requests
from datetime import datetime
from picamera2 import Picamera2

# === CONFIGURATION ===
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1424760641645973524/YY--RI5wcTTlJhrG6yptX-bFKo0HwJX-kn-oPTa-ilMZ6B89T16htSNH_7KOshT7Zm-O"  # 🔧 replace with your webhook
IMAGE_PATH = "/tmp/motion.jpg"
MOTION_THRESHOLD = 35        # Pixel intensity change threshold
PIXEL_CHANGE_LIMIT = 2500    # Number of changed pixels required
COOLDOWN = 10                # Seconds between detections

# === CAMERA SETUP ===
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()
time.sleep(2)  # allow camera to warm up

# === STATE VARIABLES ===
prev_frame = None
last_motion_time = 0
last_exposure_change = 0
last_brightness = None
stable_frames = 0

print("🟢 Motion detection with smart exposure started...")

# === EXPOSURE CONTROL ===
def adjust_exposure(frame):
    """Smooth exposure control — adjusts only when large brightness change occurs."""
    global last_brightness, stable_frames, last_exposure_change

    brightness = frame.mean()
    now = time.time()

    if last_brightness is None:
        last_brightness = brightness
        return

    diff = abs(brightness - last_brightness)

    # Only adjust if difference is big and at least 15s passed since last change
    if diff > 70 and now - last_exposure_change > 15:
        print(f"💡 Exposure adjust (brightness {brightness:.1f})")
        stable_frames = 0
        last_exposure_change = now

        if brightness < 60:  # Very dark → night mode
            picam2.set_controls({
                "ExposureTime": 60000,  # 1/17s
                "AnalogueGain": 8.0,
                "AeEnable": False
            })
        elif brightness < 120:  # Evening
            picam2.set_controls({
                "ExposureTime": 20000,  # 1/50s
                "AnalogueGain": 3.0,
                "AeEnable": False
            })
        else:  # Bright daylight
            picam2.set_controls({
                "ExposureTime": 2000,   # 1/500s
                "AnalogueGain": 1.0,
                "AeEnable": False
            })

        print("⏳ Waiting 2s for exposure to stabilize...")
        time.sleep(2)
    else:
        stable_frames += 1

    last_brightness = brightness

# === IMAGE ENHANCEMENT ===
def enhance_image(image):
    """Improves brightness and contrast for clarity."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.convertScaleAbs(gray, alpha=1.8, beta=25)
    return enhanced

# === DISCORD UPLOAD ===
def send_to_discord(image_path):
    """Send image via Discord webhook."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(image_path, "rb") as f:
            requests.post(
                DISCORD_WEBHOOK_URL,
                files={"file": f},
                data={"content": f"📸 Motion detected at {now}"}
            )
        print("📤 Image sent to Discord.")
    except Exception as e:
        print("❌ Failed to send image:", e)

# === MAIN LOOP ===
while True:
    frame = picam2.capture_array()
    adjust_exposure(frame)

    # Wait until exposure stabilizes
    if stable_frames < 5:
        time.sleep(0.5)
        continue

    # Motion detection
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    if prev_frame is None:
        prev_frame = gray
        continue

    frame_delta = cv2.absdiff(prev_frame, gray)
    thresh = cv2.threshold(frame_delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    motion_pixels = cv2.countNonZero(thresh)
    motion_detected = motion_pixels > PIXEL_CHANGE_LIMIT

    if motion_detected and (time.time() - last_motion_time > COOLDOWN):
        print(f"⚠️ Motion detected! ({motion_pixels} px changed)")
        img = enhance_image(frame)
        cv2.imwrite(IMAGE_PATH, img)
        send_to_discord(IMAGE_PATH)
        last_motion_time = time.time()

    prev_frame = gray
    time.sleep(1)
