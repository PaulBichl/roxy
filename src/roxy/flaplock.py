from time import sleep

from gpiozero import Motor


class FlapLock:
    def __init__(self) -> None:
        self.motor = Motor(forward=6, backward=5)

    def lock(self) -> None:
        """Engage the lock by running the motor forward."""
        self.motor.forward()
        sleep(1)  # Run the motor for 1 second to ensure the lock is engaged
        self.motor.stop()

    def unlock(self) -> None:
        """Disengage the lock by running the motor backward."""
        self.motor.backward()
        sleep(1)  # Run the motor for 1 second to ensure the lock is disengaged
        self.motor.stop()


if __name__ == "__main__":
    choice = input("Enter '1' to lock or '2' to unlock: ")
    lock = FlapLock()
    if choice == "1":
        lock.lock()
        print("The lock is now engaged.")
    elif choice == "2":
        lock.unlock()
        print("The lock is now disengaged.")
    else:
        print("Invalid input. Please enter '1' or '2'.")
