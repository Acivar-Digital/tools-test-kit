"""Mutation-testing target + tests that kill mutants.

The stub function and the focused tests below pin exact boundary behavior, so a
mutation testing tool (e.g. mutmut) that flips a `<` to `<=`, a `+` to `-`, or a
`*0.07` to `*0.0` is killed by at least one assertion.

One dependency only: pytest.
"""
from __future__ import annotations


def grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "F"


def add_tax(amount: float) -> float:
    return amount + amount * 0.07


def test_grading_boundaries() -> None:
    assert grade(90) == "A"
    assert grade(89.9) == "B"
    assert grade(70) == "B"
    assert grade(69.9) == "C"
    assert grade(50) == "C"
    assert grade(49.9) == "F"


def test_tax_is_seven_percent() -> None:
    assert add_tax(100.0) == 107.0
    assert add_tax(0.0) == 0.0
    assert add_tax(10.0) == 10.7


if __name__ == "__main__":
    assert grade(90) == "A"
    assert add_tax(100.0) == 107.0
    print("03_mutation_target OK")
