# Single Raw Agent Design

Date: 2026-06-30
Project: `ai-agent-disinfo-demo`

## Goal

Make `single` a real one-agent architecture instead of a coordinator over high-level
analytical tools.

The single agent should keep only low-level tools:

- `run_yt_dlp`
- `fetch_url_tool`
- `web_search_tool`

It should do the analysis itself:

- decide whether a link must be fetched
- judge manipulation from the text
- extract checkable claims
- decide which claims deserve evidence lookup
- read evidence and write the final conclusion

## Constraint

The output contract must stay the same.

`single` still has to land in the shared `FinalDecision` path so the current metrics,
Streamlit UI, and eval scripts keep working:

- `verdict_exact`
- `abstention_correct`
- `content_resolved`
- latency / tool_calls / messages / spans / handoffs

## Current Problem

Right now `single` uses high-level tools from `contours.py`:

- `screen_message`
- `analyze_narrative_tool`
- `fact_check_claim`

That makes it too close to "multi-agent with shared specialist tools but no handoffs".
The orchestration looks different, but the analytical boundary is still pre-factored
for the model.

## Design

### 1. Tool boundary

Add a dedicated tool group for the raw single agent.

- Keep `ALL_TOOLS` for any code that still needs the old full set.
- Add `SINGLE_RAW_TOOLS = [run_yt_dlp, fetch_url_tool, web_search_tool]`.
- Point `single_agent.py` at `SINGLE_RAW_TOOLS`.

### 2. Prompt

Rewrite `src/prompts/agent_system.md` from a general "decide what to do" prompt to an
explicit operating procedure.

The prompt should force this order of reasoning:

1. If the input contains a link, fetch the content first.
2. Work on the fetched text, not the raw URL.
3. Assess manipulation from the text itself.
4. Extract only atomic, checkable claims.
5. Use web search only for claims worth checking.
6. If evidence is weak or contradictory, abstain.
7. End with a stable final answer that names:
   - `verdict`
   - `abstention`
   - `маніпуляція`
   - `дезінформація`
   - short evidence-based explanations in Ukrainian

The agent should not mention hidden internal state or JSON. It should write a clear
text conclusion that `decision_from_text()` can map into `FinalDecision`.

### 3. Final normalization

Keep `runner.py` unchanged at the contract boundary:

- `single` still returns free text
- `_normalize()` still passes that text into `contours.decision_from_text()`

This keeps the shared metrics and the UI stable.

### 4. Expected effect

After this change:

- `workflow` stays code-routed
- `single` becomes one-brain-with-tools
- `multi` stays role-routed with explicit handoffs

That separation is the point of the demo.

## Risks

### Quality drift

`single` will likely get worse at:

- manipulation judgment
- claim extraction
- evidence scoping

That is acceptable if the evals show the trade-off clearly.

### Format drift

If the prompt gets too loose, the final text may become harder for
`decision_from_text()` to normalize. The prompt needs a strict closing format.

## Verification

1. `uv run python -m compileall src streamlit_app.py`
2. `uv run python -c "from src.single_agent import build_single_agent_graph; print(build_single_agent_graph().name)"`
3. Run one lightweight `run_architecture("single", ...)` smoke check
4. Run `eval/run_eval.py --limit 1`
5. Run `eval/run_contrastive.py --limit 1`

## Files to change

- `src/contours.py`
- `src/single_agent.py`
- `src/prompts/agent_system.md`
- `README.md` if the public framing mentions the old boundary
