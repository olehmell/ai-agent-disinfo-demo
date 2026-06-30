"""Shared configuration: env loading, the single LLM factory and Langfuse wiring."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from the standalone repo root.
_PROJECT_DIR = Path(__file__).resolve().parents[1]
_ENV_FILE = _PROJECT_DIR / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE, override=True)

# Langfuse v4 expects LANGFUSE_HOST; accept LANGFUSE_BASE_URL as an alias.
if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

# "Gemini Flash 3 Lite" — overridable so the exact id can be swapped without code changes.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")


def require_gemini_api_key() -> str:
    """Return the Gemini API key or raise a clear startup error."""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if api_key:
        return api_key

    env_hint = (
        f"Create {_ENV_FILE} from .env.example and add GEMINI_API_KEY."
        if not _ENV_FILE.exists()
        else f"Add GEMINI_API_KEY to {_ENV_FILE}."
    )
    raise RuntimeError(f"GEMINI_API_KEY is missing. {env_hint}")


def _temperature() -> float:
    """Read temperature at call time so harnesses can raise it to surface non-determinism.

    Low default: the demo wants reproducible client-grade behaviour, not exploration.
    """
    return float(os.getenv("GEMINI_TEMPERATURE", "0.1"))

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@cache
def load_prompt(name: str) -> str:
    """Load a versioned prompt file by stem (e.g. ``"screening"``).

    Prompts live as files (1-to-1 mapping) rather than hidden in-code strings.
    """
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


@cache
def get_llm(thinking_budget: int | None = None):
    """Return the shared chat model used by every contour, node and agent.

    ``thinking_budget=0`` disables Gemini 3 "thinking". The multi-agent architecture
    needs this: langgraph-supervisor reconstructs synthetic handoff tool-calls that lack
    the thought_signature Gemini 3 otherwise requires.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = require_gemini_api_key()
    kwargs: dict = {
        "model": GEMINI_MODEL,
        "temperature": _temperature(),
        "google_api_key": api_key,
    }
    if thinking_budget is not None:
        kwargs["thinking_budget"] = thinking_budget
    return ChatGoogleGenerativeAI(**kwargs)


def tavily_enabled() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))


def langfuse_enabled() -> bool:
    return bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))


@cache
def get_langfuse_handler():
    """Return a LangChain CallbackHandler if Langfuse is configured, else ``None``.

    The handler reads LANGFUSE_* keys from the environment. Returning ``None`` keeps
    the demo runnable (just untraced) when keys are absent.
    """
    if not langfuse_enabled():
        return None
    from langfuse.langchain import CallbackHandler

    return CallbackHandler()


@cache
def get_langfuse_client():
    """Return the Langfuse client (for scoring/flushing) if configured, else ``None``."""
    if not langfuse_enabled():
        return None
    from langfuse import get_client

    return get_client()


def run_config(architecture: str, content_id: str, *, usage_collector=None) -> dict:
    """Build the LangChain ``config`` for a graph invocation.

    Attaches the Langfuse callback and tags the trace by architecture + content_id so
    the three runs are easy to line up side by side in the Langfuse UI.
    """
    handler = get_langfuse_handler()
    config: dict = {
        "recursion_limit": 50,
        "metadata": {
            "architecture": architecture,
            "content_id": content_id,
            "langfuse_tags": [f"arch:{architecture}", f"content:{content_id}"],
            "langfuse_session_id": content_id,
        },
        "run_name": f"content-analysis-{architecture}-{content_id}",
    }
    callbacks = [h for h in (handler, usage_collector) if h is not None]
    if callbacks:
        config["callbacks"] = callbacks
    return config
