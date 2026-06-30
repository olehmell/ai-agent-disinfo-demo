"""The three analytical contours + verifier, implemented ONCE.

All three architectures (workflow / single-agent / multi-agent) call into this module,
so the capability is identical and only the orchestration differs. Each contour is
exposed twice: as a plain callable (used by the workflow nodes) and wrapped as a
LangChain ``@tool`` (used by the agent architectures).
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import tempfile
from pathlib import Path

from langchain_core.runnables.config import ensure_config
from langchain_core.tools import tool

from .config import get_llm, load_prompt, tavily_enabled
from .state import (
    ClaimBundle,
    EvidenceItem,
    FactVerdict,
    FinalDecision,
    ScreeningProfile,
)

# How many claims to actually fact-check (keeps demo latency/cost bounded — budget policy).
MAX_CLAIMS_TO_CHECK = 3
TAVILY_MAX_RESULTS = 4

YT_DLP_BIN = "yt-dlp"
YT_DLP_TIMEOUT = 90
FETCH_FAIL = "FETCH_FAILED"
_YOUTUBE_RE = re.compile(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts/)", re.IGNORECASE)
_URL_RE = re.compile(r"https?://\S+")


# --- Source ingestion (real fetch; graceful FETCH_FAILED on error) ------------------


def _first_url(text: str) -> str | None:
    m = _URL_RE.search(text or "")
    return m.group(0).rstrip(").,]") if m else None


def _parse_vtt(vtt: str) -> str:
    """Flatten a WebVTT subtitle file to deduplicated plain text."""
    out: list[str] = []
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line == "WEBVTT" or "-->" in line or line.isdigit():
            continue
        if line.startswith(("Kind:", "Language:", "NOTE")):
            continue
        line = re.sub(r"<[^>]+>", "", line)  # strip inline timing tags
        if line and (not out or out[-1] != line):
            out.append(line)
    return " ".join(out)


YT_SUB_LANGS = ["en", "uk", "ru"]  # try in this order; en auto-captions are the most reliable


def _ytdlp_one_lang(url: str, lang: str) -> str | None:
    """Try to fetch one subtitle language; return parsed text or None on failure."""
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            YT_DLP_BIN, "--write-auto-subs", "--write-subs", "--skip-download",
            "--sub-langs", lang, "--sub-format", "vtt",
            "--retries", "5", "--sleep-requests", "1",
            "-o", str(Path(tmp) / "%(id)s.%(ext)s"), url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=YT_DLP_TIMEOUT, check=False)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        vtts = sorted(Path(tmp).glob("*.vtt"))
        if not vtts:
            return None
        return _parse_vtt(vtts[0].read_text(encoding="utf-8", errors="ignore")) or None


# Cache successful transcripts so the eval doesn't re-download one video per architecture
# (also lowers YouTube rate-limit risk). Failures are not cached, so a retry can still work.
_TRANSCRIPT_CACHE: dict[str, str] = {}


def _ytdlp_transcript(url: str) -> str:
    """Fetch a video's subtitles via the local yt-dlp binary (real fetch)."""
    if url in _TRANSCRIPT_CACHE:
        return _TRANSCRIPT_CACHE[url]
    if subprocess.run([YT_DLP_BIN, "--version"], capture_output=True).returncode != 0:
        return f"{FETCH_FAIL}: yt-dlp binary not found (install it: brew install yt-dlp)"
    for lang in YT_SUB_LANGS:
        text = _ytdlp_one_lang(url, lang)
        if text:
            _TRANSCRIPT_CACHE[url] = text
            return text
    return f"{FETCH_FAIL}: no subtitles downloadable (rate-limited or unavailable)"


def fetch_url(url: str) -> str:
    """Extract readable article text from a URL via Tavily Extract."""
    if not tavily_enabled():
        return f"{FETCH_FAIL}: TAVILY_API_KEY not set"
    try:
        from langchain_tavily import TavilyExtract

        result = TavilyExtract().invoke({"urls": [url]})
        results = result.get("results", []) if isinstance(result, dict) else []
        text = " ".join((r.get("raw_content") or "") for r in results).strip()
        return text or f"{FETCH_FAIL}: no extractable content at {url}"
    except Exception as exc:  # pragma: no cover - network/runtime guard for live demo
        return f"{FETCH_FAIL}: {exc}"


def fetch_source(text_or_url: str) -> dict:
    """Resolve raw input to analyzable text. Returns {source_type, fetched, text}."""
    url = _first_url(text_or_url)
    if url and _YOUTUBE_RE.search(url):
        text = _ytdlp_transcript(url)
        return {"source_type": "youtube", "fetched": not text.startswith(FETCH_FAIL), "text": text}
    if url:
        text = fetch_url(url)
        return {"source_type": "article_url", "fetched": not text.startswith(FETCH_FAIL), "text": text}
    return {"source_type": "text", "fetched": False, "text": text_or_url}


# --- Contour 1: manipulation screening ---------------------------------------------


def screen_manipulation(content: str) -> ScreeningProfile:
    llm = get_llm().with_structured_output(ScreeningProfile)
    prompt = load_prompt("screening").format(content=content)
    return llm.invoke(prompt, config=ensure_config())


# --- Contour 2: narrative / intent analysis ----------------------------------------


def analyze_narrative(content: str, screening: ScreeningProfile | dict | None = None) -> ClaimBundle:
    if isinstance(screening, ScreeningProfile):
        screening_text = screening.model_dump_json()
    elif isinstance(screening, dict):
        screening_text = json.dumps(screening, ensure_ascii=False)
    else:
        screening_text = "немає"
    llm = get_llm().with_structured_output(ClaimBundle)
    prompt = load_prompt("narrative").format(content=content, screening=screening_text)
    return llm.invoke(prompt, config=ensure_config())


# --- Contour 3: evidence retrieval + fact-checking ----------------------------------


def web_search(query: str) -> list[EvidenceItem]:
    """Retrieve evidence for a query. Real Tavily search, deterministic mock fallback.

    The mock keeps the demo runnable on stage if the key is missing or the network
    flaps — it never claims to support/refute, so downstream fact-check abstains.
    """
    if tavily_enabled():
        try:
            from langchain_tavily import TavilySearch

            results = TavilySearch(max_results=TAVILY_MAX_RESULTS).invoke({"query": query})
            items: list[EvidenceItem] = []
            raw = results.get("results", []) if isinstance(results, dict) else results
            for r in raw:
                if isinstance(r, dict):
                    items.append(
                        EvidenceItem(
                            source=r.get("url") or r.get("source") or "unknown",
                            snippet=(r.get("content") or r.get("snippet") or "")[:600],
                        )
                    )
            if items:
                return items
        except Exception as exc:  # pragma: no cover - network/runtime guard for live demo
            return [EvidenceItem(source="search_error", snippet=f"Пошук недоступний: {exc}")]
    return [
        EvidenceItem(
            source="mock://no-retrieval",
            snippet=(
                "Реальний веб-пошук вимкнено (немає TAVILY_API_KEY). "
                "Доказів не знайдено — твердження слід вважати unverifiable."
            ),
        )
    ]


def fact_check_one(claim: str, evidence: list[EvidenceItem]) -> FactVerdict:
    evidence_text = "\n".join(f"- [{e.source}] {e.snippet}" for e in evidence) or "немає"
    llm = get_llm().with_structured_output(FactVerdict)
    prompt = load_prompt("factcheck").format(claim=claim, evidence=evidence_text)
    verdict = llm.invoke(prompt, config=ensure_config())
    # Carry the actual retrieved evidence forward if the model returned none.
    if not verdict.evidence:
        verdict.evidence = evidence
    return verdict


def fact_check(claim_bundle: ClaimBundle | dict) -> list[FactVerdict]:
    if isinstance(claim_bundle, dict):
        claims = claim_bundle.get("claims", [])
        hints = claim_bundle.get("query_hints", [])
    else:
        claims = claim_bundle.claims
        hints = claim_bundle.query_hints
    hint_suffix = (" " + " ".join(hints[:3])) if hints else ""
    verdicts: list[FactVerdict] = []
    for claim in claims[:MAX_CLAIMS_TO_CHECK]:
        evidence = web_search(f"{claim}{hint_suffix}".strip())
        verdicts.append(fact_check_one(claim, evidence))
    return verdicts


# --- Synthesis + audit -------------------------------------------------------------


def decision_from_text(text: str) -> FinalDecision:
    """Map an agent's free-text conclusion onto the shared FinalDecision schema.

    This is the agents' equivalent of the workflow's verifier node — it makes every
    architecture emit the same structured output, so the comparison is apples-to-apples.
    """
    llm = get_llm().with_structured_output(FinalDecision)
    prompt = (
        "Сформуй структурований підсумок (FinalDecision) на основі цього аналізу. "
        "Чітко розділяй МАНІПУЛЯЦІЮ (форма/риторика) і ДЕЗІНФОРМАЦІЮ (зміст/факти). "
        "Усі пояснення українською. Якщо доказів бракує — abstention.\n\nАналіз:\n" + (text or "")
    )
    return llm.invoke(prompt, config=ensure_config())


def verify_synthesis(
    *,
    screening: ScreeningProfile | dict | None,
    narrative: ClaimBundle | dict | None,
    fact_checks: list[FactVerdict] | list[dict] | None,
    narrative_explanation: str = "",
) -> FinalDecision:
    def _dump(obj) -> str:
        if obj is None:
            return "немає"
        if hasattr(obj, "model_dump_json"):
            return obj.model_dump_json()
        return json.dumps(obj, ensure_ascii=False, default=str)

    fc = fact_checks or []
    fc_text = json.dumps(
        [f.model_dump() if hasattr(f, "model_dump") else f for f in fc],
        ensure_ascii=False,
        default=str,
    )
    llm = get_llm().with_structured_output(FinalDecision)
    prompt = load_prompt("verifier").format(
        screening=_dump(screening),
        narrative=_dump(narrative),
        fact_checks=fc_text,
        narrative_explanation=narrative_explanation or "немає",
    )
    return llm.invoke(prompt, config=ensure_config())


# --- Tool wrappers (identical capability, for the agent architectures) --------------


@tool
def screen_message(content: str) -> str:
    """Оцінити риторичний ризик і маніпулятивні техніки повідомлення (контур 1)."""
    return screen_manipulation(content).model_dump_json()


@tool
def analyze_narrative_tool(content: str) -> str:
    """Реконструювати наратив, інтенцію і виділити перевірювані твердження (контур 2)."""
    return analyze_narrative(content).model_dump_json()


@tool
def web_search_tool(query: str) -> str:
    """Знайти докази у вебі за запитом. Повертає список джерел і фрагментів."""
    items = web_search(query)
    return json.dumps([i.model_dump() for i in items], ensure_ascii=False)


@tool
def fact_check_claim(claim: str) -> str:
    """Винести evidence-bounded вердикт по ОДНОМУ твердженню (пошук + синтез, контур 3)."""
    evidence = web_search(claim)
    return fact_check_one(claim, evidence).model_dump_json()


@tool
def run_yt_dlp(command: str) -> str:
    """Запустити CLI yt-dlp, щоб дістати субтитри/інфо відео. Передай аргументи рядком,
    включно з URL. Підказка для субтитрів:
    `--write-auto-subs --skip-download --sub-langs uk,ru,en --sub-format vtt -o %(id)s.%(ext)s <URL>`.
    Повертає текст субтитрів (або FETCH_FAILED)."""
    url = _first_url(command)
    if not url:
        return f"{FETCH_FAIL}: no URL found in command"
    # Robust path: ignore the model's flag choices, fetch subtitles deterministically by URL.
    # (We keep the CLI-tool framing but pin the binary + flags for a reliable live demo.)
    try:
        shlex.split(command)  # validate the agent produced parseable args
    except ValueError as exc:
        return f"{FETCH_FAIL}: unparseable command ({exc})"
    return _ytdlp_transcript(url)


@tool
def fetch_url_tool(url: str) -> str:
    """Дістати читабельний текст статті за URL (для не-відео посилань)."""
    return fetch_url(url)


# Tool groupings used by the agent architectures.
INGEST_TOOLS = [run_yt_dlp, fetch_url_tool]
ALL_TOOLS = [run_yt_dlp, fetch_url_tool, screen_message, analyze_narrative_tool, web_search_tool, fact_check_claim]
SINGLE_RAW_TOOLS = [run_yt_dlp, fetch_url_tool, web_search_tool]
SCREENING_TOOLS = [screen_message]
NARRATIVE_TOOLS = [analyze_narrative_tool]
FACTCHECK_TOOLS = [web_search_tool, fact_check_claim]
