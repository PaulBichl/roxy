import logging
import time

import cv2

from roxy.classes import camera


def run_unlock_window(roxy, model_size, image_path, unlock_duration) -> None:
    """Keep flap unlocked for a short window unless prey appears."""
    last_unlock_time = time.time()
    logging.info("Safe class detected")

    while (time.time() - last_unlock_time) < unlock_duration:
        frame = camera.Camera.capture_frame(roxy, model_size)
        label, conf = roxy.classify_frame(frame)

        if conf < roxy.conf_threshold:
            time.sleep(0.1)
            continue

        if label in roxy.PREY_CLASSES:
            roxy.lock()
            cv2.imwrite(image_path, frame)
            roxy.send_picture(image_path, label, conf)
            roxy.prey_latched = True
            logging.info("Flap re-locked due to prey class detected during unlock period")
            break

        if label in roxy.SAFE_CLASSES:
            last_unlock_time = time.time()
            time.sleep(0.1)
            continue

        time.sleep(0.1)

    roxy.lock()


def handle_detection(roxy, label, conf, frame, model_size, image_path, unlock_duration) -> None:
    """Process a single model classification result."""
    if conf < roxy.conf_threshold:
        roxy.lock()
        return

    if label not in roxy.IGNORED_CLASSES:
        cv2.imwrite(image_path, frame)
        roxy.send_picture(image_path, label, conf)
        logging.info("Notification sent for %s with confidence %.2f", label, conf)

    if label in roxy.PREY_CLASSES:
        roxy.lock()
        roxy.prey_latched = True
        logging.info("Flap locked due to prey class detected")
        return

    if label in roxy.IGNORED_CLASSES:
        roxy.lock()
        roxy.background_counter += 1
        if roxy.background_counter >= 3:
            roxy.prey_latched = False
            roxy.background_counter = 0
        return

    if label in roxy.SAFE_CLASSES:
        if roxy.prey_latched:
            roxy.lock()
            return

        roxy.unlock()
        run_unlock_window(roxy, model_size, image_path, unlock_duration)
        return

    roxy.lock()
    logging.info("Flap locked due to unknown class detected")
