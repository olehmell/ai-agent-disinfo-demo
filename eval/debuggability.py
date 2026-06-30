"""Debuggability harness — why multi-agent is harder to operate.

Measures three signals on a couple of representative inputs:
  1. Non-determinism: run the same input N times; report verdict + route variance.
  2. Coordination cost: spans, handoffs, repeated tool calls.
  3. Trace depth: distinct agents involved (fan-out) + a nesting-depth proxy.

Workflow is deterministic and flat; the agent versions vary run-to-run and nest deeper.

Usage:
    uv run python eval/debuggability.py
    uv run python eval/debuggability.py --runs 5
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Raise temperature BEFORE importing the package — get_llm caches the model on first use,
# and the multi-agent builds its LLM at import time. A higher temperature surfaces the
# run-to-run drift agents are capable of; the workflow's routing stays deterministic because
# it is code, not a model decision. Override with --temp; parsed manually here, pre-import.
_DEFAULT_TEMP = "0.9"
if "--temp" in sys.argv:
    os.environ["GEMINI_TEMPERATURE"] = sys.argv[sys.argv.index("--temp") + 1]
else:
    os.environ.setdefault("GEMINI_TEMPERATURE", _DEFAULT_TEMP)

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from src.dataset import load_dataset  # noqa: E402
from src.runner import run_architecture  # noqa: E402
from src.scoring import extract_prediction  # noqa: E402

console = Console()

ARCH_ORDER = [("workflow_no_extractor", "workflow"), ("workflow_with_fetch", "workflow_with_fetch"),
              ("single", "single"), ("multi", "multi")]


def _depth_proxy(out: dict) -> int:
    """Approximate Langfuse nesting depth from local signals."""
    arch = out["architecture"]
    if arch.startswith("workflow"):
        return 1  # graph nodes are siblings under one run
    if arch == "single":
        return 2 if out["tool_calls"] else 1  # agent -> tools
    return (2 if out["distinct_agents"] else 1) + (1 if out["tool_calls"] else 0)  # supervisor -> specialist -> tools


def main() -> None:
    parser = argparse.ArgumentParser(description="Debuggability / coordination-cost harness.")
    parser.add_argument("--runs", type=int, default=5, help="repetitions per input for the variance test")
    parser.add_argument("--temp", help="temperature for the variance harness (default 0.9)")
    parser.add_argument("--arch", nargs="+", default=[label for label, _ in ARCH_ORDER])
    args = parser.parse_args()

    selected = [(label, key) for label, key in ARCH_ORDER if label in args.arch]
    # An ambiguous rumor (drift-prone) + an unnormalized item. No network in the variance loop.
    clean = load_dataset("clean")
    hard = load_dataset("hard")
    ambiguous = next((x for x in clean if "ambiguous" in x["id"]), clean[0])
    inputs = [
        ("ambiguous-rumor", ambiguous["content"]),
        ("unnormalized", next(x for x in hard if x["input_type"] == "unnormalized")["content"]),
    ]
    console.print(f"[dim]variance harness temperature = {os.environ['GEMINI_TEMPERATURE']}[/dim]")

    # arch -> aggregated metrics across all runs/inputs
    agg: dict[str, dict] = {
        label: {"verdict_sets": [], "route_sets": [], "spans": [], "handoffs": [],
                "repeat_tools": [], "distinct_agents": [], "depth": []}
        for label, _ in selected
    }

    for in_id, content in inputs:
        console.rule(f"[cyan]{in_id}[/cyan]  ([dim]{args.runs} runs each[/dim])")
        for label, key in selected:
            verdicts, routes = [], []
            for _ in range(args.runs):
                try:
                    out = run_architecture(key, content, f"dbg-{in_id}")
                except Exception as exc:
                    console.print(f"[red]{label} failed: {exc}[/red]")
                    continue
                pred, _ = extract_prediction(out)
                verdicts.append(pred)
                routes.append(out["tool_calls"])  # route signature proxy
                agg[label]["spans"].append(out["spans"])
                agg[label]["handoffs"].append(out["handoffs"])
                agg[label]["repeat_tools"].append(out["repeat_tools"])
                agg[label]["distinct_agents"].append(out["distinct_agents"])
                agg[label]["depth"].append(_depth_proxy(out))
                agg[label].setdefault("cost_usd", []).append(out.get("cost_usd", 0.0))
                agg[label].setdefault("total_tokens", []).append(out.get("total_tokens", 0))
            agg[label]["verdict_sets"].append(len(set(verdicts)))
            agg[label]["route_sets"].append(len(set(routes)))
            console.print(
                f"  [bold]{label:15}[/bold] distinct_verdicts={len(set(verdicts))} "
                f"distinct_routes(tool_calls)={len(set(routes))} {sorted(set(routes))}"
            )

    _print_summary(agg)


def _avg(xs: list) -> float:
    return statistics.mean(xs) if xs else 0.0


def _print_summary(agg: dict[str, dict]) -> None:
    table = Table(title="Table B — debuggability / coordination cost", show_lines=True)
    table.add_column("architecture", style="bold")
    table.add_column("verdict\nvariance", justify="right")
    table.add_column("route\nvariance", justify="right")
    table.add_column("avg\nspans", justify="right")
    table.add_column("avg\nhandoffs", justify="right")
    table.add_column("avg\nrepeat tools", justify="right")
    table.add_column("avg\ndepth", justify="right")
    table.add_column("avg\ncost", justify="right")
    table.add_column("avg\ntokens", justify="right")

    for label, m in agg.items():
        table.add_row(
            label,
            f"{_avg(m['verdict_sets']):.1f}",
            f"{_avg(m['route_sets']):.1f}",
            f"{_avg(m['spans']):.1f}",
            f"{_avg(m['handoffs']):.1f}",
            f"{_avg(m['repeat_tools']):.1f}",
            f"{_avg(m['depth']):.1f}",
            f"${_avg(m.get('cost_usd', [])):.4f}",
            f"{_avg(m.get('total_tokens', [])):.0f}",
        )
    console.print(table)
    console.print(
        "[dim]variance > 1 means the same input took different paths/verdicts across runs — "
        "workflow stays at 1.0 (deterministic), agents drift. spans/handoffs/depth rise "
        "workflow → single → multi: that's the coordination debt you debug in production.[/dim]"
    )


if __name__ == "__main__":
    main()
