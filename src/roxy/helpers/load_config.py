import json


class Config:
    @staticmethod
    def _normalize_model_size(model_size) -> tuple[int, int]:
        """Normalize model size from config into (width, height)."""
        if isinstance(model_size, int):
            if model_size <= 0:
                msg = "model_size must be positive"
                raise ValueError(msg)
            return (model_size, model_size)

        if isinstance(model_size, list | tuple) and len(model_size) == 2:
            width = int(model_size[0])
            height = int(model_size[1])
            if width <= 0 or height <= 0:
                msg = "model_size values must be positive"
                raise ValueError(msg)
            return (width, height)

        msg = "model_size must be an int or [width, height]"
        raise ValueError(msg)

    def config(
        self,
        target,
        conf_threshold: float = 0.75,
        lock_override: bool = True,
        lock_state: str = "UNLOCKED",
        model_size=(320, 320),
        main_loop_delay: float = 0.05,
        unlock_poll_interval: float = 0.15,
        ignored_reset_count: int = 3,
        jpeg_quality: int = 75,
        opencv_threads: int = 2,
        model_path: str = "./tmp/models/model_ncnn_model",
    ) -> None:
        """Apply configuration values to a target instance.

        The target is expected to expose ``lock``/``unlock`` methods.
        """

        target.conf_threshold = conf_threshold
        target.lock_override = lock_override
        target.model_size = self._normalize_model_size(model_size)
        target.main_loop_delay = max(0.0, float(main_loop_delay))
        target.unlock_poll_interval = max(0.01, float(unlock_poll_interval))
        target.ignored_reset_count = max(1, int(ignored_reset_count))
        target.jpeg_quality = min(100, max(30, int(jpeg_quality)))
        target.opencv_threads = max(0, int(opencv_threads))
        target.model_path = str(model_path)

        if lock_state.upper() == "LOCKED":
            target.lock()
        elif lock_state.upper() == "UNLOCKED":
            target.unlock()

    def load_config(self, target, config_path: str = "./config.json") -> None:
        """Extract info from config file and call ``config``.

        Missing values fall back to sensible defaults.
        """
        with open(config_path, encoding="utf-8") as f:
            cfg = json.load(f)

        defaults = {
            "conf_threshold": 0.75,
            "lock_override": True,
            "lock_state": "UNLOCKED",
            "model_size": [320, 320],
            "main_loop_delay": 0.05,
            "unlock_poll_interval": 0.15,
            "ignored_reset_count": 3,
            "jpeg_quality": 75,
            "opencv_threads": 2,
            "model_path": "./tmp/models/model_ncnn_model",
        }

        merged = {**defaults, **cfg}
        self.config(target=target, **merged)
