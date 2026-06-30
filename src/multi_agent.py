"""Architecture 3 — multi-agent (supervisor + specialists).

A supervisor delegates to three specialist ReAct sub-agents, each with its own tool
subset and isolated context, then synthesizes. This makes coordination debt visible:
more spans, more state handoffs, more failure points.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor

from .config import get_llm, load_prompt
from .contours import FACTCHECK_TOOLS, INGEST_TOOLS, NARRATIVE_TOOLS, SCREENING_TOOLS

# Thinking disabled: supervisor handoffs reconstruct tool-calls without thought_signature,
# which Gemini 3 rejects when thinking is on.
_MULTI_LLM = get_llm(thinking_budget=0)


def _specialist(name: str, tools, instruction: str):
    return create_react_agent(model=_MULTI_LLM, tools=tools, prompt=instruction, name=name)


def build_multi_agent_graph():
    ingest_agent = _specialist(
        "ingest_agent",
        INGEST_TOOLS,
        "Ти спеціаліст з отримання контенту. Якщо у вхідних даних є посилання (YouTube або "
        "стаття), дістань його текст відповідним інструментом і поверни супервізору. Для "
        "YouTube використовуй yt-dlp. Якщо посилання немає — повідом, що фетч не потрібен.",
    )
    screening_agent = _specialist(
        "screening_agent",
        SCREENING_TOOLS,
        "Ти спеціаліст зі скринінгу маніпуляцій. Оціни риторичний ризик і техніки "
        "повідомлення через інструмент і коротко віддай результат супервізору.",
    )
    narrative_agent = _specialist(
        "narrative_agent",
        NARRATIVE_TOOLS,
        "Ти спеціаліст із наративно-інтенційного аналізу. Реконструюй наратив, інтенцію "
        "і виділи перевірювані твердження через інструмент. Поверни їх супервізору.",
    )
    factcheck_agent = _specialist(
        "factcheck_agent",
        FACTCHECK_TOOLS,
        "Ти спеціаліст із доказової верифікації. Для кожного твердження знайди докази у "
        "вебі й винеси evidence-bounded вердикт. Якщо доказів немає — поверни unverifiable.",
    )

    return create_supervisor(
        agents=[ingest_agent, screening_agent, narrative_agent, factcheck_agent],
        model=_MULTI_LLM,
        prompt=load_prompt("supervisor"),
        supervisor_name="supervisor",
        # Keep specialists' messages so the trace + cost metrics show real coordination.
        output_mode="full_history",
        # Don't inject synthetic handoff tool-call messages into history — Gemini 3
        # rejects functionCall parts that lack a thought_signature.
        add_handoff_messages=False,
        add_handoff_back_messages=False,
    ).compile(name="multi_agent")
