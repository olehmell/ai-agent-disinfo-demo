"""Architecture 1 — deterministic workflow (state graph).

Screening + narrative run in parallel, the orchestrator does an explicit early
stop/continue, then fact-check + narrative-explanation fan out and join at a final
verifier. All routing is plain code, which makes this the easiest version to test,
review, and debug.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from . import contours
from .state import DisinfoState

# Continue to the expensive contours when risk is non-trivial.
ESCALATION_THRESHOLD = 0.4


def _screening_node(state: DisinfoState) -> dict:
    profile = contours.screen_manipulation(state["content"])
    return {
        "manipulation_probability": profile.manipulation_probability,
        "manipulation_techniques": profile.techniques,
        "screening_profile": profile.model_dump(),
        "audit_log": [
            f"screening: p={profile.manipulation_probability:.2f} "
            f"techniques={profile.techniques} escalate={profile.escalate}"
        ],
    }


def _narrative_node(state: DisinfoState) -> dict:
    bundle = contours.analyze_narrative(state["content"])
    return {
        "narrative": bundle.narrative,
        "intent": bundle.intent,
        "claims": bundle.claims,
        "query_hints": bundle.query_hints,
        "audit_log": [f"narrative: intent={bundle.intent} claims={len(bundle.claims)}"],
    }


def _should_escalate(state: DisinfoState) -> bool:
    profile = state.get("screening_profile", {})
    return bool(profile.get("escalate")) or (
        state.get("manipulation_probability", 0.0) >= ESCALATION_THRESHOLD
    )


def _orchestrator_node(state: DisinfoState) -> dict:
    targets = _route_after_orchestrator(state)
    return {
        "audit_log": [
            f"orchestrator: escalate={_should_escalate(state)} "
            f"claims={bool(state.get('claims'))} -> {targets}"
        ]
    }


def _route_after_orchestrator(state: DisinfoState) -> list[str] | str:
    escalate = _should_escalate(state)
    has_claims = bool(state.get("claims"))
    if escalate and has_claims:
        return ["fact_checker", "narrative_explanation"]
    if escalate and state.get("manipulation_probability", 0.0) >= 0.6:
        # High-risk but no checkable claims: explain the narrative, skip fact-check.
        return ["narrative_explanation"]
    return "verifier"  # early stop


def _fact_checker_node(state: DisinfoState) -> dict:
    bundle = {"claims": state.get("claims", []), "query_hints": state.get("query_hints", [])}
    verdicts = contours.fact_check(bundle)
    return {
        "search_queries": state.get("query_hints", []),
        "fact_check_results": [v.model_dump() for v in verdicts],
        "audit_log": [f"fact_checker: checked={len(verdicts)} verdicts={[v.verdict for v in verdicts]}"],
    }


def _narrative_explanation_node(state: DisinfoState) -> dict:
    # Deterministic data step — compose a human-readable narrative explanation, no LLM call.
    actors = ", ".join(state.get("screening_profile", {}).get("triggers", [])[:3])
    explanation = (
        f"Сюжет: {state.get('narrative', '—')}. "
        f"Інтенція: {state.get('intent', '—')}. "
        f"Тригери: {actors or '—'}."
    )
    return {
        "narrative_explanation": explanation,
        "audit_log": ["narrative_explanation: composed"],
    }


def _verifier_node(state: DisinfoState) -> dict:
    decision = contours.verify_synthesis(
        screening=state.get("screening_profile"),
        narrative={
            "narrative": state.get("narrative"),
            "intent": state.get("intent"),
            "claims": state.get("claims"),
        },
        fact_checks=state.get("fact_check_results"),
        narrative_explanation=state.get("narrative_explanation", ""),
    )
    return {
        "final_result": decision.model_dump(),
        "audit_log": [f"verifier: verdict={decision.verdict} abstention={decision.abstention}"],
    }


def build_workflow_graph():
    g = StateGraph(DisinfoState)
    g.add_node("screening", _screening_node)
    g.add_node("narrative", _narrative_node)
    g.add_node("orchestrator", _orchestrator_node)
    g.add_node("fact_checker", _fact_checker_node)
    g.add_node("narrative_explanation", _narrative_explanation_node)
    g.add_node("verifier", _verifier_node)

    # Parallel entry: screening + narrative.
    g.add_edge(START, "screening")
    g.add_edge(START, "narrative")
    # Join at orchestrator.
    g.add_edge("screening", "orchestrator")
    g.add_edge("narrative", "orchestrator")
    # Explicit early stop / continue.
    g.add_conditional_edges(
        "orchestrator",
        _route_after_orchestrator,
        ["fact_checker", "narrative_explanation", "verifier"],
    )
    g.add_edge("fact_checker", "verifier")
    g.add_edge("narrative_explanation", "verifier")
    g.add_edge("verifier", END)
    return g.compile(name="workflow")
