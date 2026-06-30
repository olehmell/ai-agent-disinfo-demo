# Contrastive eval suite — design

Date: 2026-06-20
Project: `ai-agent-disinfo-demo` (content-analysis demo, one use case / three architectures)

## Goal

The current eval shows all three architectures agree on clean text inputs. That hides the
trade-offs. This suite makes the trade-offs visible by constructing inputs and metrics where:

- **(A) the deterministic workflow breaks** — inputs that aren't normalized, or that need an
  extra step (fetch a YouTube video / an article) *before* the fixed flow can do anything useful;
- **(B) the multi-agent version is measurably more complex and harder to debug** — non-determinism,
  coordination cost, and deeper traces.

The teaching line: *workflow is great when you anticipated every step; the moment an input needs an
unplanned step, the fixed graph silently does the wrong thing. An agent adapts at runtime — but you
pay for that adaptivity in cost and debuggability.*

## Decisions (confirmed)

- **Fetch is real-only** (no fixtures). Failures degrade gracefully to a visible `FETCH_FAILED: …`
  string so an agent can react and a human can see it in the trace.
- **YouTube ingestion uses the local `yt-dlp` binary** (installed, v2026.03.03), not a Python lib.
  It's a deliberately good "agent figures out and uses a CLI tool" case.
- **Two workflow variants**: `workflow_broken` (current) and `workflow_with_fetch` (adds an ingest node).
- **Debuggability signals**: non-determinism (N runs), coordination cost, trace depth.
- **Dataset URLs**: I seed evergreen public URLs (stable captions / stable article text); gold leans
  on *whether the system analyzed the real content*, so labels stay stable. User can swap later.
- Presentation slides are out of scope unless asked separately.

## Architecture / components

### 1. Source ingestion (shared) — `contours.py`

Helpers (deterministic, used by `workflow_with_fetch` and as the article path):

- `_ytdlp_transcript(url) -> str` — runs `yt-dlp --write-auto-subs --write-subs --skip-download
  --sub-langs "uk,ru,en" --sub-format vtt -o <tmp> <url>` via `subprocess.run` (list args, no shell,
  timeout ~60s, binary pinned to `yt-dlp`). Parses the `.vtt` to plain text. On any failure returns
  `FETCH_FAILED: <reason>`.
- `fetch_url(url) -> str` — Tavily **Extract** (reuses `TAVILY_API_KEY`); returns article text or
  `FETCH_FAILED: …`.
- `fetch_source(text_or_url) -> dict` — dispatch: youtube → `_ytdlp_transcript`; other url →
  `fetch_url`; plain text → passthrough. Returns `{source_type, fetched: bool, text}`.

Agent-facing tools (the "figure it out" surface):

- `run_yt_dlp(args: str) -> str` — robust subprocess wrapper around the `yt-dlp` binary. Docstring
  describes it as "run the yt-dlp CLI to fetch a video's subtitles/info; pass CLI args incl. the URL"
  with a one-line subtitle-extraction hint. Splits args safely (`shlex.split`), pins binary, no shell,
  timeout, returns combined stdout + any parsed subtitle text (or `FETCH_FAILED: …`).
- `fetch_url_tool(url)` — wraps `fetch_url`.

Both added to the agents' toolsets. The agent recognizes the link type and chooses the tool — that
runtime decision is the whole point. The fixed workflow has no equivalent leap.

*Safety note*: `run_yt_dlp` runs a real subprocess. It is pinned to the `yt-dlp` binary, uses no shell,
splits args, and enforces a timeout. We deliberately do **not** expose a generic shell tool (too flaky
and too broad a surface for a live stage demo); scoping to one CLI keeps it reliable and on-message.

### 2. Hard dataset — `eval/hard_dataset.jsonl`

Rows of inputs that need a pre-step the fixed flow never anticipated. Fields:
`id, content, input_type {youtube|article_url|unnormalized}, requires_fetch, source_url,
is_manipulative, gold_verdict, note`.

Seeded categories:
- **youtube**: `"Подивись це відео і скажи чи це фейк: <url>"` — evergreen video w/ stable captions.
- **article_url**: `"Перевір цю статтю: <url>"` — stable article (Wikipedia/press/official).
- **unnormalized**: `Fwd: Fwd:` + emoji / zero-width chars / channel-footer noise burying the claim
  (no network needed; tests normalization, not fetch).

Gold for fetch rows centers on *content_resolved* + verdict-vs-underlying, not on the content being
disinformation, so evergreen neutral sources are acceptable and labels stay stable.

### 3. Workflow: broken vs fixed

- `workflow_broken` = existing `workflow_graph.py`, unchanged. Screens raw `content`; a URL is screened
  as a string → low risk → early stop → plausible-but-wrong ("fake success").
- `workflow_with_fetch` = `workflow_with_fetch.py`. Reuses the existing node fns and prepends an
  **`ingest`** node: `fetch_source(content)` → if fetched, replace `state["content"]` with the
  resolved text and log it; then the original graph runs. Demonstrates the fix works **only because
  the step was anticipated**.

Single-agent and multi-agent get `run_yt_dlp` + `fetch_url_tool` added to their toolsets.

### 4. Metrics (input-adaptation)

- **`content_resolved`** — instrumented: did a fetch/ingest actually occur for a `requires_fetch`
  input? `workflow_broken`→0; `workflow_with_fetch`/agents→1 when fetch happened. Primary "workflow breaks"
  signal. Computed from the audit log (workflow) / tool-call names (agents).
- **`verdict_exact`** vs underlying gold (secondary).

### 5. Debuggability harness — `eval/debuggability.py`

Computed locally from message/graph events (deterministic, offline); Langfuse carries the visual.

- **Non-determinism**: run each of a few inputs `N=5×` per arch; report verdict-variance (count of
  distinct verdicts) and route-variance (distinct tool-call counts / distinct routes). Expect
  `workflow≈0`, `multi` highest.
- **Coordination cost**: per run — spans proxy (node execs + messages + tool calls), handoffs
  (distinct consecutive `message.name` segments), redundant tool calls (same tool+arg >1×).
- **Trace depth**: depth proxy (workflow flat ≈1; single ≈loop turns; multi ≈supervisor+specialist
  subtrees) + a pointer to line the three Langfuse traces up visually.

*Alternative considered*: querying the Langfuse API for true span counts — rejected as default (API
coupling + latency); local instrumentation is deterministic and Langfuse still tells the visual story.

### 6. Outputs / runners

- `eval/run_contrastive.py` — runs `{workflow_broken, workflow_with_fetch, single, multi}` over the hard
  dataset; prints **Table A (input adaptation)**: per-arch `content_resolved`, `verdict_exact`,
  latency, tools; pushes scores to Langfuse.
- `eval/debuggability.py` — prints **Table B (debuggability)**: per-arch variance, coordination cost,
  depth.
- `runner.py` — register `workflow_with_fetch` in `ARCHITECTURES`; add `--dataset hard` to pull from the
  hard dataset.
- README — add a "where each architecture breaks" section.

## Data flow

```
raw input ──► workflow_broken : screening(raw URL) → early stop → WRONG (fake success)
          ──► workflow_with_fetch : ingest(fetch_source) → screening(real text) → … → verifier ✓
          ──► single agent    : recognizes link → run_yt_dlp / fetch_url_tool → … ✓ (variable cost)
          ──► multi agent     : supervisor delegates fetch + analysis → … ✓ (most spans/handoffs)
```

## Error handling

- Fetch failures return `FETCH_FAILED: <reason>` (never raise into the graph). Agents may retry or
  abstain; workflow_with_fetch logs it and proceeds (likely abstains). All visible in the trace.
- `run_yt_dlp`: timeout + pinned binary + no shell; on non-zero exit returns stderr tail as
  `FETCH_FAILED`.
- `run_contrastive` / `debuggability` keep going on a single-run failure (already the pattern in
  `run_eval.py`).

## Testing / verification

1. `uv sync` (no new Python deps; yt-dlp is the system binary — assert availability with a clear error).
2. Smoke each arch on one youtube row and one unnormalized row via `runner.py`.
3. `uv run python eval/run_contrastive.py` — Table A shows `workflow_broken` content_resolved≈0 while
   others≈1.
4. `uv run python eval/debuggability.py` — Table B shows variance/coordination/depth rising
   workflow → single → multi.
5. Langfuse: confirm `workflow_broken` trace never fetches; line up the three traces for one input.

## Out of scope

- Presentation slide edits.
- A generic shell tool (scoped to yt-dlp on purpose).
- A scripted recursion-limit failure case (not selected).
