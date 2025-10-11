#!/usr/bin/env python3
import cv2
import numpy as np
import time
import requests
from picamera2 import Picamera2
from datetime import datetime, timedelta
import suntime 

# === CONFIGURATION ===
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1424760641645973524/YY--RI5wcTTlJhrG6yptX-bFKo0HwJX-kn-oPTa-ilMZ6B89T16htSNH_7KOshT7Zm-O"  # 👈 replace with yours
MOTION_THRESHOLD = 25
MIN_AREA = 1000
CAPTURE_INTERVAL = 3  # seconds between motion triggers
IMAGE_PATH = "/tmp/motion.jpg"

# === CAMERA SETUP ===
picam2 = Picamera2()
config = picam2.create_still_configuration(main={"size": (1280, 960)})
picam2.configure(config)
picam2.start()
time.sleep(2)  # allow camera to stabilize

#setup sun times
latitude = 55.745833  # replace with your latitude
longitude = 12.331283  # replace with your longitude
sun = suntime.Sun(latitude, longitude)

# === STATE ===
last_frame = None
last_capture_time = 0


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

def changeExposure():
    sunRise = sun.get_sunrise_time().replace(tzinfo=None) 
    sunRise = sunRise + timedelta(hours=2)
    print( "Sunrise is at:", sunRise)
    sunSet = sun.get_sunset_time().replace(tzinfo=None)
    sunSet = sunSet + timedelta(hours=2)
    print( "Sunset is at:", sunSet)
    now = datetime.now()
    mode = "unknown"

    if sunRise < now < sunSet:
        picam2.set_controls({
                        "AeEnable": False,
                        "ExposureTime": 3500,   
                        "AnalogueGain": 1.0,    
                        "AwbEnable": False
                    })
        mode = "day"
        print("Daytime exposure set")

    else:
        picam2.set_controls({
                        "AeEnable": False,
                        "ExposureTime": 30000,   
                        "AnalogueGain": 4.0,    
                        "AwbEnable": False
                    })
        mode = "night"
        print("Nighttime exposure set")
    
    print(f"Current time: {now}, Mode: {mode}")
    

def captureGrayscaleImage():
    """Capture and save a grayscale image."""
    frame = picam2.capture_array()
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    cv2.imwrite(IMAGE_PATH, gray)
    return IMAGE_PATH


# === STARTUP CAPTURE ===
print("📷 Taking startup image...")
#changeExposure()
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

    frame_delta = cv2.absdiff(last_frame, gray)
    thresh = cv2.threshold(frame_delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.dilate(thresh, None, iterations=2)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    motion_detected = False
    for contour in contours:
        if cv2.contourArea(contour) < MIN_AREA:
            continue
        motion_detected = True
        break

    if motion_detected and (time.time() - last_capture_time > CAPTURE_INTERVAL):
     #changeExposure()
        print("⚠️ Motion detected!")
        image_path = captureGrayscaleImage()
        sendToDiscord(image_path)
        last_capture_time = time.time()

    last_frame = gray
    time.sleep(0.5)
