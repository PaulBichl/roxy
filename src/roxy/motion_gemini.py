#!/usr/bin/env python3
import cv2
import time
import requests
import numpy as np
from datetime import datetime
from picamera2 import Picamera2

# === CONFIGURATION ===
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1424760641645973524/YY--RI5wcTTlJhrG6yptX-bFKo0HwJX-kn-oPTa-ilMZ6B89T16htSNH_7KOshT7Zm-O"
IMAGE_PATH = "/tmp/motion.jpg"
MOTION_THRESHOLD = 35
PIXEL_CHANGE_LIMIT = 3000 # Increased this a bit more for stability
COOLDOWN = 10
DAY_BRIGHTNESS_THRESHOLD = 100

# === CAMERA SETUP ===
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"size": (640, 480)})
picam2.configure(config)
picam2.start()
time.sleep(2)

last_motion_time = 0
prev_frame = None
mask = None
current_mode = None
print("🟢 Robust motion detection started...")

# === HELPER FUNCTIONS ===
def set_camera_mode(frame, current_mode):
    """
    Checks brightness and switches modes. Returns the new mode if changed, otherwise None.
    """
    brightness = np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
    
    # --- DAY MODE ---
    if brightness > DAY_BRIGHTNESS_THRESHOLD:
        if current_mode != "day":
            print("💡 Switching to Day Mode")
            picam2.set_controls({"ExposureTime": 8000, "AnalogueGain": 1.0, "AeEnable": False})
            return "day"
            
    # --- NIGHT MODE ---
    else: # Covers evening and night
        if current_mode != "night":
            print("🌙 Switching to Night Mode")
            picam2.set_controls({"ExposureTime": 50000, "AnalogueGain": 8.0, "AeEnable": False})
            return "night"
    
    return None # No mode change occurred

def create_roi_mask(frame_shape):
    mask = np.zeros(frame_shape, dtype=np.uint8)
    roi_corners = np.array([[(0, 150), (450, 150), (450, 480), (0, 480)]], dtype=np.int32)
    cv2.fillPoly(mask, roi_corners, 255)
    return mask

# (Your enhance_image and send_to_discord functions are fine, no changes needed)
# ...

# === MAIN LOOP ===
while True:
    frame = picam2.capture_array()

    # --- NEW LOGIC TO PREVENT BAD FRAMES ---
    mode_that_was_set = set_camera_mode(frame, current_mode)

    # If the mode was changed, the frame we have is now invalid (taken with old settings)
    if mode_that_was_set:
        print(f"Settings changed to '{mode_that_was_set}', recapturing frame...")
        current_mode = mode_that_was_set
        time.sleep(0.2) # Allow controls to settle
        frame = picam2.capture_array() # Capture a fresh frame with the new settings
        # Reset previous frame to avoid a false motion trigger from the settings change
        prev_frame = None 
    # --- END OF NEW LOGIC ---

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (21, 21), 0)

    if mask is None:
        mask = create_roi_mask(gray.shape)
    gray_masked = cv2.bitwise_and(gray, gray, mask=mask)

    if prev_frame is None:
        # This will now correctly use the recaptured frame after a settings change
        prev_frame = gray_masked
        continue

    frame_delta = cv2.absdiff(prev_frame, gray_masked)
    thresh = cv2.threshold(frame_delta, MOTION_THRESHOLD, 255, cv2.THRESH_BINARY)[1]
    motion_detected = cv2.countNonZero(thresh) > PIXEL_CHANGE_LIMIT

    if motion_detected and (time.time() - last_motion_time > COOLDOWN):
        # ... (Image capture and send logic)
        last_motion_time = time.time()
        
    prev_frame = gray_masked