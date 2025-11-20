#!/usr/bin/env python3
import json
import subprocess
import time
from datetime import datetime

import cv2
import requests
from ultralytics import YOLO

from .flaplock import FlapLock

try:
    model = YOLO("./tmp/models/model.pt")  # use .pt for now, TODO switch to ncnn
except Exception as e:
    print(f"❌ Failed to load model: {e}")

# === CONFIGURATION ===
lock = FlapLock()
lock.lock()

json_data = {}
with open("data.json") as data:
    json_data = json.load(data)
    DISCORD_WEBHOOK = json_data.get("discord_webhook", "")

# --- Fine-tune these values for your environment ---
MOTION_THRESHOLD = json_data.get(
    "MOTION_THRESHOLD",
    50,
)  # How much a pixel needs to change to be considered motion (1-255). Lower is more sensitive.
MIN_AREA = json_data.get("MIN_AREA", 10000)  # The minimum size (in pixels) of a moving object to trigger an alert.
CAPTURE_INTERVAL = json_data.get("CAPTURE_INTERVAL", 3)  # Seconds between motion trigger notifications.
ALPHA = json_data.get(
    "ALPHA",
    0.02,
)  # How quickly the background model adapts to slow changes (like sunrise). (0.01-0.1 is a good range)

# --- System Paths ---
IMAGE_PATH = json_data.get("IMAGE_PATH", "/tmp/motion.jpg")  # noqa: S108 TODO fix this, change to tmp/motion.jpg on windows

# === STATE ===
background_model = None
last_capture_time = 0

print("📷 Initializing motion detection script for Day & Night...")


# === FUNCTIONS ===
def send_to_discord(image_path, image_label="", startup=False) -> None:
    """Send an image to the Discord webhook."""
    with open(image_path, "rb") as f:
        files = {"file": f}
        label = (
            f"🚀 Startup image, {datetime.now().strftime('%H:%M:%S')}, class dedected: {image_label}"
            if startup
            else f"🚨 Motion detected at {datetime.now().strftime('%H:%M:%S')}, class dedected: {image_label}"
        )
        data = {"content": label}
        try:
            requests.post(DISCORD_WEBHOOK, data=data, files=files, timeout=10)
            print("✅ Image sent to Discord")
        except Exception as e:
            print(f"❌ Discord upload failed: {e}")


def capture_frame() -> cv2.Mat | None:
    """
    Captures a frame using rpicam-still, allowing auto-exposure to adapt
    to day/night conditions while giving it time to stabilize.
    """
    try:
        command = [
            "rpicam-still",
            "-o",
            IMAGE_PATH,
            "--width",
            "640",
            "--height",
            "640",
            # CRITICAL: Give the camera 1 second (1000ms) for its auto-exposure
            # and auto-white-balance algorithms to settle before taking the picture.
            # This prevents false alarms from rapid auto-adjustments.
            "-t",
            "1000",
            "--nopreview",
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603 subprocess call is safe here, bandit false positive, consider reviewing
        frame = cv2.imread(IMAGE_PATH)
        if frame is None:
            print("❌ Failed to read image from disk after capture.")
            return None
        return frame
    except subprocess.CalledProcessError as e:
        print(f"❌ rpicam-still command failed: {e.stderr}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred during capture: {e}")
        return None


def classify_image(image_path) -> str:
    """
    function which uses trained ML model to classify image
    and returns the label as string
    """
    cv2.imread(image_path)
    results = model(image_path)
    return results[0].names[results[0].probs.top1]


# === INITIALIZE BACKGROUND MODEL ===
print("📸 Capturing startup image to establish background...")
# A longer sleep on startup ensures the very first frame is well-exposed.
time.sleep(3)
initial_frame = capture_frame()

if initial_frame is not None:
    send_to_discord(IMAGE_PATH, classify_image(IMAGE_PATH), startup=True)
    # FIX: Corrected typo to cv2.COLOR_BGR2GRAY
    gray = cv2.cvtColor(initial_frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)
    background_model = gray.astype("float")
    print("✅ Background model established. Starting motion detection...")
else:
    print("❌ Could not capture startup image. Exiting.")
    exit()

# === MAIN LOOP === TODO replace with main
while True:
    frame = capture_frame()

    if frame is None:
        print("⚠️ Skipping frame due to capture error.")
        time.sleep(2)
        continue

    # FIX: Corrected typo to cv2.COLOR_BGR2GRAY
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    # FIX: Convert the current frame to a float to match the background_model's data type.
    current_frame_float = gray.astype("float")

    # Update the background model slowly over time using the float version of the frame
    cv2.addWeighted(current_frame_float, ALPHA, background_model, 1 - ALPHA, 0, background_model)

    # Compare the original uint8 gray frame to the stable background model
    frame_delta = cv2.absdiff(gray, cv2.convertScaleAbs(background_model))
    thresh = cv2.threshold(frame_delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = any(cv2.contourArea(c) >= MIN_AREA for c in contours)

    if motion_detected and (time.time() - last_capture_time > CAPTURE_INTERVAL):
        print(f"⚠️ Motion detected at {datetime.now().strftime('%H:%M:%S')}!")
        dedected_label = classify_image(IMAGE_PATH)

        if dedected_label == "cat":
            print("🔓 Cat detected, unlocking flap...")
            lock.unlock()
            send_to_discord(IMAGE_PATH, dedected_label)
            time.sleep(30)
            lock.lock()
        else:
            send_to_discord(IMAGE_PATH, dedected_label)
        last_capture_time = time.time()  #!/usr/bin/env python3
