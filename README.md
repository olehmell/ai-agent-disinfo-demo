# Content analysis demo

This repo compares four ways to run the same task.

The task stays fixed. The orchestration changes.

- `workflow` runs a fixed graph.
- `workflow_with_fetch` runs the same graph with a hardcoded fetch step.
- `single` gives one agent only fetch and search tools.
- `multi` splits the work between a supervisor and specialists.

The code answers two questions about a piece of content:

1. Is the writing manipulative?
2. Are the claims false or misleading?

## Files that matter

- [`src/contours.py`](src/contours.py): shared analysis logic
- [`src/workflow_graph.py`](src/workflow_graph.py): fixed graph
- [`src/workflow_with_fetch.py`](src/workflow_with_fetch.py): fixed graph with URL fetch
- [`src/single_agent.py`](src/single_agent.py): one raw agent over low-level tools
- [`src/multi_agent.py`](src/multi_agent.py): supervisor + specialists
- [`streamlit_app.py`](streamlit_app.py): UI
- [`eval/`](eval/): regression and contrastive evals

## Setup

```bash
uv sync
cp .env.example .env
```

Add `GEMINI_API_KEY` to `.env`.

The app and CLI stop at startup if the key is missing.

Optional keys:

- `TAVILY_API_KEY`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST` or `LANGFUSE_BASE_URL`

Without Tavily, the retrieval path falls back to a mock.
Without Langfuse, the runs still work but you get no traces.

## Run the UI

```bash
uv run streamlit run streamlit_app.py
```

The UI shows one shared manipulation panel and one result row per architecture.

## Datasets

- [`eval/dataset.jsonl`](eval/dataset.jsonl): clean text examples
- [`eval/hard_dataset.jsonl`](eval/hard_dataset.jsonl): URL, YouTube, and noisy inputs
- [`eval/euvsdisinfo_cases.jsonl`](eval/euvsdisinfo_cases.jsonl): real EUvsDisinfo cases

## Evals

```bash
uv run python eval/run_eval.py
uv run python eval/run_contrastive.py
uv run python eval/debuggability.py
```

- `run_eval.py` compares accuracy and cost.
- `run_contrastive.py` shows where the plain workflow fails.
- `debuggability.py` measures variance, handoffs, and span depth.

## More context

- [`RUNBOOK.md`](RUNBOOK.md): step-by-step demo flow
- [`docs/architectures.md`](docs/architectures.md): diagrams
- [`ARD.md`](ARD.md): problem, data, eval, architecture
