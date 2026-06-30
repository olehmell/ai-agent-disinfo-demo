"""Shared scoring helpers for the eval scripts."""

from __future__ import annotations

import re

CANON_VERDICTS = ["likely_disinformation", "likely_reliable", "mixed", "unverified"]
MANIPULATIVE_VERDICTS = {"likely_disinformation", "mixed"}


def normalize_verdict(text: str) -> str:
    t = (text or "").lower()
    if "disinfo" in t:
        return "likely_disinformation"
    if "reliable" in t:
        return "likely_reliable"
    if "mixed" in t:
        return "mixed"
    return "unverified"


def extract_prediction(out: dict) -> tuple[str, bool]:
    """Return (canonical_verdict, abstention) from any architecture's output."""
    if out.get("final_result") is not None:
        fr = out["final_result"]
        return normalize_verdict(str(fr.get("verdict"))), bool(fr.get("abstention"))
    text = out.get("final_text") or ""
    verdict_match = re.search(r"verdict\s*[:\-]\s*(\w+)", text, re.IGNORECASE)
    verdict = normalize_verdict(verdict_match.group(1) if verdict_match else text)
    abstain_match = re.search(r"abstention\s*[:\-]\s*(true|false|так|ні)", text, re.IGNORECASE)
    abstention = bool(abstain_match) and abstain_match.group(1).lower() in {"true", "так"}
    return verdict, abstention
