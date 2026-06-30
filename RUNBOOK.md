# Runbook — reproduce every demo flow

A linear walkthrough of the demo. For the high-level framing, see [`README.md`](README.md).
For the flow diagrams, see [`docs/architectures.md`](docs/architectures.md).

All commands run from the repo root.

## 0. Prerequisites

| Need | Check | Install |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `yt-dlp` | `yt-dlp --version` | `brew install yt-dlp` |
| API keys | see step 2 | — |

## 1. Install

```bash
uv sync
```

Expected: a `.venv/` is created and dependencies resolve without errors.

## 2. Configure keys

Copy the template and fill in the repo-local `.env`:

```bash
cp .env.example .env
```

Required: `GEMINI_API_KEY`, `TAVILY_API_KEY`, `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, plus `LANGFUSE_HOST` or `LANGFUSE_BASE_URL`.

Sanity check:

```bash
uv run python -c "from src.config import tavily_enabled, langfuse_enabled, GEMINI_MODEL; print(GEMINI_MODEL, tavily_enabled(), langfuse_enabled())"
```

Expected: `gemini-flash-lite-latest True True`.

## 3. Flow A — Streamlit app

```bash
uv run streamlit run streamlit_app.py
```

Open `http://localhost:8501`, pick a dataset item or paste text or URL, choose architectures,
and compare verdicts, fake-success flags, and trace links side by side.

## 4. Flow B — clean regression eval

```bash
uv run python eval/run_eval.py
```

Expected: a per-case stream and summary table. Accuracy stays fairly close, while
latency, tool calls, and messages increase from `workflow` to `multi`.

## 5. Flow C — real cases batch

```bash
uv run python eval/run_eval.py --dataset euvsdisinfo
```

## 6. Flow D — workflow-breaks eval

```bash
uv run python eval/run_contrastive.py
```

Expected: `workflow_no_extractor` has `content_resolved ≈ 0`, while
`workflow_with_fetch`, `single`, and `multi` resolve the content.

## 7. Flow E — debuggability / coordination cost

```bash
uv run python eval/debuggability.py --runs 4
```

Expected: `workflow` stays deterministic, agents drift more as temperature rises,
and spans, handoffs, and depth increase across more autonomous architectures.

## 8. Flow F — Langfuse traces

After any run, filter Langfuse by `arch:<name>` or `content:<id>` to line up the same
input across architectures and compare trace depth.

## Suggested demo order

1. Run Flow A and compare the same input across architectures.
2. Use a hard URL or YouTube case in the app.
3. Run Flows D and E to tie the story to metrics.
4. Close in Langfuse with Flow F.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `GEMINI_API_KEY is not set` | add it to `.env` in the repo root |
| YouTube `FETCH_FAILED: ... 429` | transient rate limit; re-run |
| `yt-dlp binary not found` | `brew install yt-dlp` |
| Langfuse not configured | optional; runs still work, just untraced |
| Tavily missing | retrieval falls back to a mock and abstains more often |
