from __future__ import annotations  # allows us to use type hints of classes that are defined later in the file

GLOBAL_CONSTANT = 3.14  # constant names are uppercase with words separated by underscores


# here are some examples of the PEP 8 code style
def square(x: float) -> float:  # function name is lowercase with words separated by underscores, type hints are used
    # docstring is used to describe the function, not requiered for all functions, classes, use at your own discretion
    """
    Returns the square of a number.
    """
    return x * x


class FloatCalcualtor:  # class name uses CamelCase
    def __init__(self, value: float) -> None:
        self.value = value

    def add(self, other: float) -> float:
        return self.value + other

    def multiply(self, other: float) -> float:
        return self.value * other


def main() -> None:
    num = 5.0
    calculator = FloatCalcualtor(num)
    print(f"Square of {num} is {square(num)}")
    print(f"{num} + 10.0 = {calculator.add(10.0)}")
    print(f"{num} * 2.0 = {calculator.multiply(2.0)}")


if __name__ == "__main__":
    main()
