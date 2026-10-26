"""Bounded fact checks; not a proof of mathematical or semantic equivalence."""

from collections import Counter
import re


def numbers(text: str) -> Counter:
    return Counter(re.findall(r"\d+(?:[.,]\d+)?", text))


def numeric_facts_preserved(source: str, candidate: str) -> bool:
    return numbers(source) == numbers(candidate)
