"""Shared execution helpers for Streamlit and eval scripts."""

from __future__ import annotations

import time

from . import contours
from .config import get_langfuse_client, run_config
from .metrics import UsageCollector, attach_usage_metrics, push_langfuse_cost_scores
from .multi_agent import build_multi_agent_graph
from .single_agent import build_single_agent_graph
from .workflow_graph import build_workflow_graph
from .workflow_with_fetch import build_workflow_with_fetch_graph

ARCHITECTURES = {
    "workflow": build_workflow_graph,
    "workflow_with_fetch": build_workflow_with_fetch_graph,
    "single": build_single_agent_graph,
    "multi": build_multi_agent_graph,
}

_IS_AGENT = {"single", "multi"}
# Tools whose use means the system adapted to fetch external content.
FETCH_TOOLS = {"run_yt_dlp", "fetch_url_tool"}


def _content_to_text(content) -> str:
    """Flatten a message's content to plain text (Gemini may return content blocks)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get("text") or p.get("content") or "")
            else:
                parts.append(str(p))
        return "\n".join(x for x in parts if x)
    return str(content)


def _normalize(arch: str, result: dict) -> dict:
    if arch in _IS_AGENT:
        messages = result.get("messages", [])
        final_text = _content_to_text(messages[-1].content) if messages else ""
        tool_names = [
            tc["name"]
            for m in messages
            for tc in (getattr(m, "tool_calls", []) or [])
        ]
        # Agent handoffs: transitions between distinct *agent* names on AI messages
        # (tool messages carry tool names — excluded so single-agent reads as 0 handoffs).
        segments = [
            m.name
            for m in messages
            if m.__class__.__name__ == "AIMessage" and getattr(m, "name", None)
        ]
        handoffs = max(0, sum(1 for a, b in zip(segments, segments[1:]) if a != b))
        # coordination-cost proxies
        repeat_tools = len(tool_names) - len(set(tool_names))
        spans = len(messages) + len(tool_names)
        # All architectures emit the SAME structured FinalDecision: agents get a final
        # structured-synthesis step (their equivalent of the workflow's verifier node).
        final_result = contours.decision_from_text(final_text).model_dump() if final_text else None
        return {
            "architecture": arch,
            "final_text": final_text,
            "messages": len(messages),
            "tool_calls": len(tool_names),
            "tool_names": tool_names,
            "handoffs": handoffs,
            "distinct_agents": len(set(segments)),
            "repeat_tools": repeat_tools,
            "spans": spans,
            "fetched": any(t in FETCH_TOOLS for t in tool_names),
            "final_result": final_result,
            "audit_log": [],
        }

    audit = result.get("audit_log", [])
    return {
        "architecture": arch,
        "final_text": "",
        "messages": 0,
        "tool_calls": 0,
        "tool_names": [],
        "handoffs": 0,
        "distinct_agents": 0,
        "repeat_tools": 0,
        "spans": len(audit),  # node executions ≈ spans for the workflow
        "fetched": any(e.startswith("url_extractor: fetched") for e in audit),
        "final_result": result.get("final_result"),
        "audit_log": audit,
    }


def run_architecture(arch: str, content: str, content_id: str) -> dict:
    """Invoke one architecture on one message. Returns a normalized result dict."""
    if arch not in ARCHITECTURES:
        raise ValueError(f"unknown architecture {arch!r}; choose from {list(ARCHITECTURES)}")
    graph = ARCHITECTURES[arch]()
    usage_collector = UsageCollector()
    config = run_config(arch, content_id, usage_collector=usage_collector)
    state = (
        {"messages": [{"role": "user", "content": content}]}
        if arch in _IS_AGENT
        else {"content": content, "content_id": content_id, "audit_log": []}
    )
    client = get_langfuse_client()

    started = time.perf_counter()
    trace_url = None
    if client is not None:
        # Wrap so we can capture the trace URL for deep-linking from the UI.
        with client.start_as_current_observation(name=f"run-{arch}-{content_id}", as_type="span") as span:
            result = graph.invoke(state, config=config)
            try:
                trace_url = client.get_trace_url()
            except Exception:
                trace_url = None
            out = _normalize(arch, result)
            attach_usage_metrics(
                out,
                usage_collector,
                result.get("messages") if arch in _IS_AGENT else None,
            )
            out["latency_s"] = round(time.perf_counter() - started, 2)
            out["trace_url"] = trace_url
            push_langfuse_cost_scores(span, out)
    else:
        result = graph.invoke(state, config=config)
        out = _normalize(arch, result)
        attach_usage_metrics(
            out,
            usage_collector,
            result.get("messages") if arch in _IS_AGENT else None,
        )
        out["latency_s"] = round(time.perf_counter() - started, 2)
        out["trace_url"] = trace_url

    if client is not None:
        client.flush()
    return out


if __name__ == "__main__":
    raise SystemExit("Use `uv run streamlit run streamlit_app.py`. `src.runner` is an internal module.")
