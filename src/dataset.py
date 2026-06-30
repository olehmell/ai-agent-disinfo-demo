"""Loaders for the labeled eval datasets under the repo's ``eval/`` directory."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parents[1] / "eval"
DATASETS = {
    "clean": "dataset.jsonl",
    "hard": "hard_dataset.jsonl",
    "euvsdisinfo": "euvsdisinfo_cases.jsonl",  # real EUvsDisinfo debunk cases
}


@cache
def load_dataset(name: str = "clean") -> list[dict]:
    path = EVAL_DIR / DATASETS.get(name, name)
    items: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def get_example(index: int, name: str = "clean") -> dict:
    data = load_dataset(name)
    if not 1 <= index <= len(data):
        raise IndexError(f"example {index} out of range (1..{len(data)})")
    return data[index - 1]
