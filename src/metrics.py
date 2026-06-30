"""Token usage and USD cost estimation for architecture runs.

Collects usage via a LangChain callback (works for workflow nodes when contours pass
``get_config()``) and falls back to ``usage_metadata`` on agent messages.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from .config import GEMINI_MODEL

# USD per 1M tokens — override with GEMINI_INPUT_PRICE_1M / GEMINI_OUTPUT_PRICE_1M.
_DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "gemini-flash-lite-latest": (0.10, 0.40),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
}


@dataclass
class UsageStats:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0

    def merge(self, inp: int, out: int, total: int | None = None) -> None:
        self.input_tokens += inp
        self.output_tokens += out
        self.total_tokens += total if total is not None else (inp + out)
        self.llm_calls += 1

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
        }


def _usage_from_llm_result(response: LLMResult) -> tuple[int, int, int]:
    inp = out = total = 0
    for gen_list in response.generations:
        for gen in gen_list:
            msg = getattr(gen, "message", None)
            if msg is not None and getattr(msg, "usage_metadata", None):
                u = msg.usage_metadata
                inp += int(u.get("input_tokens") or 0)
                out += int(u.get("output_tokens") or 0)
                total += int(u.get("total_tokens") or 0)
    if total == 0 and response.llm_output:
        tu = response.llm_output.get("token_usage") or {}
        inp = int(tu.get("prompt_tokens") or tu.get("input_tokens") or 0)
        out = int(tu.get("completion_tokens") or tu.get("output_tokens") or 0)
        total = int(tu.get("total_tokens") or inp + out)
    return inp, out, total


class UsageCollector(BaseCallbackHandler):
    """Aggregate token usage across every LLM call in one architecture run."""

    def __init__(self) -> None:
        self.stats = UsageStats()

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        inp, out, total = _usage_from_llm_result(response)
        if inp or out or total:
            self.stats.merge(inp, out, total)


def usage_from_messages(messages) -> UsageStats:
    stats = UsageStats()
    for m in messages or []:
        u = getattr(m, "usage_metadata", None)
        if u:
            stats.merge(
                int(u.get("input_tokens") or 0),
                int(u.get("output_tokens") or 0),
                int(u.get("total_tokens") or 0) or None,
            )
    return stats


def _pricing(model: str) -> tuple[float, float]:
    if os.getenv("GEMINI_INPUT_PRICE_1M") and os.getenv("GEMINI_OUTPUT_PRICE_1M"):
        return float(os.environ["GEMINI_INPUT_PRICE_1M"]), float(os.environ["GEMINI_OUTPUT_PRICE_1M"])
    if model in _DEFAULT_PRICING:
        return _DEFAULT_PRICING[model]
    for key, prices in _DEFAULT_PRICING.items():
        if key in model or model in key:
            return prices
    return (0.10, 0.40)


def estimate_cost_usd(input_tokens: int, output_tokens: int, model: str | None = None) -> float:
    in_p, out_p = _pricing(model or GEMINI_MODEL)
    return round((input_tokens * in_p + output_tokens * out_p) / 1_000_000, 6)


def attach_usage_metrics(out: dict, collector: UsageCollector, messages=None) -> None:
    stats = collector.stats
    if stats.llm_calls == 0 and messages:
        stats = usage_from_messages(messages)
    out.update(stats.as_dict())
    out["cost_usd"] = estimate_cost_usd(out["input_tokens"], out["output_tokens"])


def push_langfuse_cost_scores(span, out: dict) -> None:
    """Attach operational + cost scores to the current Langfuse observation."""
    for key in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "cost_usd",
        "latency_s",
        "tool_calls",
        "messages",
        "handoffs",
        "spans",
        "llm_calls",
    ):
        val = out.get(key)
        if val is not None:
            span.score_trace(name=key, value=float(val), data_type="NUMERIC")
