"""Shared test utilities — import directly from any step def file."""
import random


def unique_suffix(length: int = 4) -> str:
    """Return a random numeric string of `length` digits (e.g. '4731').
    Append to any value that must be unique per test run."""
    return str(random.randint(10 ** (length - 1), 10 ** length - 1))
