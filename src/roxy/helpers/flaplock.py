import time

import gpiozero as gpio


class FlapLock:
    def __init__(self) -> None:
        self.motor = gpio.Motor(forward=6, backward=5)
        self.lock_state = ""
        self.action_duration = 0.5  # time the motor runs to fully lock/unlock

    def lock(self) -> None:
        if self.lock_state == "LOCKED":  # avoid redundant locking
            return
        self.motor.forward()
        time.sleep(self.action_duration)
        self.motor.stop()
        self.lock_state = "LOCKED"

    def unlock(self) -> None:
        if self.lock_state == "UNLOCKED":  # avoid redundant locking
            return
        self.motor.backward()
        time.sleep(self.action_duration)
        self.motor.stop()
        self.lock_state = "UNLOCKED"
