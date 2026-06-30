"""Architecture 2 — one raw ReAct agent over low-level tools.

The agent gets fetch and search tools, but it has to do the analytical work itself:
judge manipulation, extract claims, choose searches, and write the conclusion.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from .config import get_llm, load_prompt
from .contours import SINGLE_RAW_TOOLS


def build_single_agent_graph():
    return create_react_agent(
        model=get_llm(),
        tools=SINGLE_RAW_TOOLS,
        prompt=load_prompt("agent_system"),
        name="single_agent",
    )
