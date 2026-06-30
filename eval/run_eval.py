"""Regression eval: run every labeled example through all three architectures.

Computes per-contour-style metrics + operational cost, attaches Langfuse scores to
each trace, and prints a comparison table.

Usage:
    uv run python eval/run_eval.py
    uv run python eval/run_eval.py --arch workflow single   # subset
    uv run python eval/run_eval.py --limit 4                # quick smoke
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make the repo package importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from src.config import get_langfuse_client  # noqa: E402
from src.dataset import load_dataset  # noqa: E402
from src.runner import ARCHITECTURES, run_architecture  # noqa: E402
from src.scoring import MANIPULATIVE_VERDICTS, extract_prediction  # noqa: E402

console = Console()


def score_example(example: dict, out: dict) -> dict:
    pred_verdict, pred_abstention = extract_prediction(out)
    gold_verdict = example["gold_verdict"]
    gold_abstain = gold_verdict == "unverified"

    manipulation_pred = pred_verdict in MANIPULATIVE_VERDICTS
    return {
        "manipulation_correct": float(manipulation_pred == example["is_manipulative"]),
        "abstention_correct": float(pred_abstention == gold_abstain),
        "verdict_exact": float(pred_verdict == gold_verdict),
        "latency_s": out["latency_s"],
        "tool_calls": out["tool_calls"],
        "messages": out["messages"],
        "cost_usd": out.get("cost_usd", 0.0),
        "total_tokens": out.get("total_tokens", 0),
        "_pred_verdict": pred_verdict,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the 3-architecture regression eval.")
    parser.add_argument("--arch", nargs="+", choices=list(ARCHITECTURES), default=list(ARCHITECTURES))
    parser.add_argument("--dataset", default="clean", help="clean | hard | euvsdisinfo")
    parser.add_argument("--limit", type=int, default=None, help="evaluate only the first N examples")
    args = parser.parse_args()

    dataset = load_dataset(args.dataset)
    if args.limit:
        dataset = dataset[: args.limit]
    client = get_langfuse_client()
    if client is None:
        console.print("[yellow]Langfuse not configured — running without trace scoring.[/yellow]")

    # arch -> list of per-example score dicts
    results: dict[str, list[dict]] = {a: [] for a in args.arch}

    for ex in dataset:
        console.rule(f"[cyan]{ex['id']}[/cyan]")
        for arch in args.arch:
            try:
                if client is not None:
                    with client.start_as_current_observation(
                        name=f"eval-{arch}-{ex['id']}", as_type="span"
                    ) as root:
                        out = run_architecture(arch, ex["content"], ex["id"])
                        scores = score_example(ex, out)
                        for key in (
                            "manipulation_correct",
                            "abstention_correct",
                            "verdict_exact",
                            "latency_s",
                            "cost_usd",
                            "total_tokens",
                        ):
                            root.score_trace(name=key, value=float(scores[key]), data_type="NUMERIC")
                else:
                    out = run_architecture(arch, ex["content"], ex["id"])
                    scores = score_example(ex, out)
            except Exception as exc:  # keep the regression pass going on a single failure
                console.print(f"[red]{arch} failed on {ex['id']}: {exc}[/red]")
                continue
            results[arch].append(scores)
            console.print(
                f"  [bold]{arch:9}[/bold] pred={scores['_pred_verdict']:20} gold={ex['gold_verdict']:20} "
                f"verdict_exact={scores['verdict_exact']:.0f} latency={scores['latency_s']}s "
                f"cost=${scores['cost_usd']:.4f} tools={scores['tool_calls']}"
            )

    if client is not None:
        client.flush()

    _print_summary(results)


def _mean(rows: list[dict], key: str) -> float:
    return sum(r[key] for r in rows) / len(rows) if rows else 0.0


def _print_summary(results: dict[str, list[dict]]) -> None:
    table = Table(title="Three architectures — regression summary", show_lines=True)
    table.add_column("architecture", style="bold")
    table.add_column("n", justify="right")
    table.add_column("manip\nacc", justify="right")
    table.add_column("abstain\nacc", justify="right")
    table.add_column("verdict\nexact", justify="right")
    table.add_column("avg\nlatency", justify="right")
    table.add_column("avg\ncost", justify="right")
    table.add_column("avg\ntokens", justify="right")
    table.add_column("avg\ntools", justify="right")
    table.add_column("avg\nmessages", justify="right")

    for arch, rows in results.items():
        table.add_row(
            arch,
            str(len(rows)),
            f"{_mean(rows, 'manipulation_correct'):.2f}",
            f"{_mean(rows, 'abstention_correct'):.2f}",
            f"{_mean(rows, 'verdict_exact'):.2f}",
            f"{_mean(rows, 'latency_s'):.1f}s",
            f"${_mean(rows, 'cost_usd'):.4f}",
            f"{_mean(rows, 'total_tokens'):.0f}",
            f"{_mean(rows, 'tool_calls'):.1f}",
            f"{_mean(rows, 'messages'):.1f}",
        )
    console.print(table)
    console.print(
        "[dim]Read top-to-bottom: accuracy is roughly comparable (same contours), but "
        "latency / tool_calls / messages — the operational cost — grow workflow -> single -> multi.[/dim]"
    )


if __name__ == "__main__":
    main()
