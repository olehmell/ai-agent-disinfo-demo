"""Contrastive eval — where the deterministic workflow breaks.

Runs the hard dataset (URLs / YouTube / unnormalized inputs) through:
  workflow_no_extractor | workflow_with_fetch | single | multi
and shows that the broken workflow never resolves the real content — it screens the raw
URL and returns a plausible-but-wrong answer ("fake success"), while the fixed workflow
and the agents fetch and analyze the actual content.

Usage:
    uv run python eval/run_contrastive.py
    uv run python eval/run_contrastive.py --arch workflow workflow_with_fetch single
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from src.config import get_langfuse_client  # noqa: E402
from src.dataset import load_dataset  # noqa: E402
from src.runner import run_architecture  # noqa: E402
from src.scoring import extract_prediction  # noqa: E402

console = Console()

# Map display label -> ARCHITECTURES key. "workflow" has no URL extractor.
ARCH_ORDER = [("workflow_no_extractor", "workflow"), ("workflow_with_fetch", "workflow_with_fetch"),
              ("single", "single"), ("multi", "multi")]


def score(example: dict, out: dict) -> dict:
    pred_verdict, _ = extract_prediction(out)
    requires_fetch = bool(example.get("requires_fetch"))
    return {
        "requires_fetch": requires_fetch,
        # content_resolved only meaningful when a fetch was needed
        "content_resolved": float(out["fetched"]) if requires_fetch else None,
        "verdict_exact": float(pred_verdict == example["gold_verdict"]),
        "latency_s": out["latency_s"],
        "tool_calls": out["tool_calls"],
        "cost_usd": out.get("cost_usd", 0.0),
        "total_tokens": out.get("total_tokens", 0),
        "_pred": pred_verdict,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Contrastive eval on the hard dataset.")
    parser.add_argument("--arch", nargs="+", default=[label for label, _ in ARCH_ORDER])
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    selected = [(label, key) for label, key in ARCH_ORDER if label in args.arch]
    dataset = load_dataset("hard")
    if args.limit:
        dataset = dataset[: args.limit]
    client = get_langfuse_client()

    results: dict[str, list[dict]] = {label: [] for label, _ in selected}

    for ex in dataset:
        console.rule(f"[cyan]{ex['id']}[/cyan]  ([dim]{ex['input_type']}, requires_fetch={ex.get('requires_fetch')}[/dim])")
        for label, key in selected:
            try:
                if client is not None:
                    with client.start_as_current_observation(
                        name=f"contrastive-{label}-{ex['id']}", as_type="span"
                    ) as root:
                        out = run_architecture(key, ex["content"], ex["id"])
                        sc = score(ex, out)
                        root.score_trace(name="verdict_exact", value=sc["verdict_exact"], data_type="NUMERIC")
                        root.score_trace(name="cost_usd", value=float(sc["cost_usd"]), data_type="NUMERIC")
                        root.score_trace(name="total_tokens", value=float(sc["total_tokens"]), data_type="NUMERIC")
                        if sc["content_resolved"] is not None:
                            root.score_trace(name="content_resolved", value=sc["content_resolved"], data_type="NUMERIC")
                else:
                    out = run_architecture(key, ex["content"], ex["id"])
                    sc = score(ex, out)
            except Exception as exc:
                console.print(f"[red]{label} failed on {ex['id']}: {exc}[/red]")
                continue
            results[label].append(sc)
            cr = "n/a" if sc["content_resolved"] is None else f"{sc['content_resolved']:.0f}"
            mark = "[red]✗ fake success[/red]" if (sc["requires_fetch"] and not out["fetched"]) else "[green]✓[/green]"
            console.print(
                f"  [bold]{label:15}[/bold] content_resolved={cr:3} pred={sc['_pred']:20} "
                f"latency={sc['latency_s']}s tools={sc['tool_calls']} {mark}"
            )

    if client is not None:
        client.flush()

    _print_summary(results)


def _mean(rows: list[dict], key: str, only_fetch: bool = False) -> float | None:
    vals = [r[key] for r in rows if r[key] is not None and (not only_fetch or r["requires_fetch"])]
    return sum(vals) / len(vals) if vals else None


def _print_summary(results: dict[str, list[dict]]) -> None:
    table = Table(title="Table A — input adaptation (hard dataset)", show_lines=True)
    table.add_column("architecture", style="bold")
    table.add_column("n", justify="right")
    table.add_column("content\nresolved\n(fetch rows)", justify="right")
    table.add_column("verdict\nexact", justify="right")
    table.add_column("avg\nlatency", justify="right")
    table.add_column("avg\ncost", justify="right")
    table.add_column("avg\ntools", justify="right")

    for label, rows in results.items():
        cr = _mean(rows, "content_resolved")
        table.add_row(
            label,
            str(len(rows)),
            "—" if cr is None else f"{cr:.2f}",
            f"{_mean(rows, 'verdict_exact'):.2f}" if rows else "—",
            f"{_mean(rows, 'latency_s'):.1f}s" if rows else "—",
            f"${_mean(rows, 'cost_usd'):.4f}" if rows else "—",
            f"{_mean(rows, 'tool_calls'):.1f}" if rows else "—",
        )
    console.print(table)
    console.print(
        "[dim]workflow_no_extractor: content_resolved≈0 — it screens the raw URL and returns a "
        "plausible-but-wrong verdict (fake success). Adding a URL-extractor step fixes it, but "
        "you had to anticipate it; the agents adapt at runtime.[/dim]"
    )


if __name__ == "__main__":
    main()
