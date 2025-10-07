#!/usr/bin/env python3
import os
import cv2
import numpy as np
import time
import requests
import logging
from datetime import datetime
import argparse

# Try to import Picamera2; allow fallback to cv2.VideoCapture
try:
    from picamera2 import Picamera2
    PICAMERA2_AVAILABLE = True
except Exception:
    PICAMERA2_AVAILABLE = False

from suntime import Sun

# === CONFIGURATION ===
DISCORD_WEBHOOK = os.environ.get(
    "DISCORD_WEBHOOK",
    "https://discord.com/api/webhooks/1424760641645973524/YY--RI5wcTTlJhrG6yptX-bFKo0HwJX-kn-oPTa-ilMZ6B89T16htSNH_7KOshT7Zm-O"
)
MOTION_THRESHOLD = int(os.environ.get("MOTION_THRESHOLD", 40))
PROCESS_WIDTH = int(os.environ.get("PROCESS_WIDTH", 320))
PROCESS_HEIGHT = int(os.environ.get("PROCESS_HEIGHT", 180))
MIN_AREA = int(os.environ.get("MIN_AREA", 750))
CAPTURE_INTERVAL = float(os.environ.get("CAPTURE_INTERVAL", 5.0))
IMAGE_PATH = os.environ.get("IMAGE_PATH", "/tmp/motion.jpg")
SUN_CHECK_INTERVAL = float(os.environ.get("SUN_CHECK_INTERVAL", 600.0))

# NoIR camera flag (IR-sensitive camera)
CAMERA_NOIR = bool(int(os.environ.get("CAMERA_NOIR", "0")))

# Camera full resolution
FULL_RES = (1280, 960)

# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("motion_gemini")

# === CAMERA SETUP ===
picam2 = None
video_capture = None


def initialize_camera():
    """Initialize Picamera2 or fallback to OpenCV VideoCapture."""
    global picam2, video_capture
    if PICAMERA2_AVAILABLE:
        try:
            picam2 = Picamera2()
            config = picam2.create_still_configuration(main={"size": FULL_RES})
            picam2.configure(config)
            picam2.start()
            time.sleep(2)
            logger.info("Picamera2 initialized (full-res %s)", FULL_RES)
            return
        except Exception as e:
            logger.warning("Failed to initialize Picamera2: %s", e)

    video_capture = cv2.VideoCapture(0)
    video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, FULL_RES[0])
    video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, FULL_RES[1])
    if not video_capture.isOpened():
        logger.error("No camera available (Picamera2 unavailable and cv2.VideoCapture failed).")
        raise RuntimeError("Camera initialization failed")
    logger.info("Using cv2.VideoCapture as fallback")


# === Sunlight and Time ===
latitude = float(os.environ.get("LATITUDE", 51.5074))
longitude = float(os.environ.get("LONGITUDE", -0.1278))
try:
    sun_obj = Sun(latitude, longitude)
    sunrise_time = sun_obj.get_sunrise_time().time()
    sunset_time = sun_obj.get_sunset_time().time()
    logger.info("Sunrise at %s, Sunset at %s", sunrise_time, sunset_time)
except Exception as e:
    logger.warning("Initial sun calculation failed: %s", e)
    sunrise_time = None
    sunset_time = None

is_daytime = True
last_sun_check = time.monotonic()


def camera_setup(is_daytime_flag):
    """Configure camera settings depending on time of day."""
    if PICAMERA2_AVAILABLE and picam2 is not None:
        try:
            if is_daytime_flag:
                logger.info("Camera mode: Day")
                if CAMERA_NOIR:
                    # === Brighter daytime settings for NoIR camera ===
                    picam2.set_controls({
                        "AeEnable": True,
                        "ExposureTime": 5000,   # increased from 2000
                        "AnalogueGain": 2.0,    # increased from 1.5
                        "AwbEnable": True
                    })
                else:
                    picam2.set_controls({
                        "AeEnable": True,
                        "ExposureTime": 1000,
                        "AnalogueGain": 1.0,
                        "AwbEnable": True
                    })
            else:
                logger.info("Camera mode: Night")
                if CAMERA_NOIR:
                    picam2.set_controls({
                        "AeEnable": False,
                        "ExposureTime": 20000,
                        "AnalogueGain": 8.0,
                        "AwbEnable": False
                    })
                else:
                    picam2.set_controls({
                        "AeEnable": False,
                        "ExposureTime": 16000,
                        "AnalogueGain": 6.0,
                        "AwbEnable": False
                    })
        except Exception as e:
            logger.debug("Failed to set Picamera2 controls: %s", e)
    else:
        logger.debug("Camera setup skipped (not using Picamera2)")


def send_discord(image_path, webhook=None, message="Motion detected"):
    """Upload an image to Discord via webhook."""
    if webhook is None:
        webhook = DISCORD_WEBHOOK
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
        logger.warning("Discord upload exception: %s", e)


def capture_frame():
    """Return an RGB numpy array for processing."""
    if PICAMERA2_AVAILABLE and picam2 is not None:
        frame = picam2.capture_array()
        return frame
    else:
        ret, frame = video_capture.read()
        if not ret or frame is None:
            raise RuntimeError("Failed to read frame from cv2.VideoCapture")
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def motion_detection_loop():
    """Main motion detection loop."""
    global is_daytime, last_sun_check, sunrise_time, sunset_time

    prev_gray = None
    last_capture_time = 0.0
    scaled_min_area = MIN_AREA
    camera_setup(is_daytime)

    try:
        while True:
            now_monotonic = time.monotonic()

            # Update sunrise/sunset info periodically
            if now_monotonic - last_sun_check > SUN_CHECK_INTERVAL:
                try:
                    sun_obj = Sun(latitude, longitude)
                    sunrise_time = sun_obj.get_sunrise_time().time()
                    sunset_time = sun_obj.get_sunset_time().time()
                    current_time = datetime.now().time()

                    new_is_day = True
                    if sunrise_time and sunset_time:
                        new_is_day = sunrise_time <= current_time <= sunset_time

                    if new_is_day != is_daytime:
                        is_daytime = new_is_day  # <-- fixed: actually update flag
                        camera_setup(is_daytime)
                        logger.info("Mode changed. Daytime: %s", is_daytime)
                except Exception as e:
                    logger.warning("Sun check failed: %s", e)
                last_sun_check = now_monotonic

            # Capture a frame
            try:
                frame = capture_frame()
            except Exception as e:
                logger.warning("Frame capture failed: %s", e)
                time.sleep(0.5)
                continue

            # Resize and grayscale for motion detection
            small = cv2.resize(frame, (PROCESS_WIDTH, PROCESS_HEIGHT), interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, (11, 11), 0)

            if prev_gray is None:
                prev_gray = gray
                time.sleep(0.05)
                continue

            # Detect differences
            delta = cv2.absdiff(prev_gray, gray)
            _, thresh = cv2.threshold(delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=1)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            motion_detected = any(cv2.contourArea(c) >= scaled_min_area for c in contours)

            # On motion, capture image
            if motion_detected and (time.monotonic() - last_capture_time) >= CAPTURE_INTERVAL:
                try:
                    gray_full = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)

                    if CAMERA_NOIR:
                        if not is_daytime:
                            # Night: equalize for contrast
                            gray_full = cv2.equalizeHist(gray_full)
                        else:
                            # === Daytime brightness correction ===
                            mean_brightness = np.mean(gray_full)
                            if mean_brightness < 90:
                                # Apply gamma correction
                                gamma = 1.4
                                inv_gamma = 1.0 / gamma
                                table = np.array([(i / 255.0) ** inv_gamma * 255 for i in np.arange(256)]).astype("uint8")
                                gray_full = cv2.LUT(gray_full, table)
                                # If still too dark, add a gentle linear boost
                                gray_full = cv2.convertScaleAbs(gray_full, alpha=1.2, beta=15)

                    cv2.imwrite(IMAGE_PATH, gray_full)
                    logger.info("Motion detected. Image saved to %s", IMAGE_PATH)
                    send_discord(IMAGE_PATH)

                except Exception as e:
                    logger.warning("Error saving/sending image: %s", e)
                last_capture_time = time.monotonic()

            prev_gray = gray
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
    logger.warning("Discord upload exception: %s", e)