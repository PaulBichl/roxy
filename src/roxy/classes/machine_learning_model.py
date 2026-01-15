import logging
import time

from ultralytics import YOLO


class MachineLearningModel:
    def __init__(self) -> None:
        self.model = None

    def initialize_model(self, model_path: str) -> None:
        """Load a classification model from the given path."""
        logging.info(f"Loading model from {model_path}")
        try:
            if model_path.endswith((".pt", "_ncnn_model")):
                self.model = YOLO(model_path, task="classify")
            else:
                msg = "Unsupported model format"
                raise ValueError(msg)
        except Exception as e:
            logging.error("Model Init Failed")
            msg = "Model Init Failed"
            raise Exception(msg) from e

    def classify_frame(self, frame) -> tuple[str, float]:
        """Classify a frame using the loaded model."""
        start_time = time.time()
        results = self.model(frame, verbose=False)
        top1_index = results[0].probs.top1
        conf = results[0].probs.top1conf.item()
        label = results[0].names[top1_index]
        logging.debug("Classification: %s (%.2f) in %.2fs", label, conf, time.time() - start_time)
        return label, conf


_MODEL = MachineLearningModel()


def initialize_model(model_path: str) -> None:
    """Module-level helper to mirror previous API surface."""
    _MODEL.initialize_model(model_path)


def classify_frame(frame) -> tuple[str, float]:
    """Classify frame using the shared model instance."""
    return _MODEL.classify_frame(frame)
