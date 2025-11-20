from time import sleep

from gpiozero import Motor

lock_motor = Motor(forward=6, backward=5)


def lock() -> None:
    """Engage the lock by running the motor forward."""
    lock_motor.forward()
    sleep(1)  # Run the motor for 1 second to ensure the lock is engaged
    lock_motor.stop()


def unlock() -> None:
    """Disengage the lock by running the motor backward."""
    lock_motor.backward()
    sleep(1)  # Run the motor for 1 second to ensure the lock is disengaged
    lock_motor.stop()


while True:
    choice = input("Enter '1' to lock or '2' to unlock: ")
    if choice == "1":
        lock()
        print("The lock is now engaged.")
    elif choice == "2":
        unlock()
        print("The lock is now disengaged.")
    else:
        print("Invalid input. Please enter '1' or '2'.")
