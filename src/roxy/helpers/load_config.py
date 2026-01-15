import json


class Config:
    def config(
        self,
        target,
        conf_threshold: float = 0.75,
        lock_override: bool = True,
        lock_state: str = "LOCKED",
    ) -> None:
        """Apply configuration values to a target instance.

        The target is expected to expose ``lock``/``unlock`` methods.
        """

        target.conf_threshold = conf_threshold
        target.lock_override = lock_override

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
            "lock_state": "LOCKED",
        }

        merged = {**defaults, **cfg}
        self.config(target=target, **merged)
