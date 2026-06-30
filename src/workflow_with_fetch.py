"""Architecture 1b — deterministic workflow with an explicit fetch step.

Same graph as ``workflow_graph`` but with a ``url_extractor`` node prepended that
normalizes the input (detects a URL, fetches the YouTube transcript or article text,
then replaces ``content``). The teaching point: the workflow can handle these inputs,
but only because the extra step was anticipated and hardcoded ahead of time.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import contours
from .workflow_graph import (
    _fact_checker_node,
    _narrative_explanation_node,
    _narrative_node,
    _orchestrator_node,
    _route_after_orchestrator,
    _screening_node,
    _verifier_node,
)
from .state import DisinfoState


def _url_extractor_node(state: DisinfoState) -> dict:
    result = contours.fetch_source(state["content"])
    if result["fetched"]:
        return {
            "content": result["text"],
            "audit_log": [
                f"url_extractor: fetched {result['source_type']} ({len(result['text'])} chars)"
            ],
        }
    return {"audit_log": [f"url_extractor: no URL to extract ({result['source_type']})"]}


def build_workflow_with_fetch_graph():
    g = StateGraph(DisinfoState)
    g.add_node("url_extractor", _url_extractor_node)
    g.add_node("screening", _screening_node)
    g.add_node("narrative", _narrative_node)
    g.add_node("orchestrator", _orchestrator_node)
    g.add_node("fact_checker", _fact_checker_node)
    g.add_node("narrative_explanation", _narrative_explanation_node)
    g.add_node("verifier", _verifier_node)

    # The anticipated extra step: extract content from a URL BEFORE the fixed flow runs.
    g.add_edge(START, "url_extractor")
    g.add_edge("url_extractor", "screening")
    g.add_edge("url_extractor", "narrative")
    g.add_edge("screening", "orchestrator")
    g.add_edge("narrative", "orchestrator")
    g.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        ["fact_checker", "narrative_explanation", "verifier"],
    )
    g.add_edge("fact_checker", "verifier")
    g.add_edge("narrative_explanation", "verifier")
    g.add_edge("verifier", END)
    return g.compile(name="workflow_with_fetch")
