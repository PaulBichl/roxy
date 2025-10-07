#!/usr/bin/env python3
import os
import cv2
import numpy as np
import time
import requests
import logging
from datetime import datetime
import argparse

# Try to import Picamera2; allow fallback to cv2.VideoCapture for testing/dev
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except Exception:
    PICAMERA2_AVAILABLE = False

import suntime as sun

# === CONFIGURATION (env overrides) ===
DISCORD_WEBHOOK = os.environ.get(
    "DISCORD_WEBHOOK",
    "https://discord.com/api/webhooks/1424760641645973524/YY--RI5wcTTlJhrG6yptX-bFKo0HwJX-kn-oPTa-ilMZ6B89T16htSNH_7KOshT7Zm-O"
)
MOTION_THRESHOLD = int(os.environ.get("MOTION_THRESHOLD", 40))
PROCESS_WIDTH = int(os.environ.get("PROCESS_WIDTH", 320))
PROCESS_HEIGHT = int(os.environ.get("PROCESS_HEIGHT", 180))
MIN_AREA = int(os.environ.get("MIN_AREA", 750))  # minimum changed pixels in the downscaled frame
CAPTURE_INTERVAL = float(os.environ.get("CAPTURE_INTERVAL", 5.0))
IMAGE_PATH = os.environ.get("IMAGE_PATH", "/tmp/motion.jpg")
SUN_CHECK_INTERVAL = float(os.environ.get("SUN_CHECK_INTERVAL", 600.0))  # seconds

# New: set to "1" to indicate NoIR / IR-capable camera module
CAMERA_NOIR = os.environ.get("CAMERA_NOIR", "0") == "1"

# Camera still size (full-res)
FULL_RES = (640, 480)   

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("motion_gemini")

# === CAMERA SETUP (SINGLE STREAM) ===
picam2 = None
video_capture = None

def initialize_camera():
    global picam2, video_capture
    if PICAMERA2_AVAILABLE:
        try:
            picam2 = Picamera2()
            config = picam2.create_still_configuration(main={"size": FULL_RES})
            picam2.configure(config)
            picam2.start()
            time.sleep(2)  # Allow camera to stabilize
            logger.info("Picamera2 initialized (full-res %s)", FULL_RES)
            return
        except Exception as e:
            logger.warning("Failed to initialize Picamera2: %s", e)

    # Fallback to OpenCV VideoCapture (0)
    video_capture = cv2.VideoCapture(0)
    # Try to set resolution
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, FULL_RES[0])
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FULL_RES[1])
    if not video_capture.isOpened():
        logger.error("No camera available (Picamera2 unavailable and cv2.VideoCapture failed).")
        raise RuntimeError("Camera initialization failed")
    logger.info("Using cv2.VideoCapture as fallback")

# === Sun Up or Down ===
latitude = float(os.environ.get("LATITUDE", 51.5074))
longitude = float(os.environ.get("LONGITUDE", -0.1278))
try:
    sunrise_sunset = sun.sun(latitude, longitude)
    sunrise_time = sunrise_sunset['sunrise'].time()
    sunset_time = sunrise_sunset['sunset'].time()
    logger.info("Sunrise at %s, Sunset at %s", sunrise_time, sunset_time)
except Exception as e:
    logger.warning("Initial sun calculation failed: %s", e)
    sunrise_time = None
    sunset_time = None

is_daytime = True  # initial assumption; updated in loop
last_sun_check = time.monotonic()

def Camera_setup(is_daytime_flag):
    """Sets up the camera controls depending on day/night. No-op if using cv2 fallback."""
    if PICAMERA2_AVAILABLE and picam2 is not None:
        try:
            if is_daytime_flag:
                logger.info("Camera mode: Day")
                # Day settings: keep AWB on for color cameras; for NoIR daytime AWB usually OK
                if CAMERA_NOIR:
                    # NoIR in daylight - keep AWB but reduce exposure/gain
                    picam2.set_controls({
                        "AeEnable": True, "ExposureTime": 2000, "AnalogueGain": 1.5, "AwbEnable": True
                    })
                else:
                    picam2.set_controls({
                        "AeEnable": True, "ExposureTime": 1000, "AnalogueGain": 1.0, "AwbEnable": True
                    })
            else:
                logger.info("Camera mode: Night")
                # Night settings: disable AWB for IR and increase exposure/gain
                if CAMERA_NOIR:
                    picam2.set_controls({
                        "AeEnable": False, "ExposureTime": 20000, "AnalogueGain": 8.0, "AwbEnable": False
                    })
                else:
                    picam2.set_controls({
                        "AeEnable": False, "ExposureTime": 16000, "AnalogueGain": 6.0, "AwbEnable": False
                    })
        except Exception as e:
            logger.debug("Failed to set Picamera2 controls: %s", e)
    else:
        logger.debug("Camera setup skipped (not using Picamera2)")

def send_discord(image_path, webhook=DISCORD_WEBHOOK, message="Motion detected"):
    if not webhook:
        logger.debug("No webhook configured; skipping Discord upload")
        return
    try:
        with open(image_path, "rb") as f:
            r = requests.post(webhook, data={"content": message}, files={"file": f}, timeout=15)
            if r.status_code >= 400:
                logger.warning("Discord upload failed: %s %s", r.status_code, r.text)
            else:
                logger.info("Uploaded image to Discord")
    except Exception as e:
        logger.warning("Discord upload failed: %s", e)

def capture_frame():
    """
    Return an RGB numpy array for processing.
    Uses Picamera2 if available, else cv2.VideoCapture.
    """
    if PICAMERA2_AVAILABLE and picam2 is not None:
        frame = picam2.capture_array()
        # picamera2 returns RGB by default
        return frame
    else:
        ret, frame = video_capture.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to read frame from cv2.VideoCapture")
        # cv2 returns BGR; convert to RGB for consistency
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

def motion_detection_loop():
    """
    Lightweight motion detection loop suitable for Pi Zero W2.
    """
    global is_daytime, last_sun_check, sunrise_time, sunset_time

    prev_gray = None
    last_capture_time = 0.0

    # Scale MIN_AREA according to processing resolution ratio relative to full res if needed
    # (keep MIN_AREA as pixels on the processing size)
    scaled_min_area = MIN_AREA

    Camera_setup(is_daytime)

    try:
        while True:
            now_monotonic = time.monotonic()
            # Update sun times periodically
            if now_monotonic - last_sun_check > SUN_CHECK_INTERVAL:
                try:
                    sunrise_sunset = sun.sun(latitude, longitude)
                    sunrise_time = sunrise_sunset['sunrise'].time()
                    sunset_time = sunrise_sunset['sunset'].time()
                    current_time = datetime.now().time()
                    new_is_day = True
                    if sunrise_time is not None and sunset_time is not None:
                        new_is_day = sunrise_time <= current_time <= sunset_time
                    if new_is_day != is_daytime:
                        is_daytime = new_is_day
                        Camera_setup(is_daytime)
                        logger.info("Mode changed. Daytime: %s", is_daytime)
                except Exception as e:
                    logger.warning("Sun check failed: %s", e)
                last_sun_check = now_monotonic

            # Capture a frame (returns RGB array)
            try:
                frame = capture_frame()
            except Exception as e:
                logger.warning("Frame capture failed: %s", e)
                time.sleep(0.5)
                continue

            # Resize for processing to reduce CPU usage on Pi Zero W2
            small = cv2.resize(frame, (PROCESS_WIDTH, PROCESS_HEIGHT), interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
            # Use a smaller blur kernel to reduce CPU while still smoothing noise
            gray = cv2.GaussianBlur(gray, (11, 11), 0)

            if prev_gray is None:
                prev_gray = gray
                time.sleep(0.05)
                continue

            # Frame differencing
            delta = cv2.absdiff(prev_gray, gray)
            _, thresh = cv2.threshold(delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=1)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            motion_detected = False
            for c in contours:
                if cv2.contourArea(c) >= scaled_min_area:
                    motion_detected = True
                    break

            if motion_detected and (time.monotonic() - last_capture_time) >= CAPTURE_INTERVAL:
                try:
                    # Convert full-res RGB to grayscale and save.
                    # For IR (NoIR) nighttime captures apply histogram equalization to improve contrast.
                    gray_full = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                    if CAMERA_NOIR and not is_daytime:
                        try:
                            gray_full = cv2.equalizeHist(gray_full)
                        except Exception:
                            # If equalizeHist fails, continue with raw gray image
                            pass
                    cv2.imwrite(IMAGE_PATH, gray_full)
                    logger.info("Motion detected. Grayscale image saved to %s", IMAGE_PATH)
                    send_discord(IMAGE_PATH)
                except Exception as e:
                    logger.warning("Error saving/sending image: %s", e)
                last_capture_time = time.monotonic()

            prev_gray = gray
            # Short sleep to yield CPU on Pi Zero W2
            time.sleep(0.08)

    except KeyboardInterrupt:
        logger.info("Stopping motion detection (KeyboardInterrupt).")
    except Exception as e:
        logger.exception("Unexpected error in motion_detection_loop: %s", e)
    finally:
        try:
            if PICAMERA2_AVAILABLE and picam2 is not None:
                picam2.stop()
        except Exception:
            pass
        try:
            if video_capture is not None:
                video_capture.release()
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Pi Zero W2 motion detector")
    parser.add_argument("--no-discord", action="store_true", help="Disable Discord uploads")
    args = parser.parse_args()
    if args.no_discord:
        global DISCORD_WEBHOOK
        DISCORD_WEBHOOK = ""
        logger.info("Discord uploads disabled via --no-discord")

    initialize_camera()
    motion_detection_loop()

if __name__ == "__main__":
    main()

