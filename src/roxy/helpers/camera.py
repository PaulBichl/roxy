import logging

import cv2


class Camera:
    def __init__(self) -> None:
        try:
            from picamera2 import Picamera2  # no import on non-raspberry pi systems for testing

            self.picam = Picamera2()
        except ModuleNotFoundError:
            logging.error("Picamera2 not available; camera not initialized")
            self.picam = None
        except Exception:
            logging.error("hardware initialization failed, if simulating, ignore this.")
            self.picam = None

    def initialize_camera(self, model_size) -> None:
        try:
            if self.picam is None:
                msg = "Camera hardware not available"
                raise RuntimeError(msg)
            config = self.picam.create_preview_configuration(
                main={"size": model_size, "format": "XBGR8888"},
            )  # configure camera size and colour format
            self.picam.configure(config)
            self.picam.start()
            logging.info("Camera initialized")
        except Exception as e:
            logging.error("Camera Init Failed")
            msg = "Camera Init Failed"
            raise Exception(msg) from e

    def capture_frame(self, model_size) -> str:
        """
        Capture frame from camera and prepare for classification, if in sim mode return test image
        """
        if self.picam is None:
            msg = "Camera not initialized"
            raise RuntimeError(msg)
        frame_raw = self.picam.capture_array()
        frame = frame_raw[:, :, :3]  # Remove alpha channel if present to get BGR format for better yolo compatibility
        if (frame.shape[1], frame.shape[0]) != model_size:
            frame = cv2.resize(frame, model_size, interpolation=cv2.INTER_LINEAR)
        return frame
