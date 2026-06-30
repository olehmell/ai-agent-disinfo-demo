"""Streamlit app — see the real difference between the architectures.

Two distinct outputs, shown separately:
  1. МАНІПУЛЯЦІЯ (форма) — highlight the manipulative spans + explain why (contour 1, shared).
  2. ДЕЗІНФОРМАЦІЯ (зміст) — is it factually false + why, per architecture (contours 2–3).

    uv run streamlit run streamlit_app.py
"""

from __future__ import annotations

import html
import re

import streamlit as st

from src import contours
from src.config import require_gemini_api_key
from src.dataset import load_dataset
from src.runner import ARCHITECTURES, run_architecture
from ui_theme import highlight_markup, inject, panel, pill, section, title_block, verdict_label

st.set_page_config(page_title="AI Agent Content Analysis Demo", layout="wide", initial_sidebar_state="expanded")

try:
    require_gemini_api_key()
except RuntimeError as exc:
    st.error(str(exc))
    st.stop()

inject(st)

ARCH_LABELS = {
    "workflow": "Workflow (no URL extractor)",
    "workflow_with_fetch": "Workflow (fetch step)",
    "single": "Single agent",
    "multi": "Multi-agent",
}
DATASET_LABELS = {
    "euvsdisinfo": "Реальні кейси EUvsDisinfo",
    "hard": "Зламні входи (URL / YouTube / шум)",
    "clean": "Базові приклади",
}
_CANON_VERDICT = ("likely_disinformation", "mixed", "unverified", "likely_reliable")
_URL_RE = re.compile(r"https?://\S+")


def _canon(verdict: str) -> str:
    v = (verdict or "").lower()
    for key in _CANON_VERDICT:
        if key.split("_")[-1] in v:
            return key
    return "unverified"


def _line(text: str, key: str) -> str:
    m = re.search(rf"{key}\s*[:\-]\s*(.+)", text or "", re.IGNORECASE)
    return m.group(1).strip() if m else ""


def _is_true(s: str) -> bool:
    return bool(re.match(r"\s*(true|так|yes)\b", s, re.IGNORECASE))


def _strip_bool(s: str) -> str:
    return re.sub(r"^\s*(true|false|так|ні|yes|no)\s*[—\-:.]*\s*", "", s, flags=re.IGNORECASE)


def result_view(out: dict) -> dict:
    """Normalize one architecture's output to the disinformation view."""
    if out.get("final_result"):
        fr = out["final_result"]
        return {
            "verdict": str(fr.get("verdict")),
            "abstention": bool(fr.get("abstention")),
            "is_disinformation": bool(fr.get("is_disinformation")),
            "disinfo_expl": fr.get("disinformation_explanation", ""),
            "is_manipulative": bool(fr.get("is_manipulative")),
            "manip_expl": fr.get("manipulation_explanation", ""),
            "raw": "",
        }
    text = out.get("final_text") or ""
    disinfo_raw, manip_raw = _line(text, "disinformation"), _line(text, "manipulation")
    return {
        "verdict": _line(text, "verdict") or "unverified",
        "abstention": _is_true(_line(text, "abstention")),
        "is_disinformation": _is_true(disinfo_raw),
        "disinfo_expl": _strip_bool(disinfo_raw),
        "is_manipulative": _is_true(manip_raw),
        "manip_expl": _strip_bool(manip_raw),
        "raw": text,
    }


def _format_cost(usd: float) -> str:
    if usd >= 0.01:
        return f"${usd:.3f}"
    if usd >= 0.0001:
        return f"${usd:.4f}"
    return f"${usd:.6f}"


def _format_tokens(n: int) -> str:
    if n >= 10_000:
        return f"{n / 1000:.1f}k"
    return str(n)


def _depth(out: dict) -> int:
    arch = out["architecture"]
    if arch.startswith("workflow"):
        return 1
    if arch == "single":
        return 2 if out["tool_calls"] else 1
    return (2 if out["distinct_agents"] else 1) + (1 if out["tool_calls"] else 0)


def _render_arch_row(arch: str, out: dict, view: dict, needs_fetch: bool) -> None:
    if "error" in out:
        st.markdown(
            panel(
                f"<h4>{html.escape(ARCH_LABELS[arch])}</h4>"
                f'<p style="color:var(--t-rose)">ERR: {html.escape(out["error"])}</p>'
            ),
            unsafe_allow_html=True,
        )
        return

    fetch_html = ""
    if needs_fetch:
        if out["fetched"]:
            fetch_html = pill("CONTENT_RESOLVED", "ok")
        else:
            fetch_html = pill("FAKE SUCCESS", "bad")

    abst = pill("ABSTENTION", "warn") if view["abstention"] else ""
    disinfo_flag = pill("DISINFO", "bad") if view["is_disinformation"] else pill("NOT PROVEN", "muted")

    trace_link = ""
    if out.get("trace_url"):
        trace_link = f'<p class="t-muted"><a href="{html.escape(out["trace_url"])}" target="_blank">trace → Langfuse</a></p>'

    details = ""
    if out.get("audit_log"):
        log = html.escape("\n".join(out["audit_log"]))
        details += f"<p><strong>audit log</strong></p><pre style='font-size:0.72rem;color:var(--t-green-dim)'>{log}</pre>"
    if out.get("tool_names"):
        tools = html.escape(" → ".join(out["tool_names"]))
        details += f"<p class='t-muted'>tools: {tools}</p>"
    if view["raw"]:
        details += f"<pre style='font-size:0.72rem;color:var(--t-green-dim)'>{html.escape(view['raw'])}</pre>"

    inner = f"""
    <h4>{html.escape(ARCH_LABELS[arch])}</h4>
    <div style="margin:8px 0">{verdict_label(_canon(view['verdict']))} {fetch_html} {abst}</div>
    <div class="t-verdict"><code>{html.escape(view['verdict'])}</code></div>
    <p style="margin-top:12px"><strong>дезінформація?</strong> {disinfo_flag}</p>
    <p>{html.escape(view['disinfo_expl'] or view['raw'] or '—')}</p>
    <div class="t-stats">
      <b>cost</b> {_format_cost(out.get('cost_usd', 0.0))} &middot;
      <b>tokens</b> {_format_tokens(out.get('total_tokens', 0))}
      ({out.get('input_tokens', 0)} in / {out.get('output_tokens', 0)} out)<br>
      <b>latency</b> {out['latency_s']}s &middot; <b>tools</b> {out['tool_calls']} &middot;
      <b>messages</b> {out['messages']} &middot; <b>handoffs</b> {out['handoffs']}<br>
      <b>spans</b> {out['spans']} &middot; <b>depth</b> {_depth(out)} &middot;
      <b>llm_calls</b> {out.get('llm_calls', 0)}
    </div>
    {trace_link}
  """
    st.markdown(panel(inner), unsafe_allow_html=True)
    if details:
        with st.expander("деталі"):
            st.markdown(details, unsafe_allow_html=True)


def _comparison_table(results: dict, needs_fetch: bool) -> str:
    rows = []
    for arch, out in results.items():
        if "error" in out:
            continue
        view = result_view(out)
        fetched = "✓" if out["fetched"] else ("✕" if needs_fetch else "—")
        fetched_cls = "" if fetched == "✓" else ("bad" if fetched == "✕" else "")
        rows.append(
            f"<tr>"
            f"<td>{html.escape(ARCH_LABELS[arch])}</td>"
            f"<td><code>{html.escape(view['verdict'])}</code></td>"
            f'<td class="{fetched_cls}">{fetched}</td>'
            f"<td>{_format_cost(out.get('cost_usd', 0.0))}</td>"
            f"<td>{out.get('total_tokens', 0)}</td>"
            f"<td>{out['latency_s']}</td>"
            f"<td>{out['tool_calls']}</td>"
            f"<td>{out['messages']}</td>"
            f"<td>{out['handoffs']}</td>"
            f"<td>{out['spans']}</td>"
            f"<td>{_depth(out)}</td>"
            f"</tr>"
        )
    if not rows:
        return ""
    return (
        "<table class='t-table'><thead><tr>"
        "<th>архітектура</th><th>verdict</th><th>fetched</th><th>cost</th><th>tokens</th>"
        "<th>latency</th><th>tools</th><th>msgs</th><th>handoffs</th><th>spans</th><th>depth</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


# --- Sidebar -----------------------------------------------------------------------

with st.sidebar:
    st.markdown(section("INPUT", "Вхід"), unsafe_allow_html=True)
    mode = st.radio("Джерело", ["Готовий кейс", "Свій текст або URL"], label_visibility="collapsed")

    content, meta = "", {}
    if mode == "Готовий кейс":
        ds_key = st.selectbox("Датасет", list(DATASET_LABELS), format_func=lambda k: DATASET_LABELS[k])
        rows = load_dataset(ds_key)
        idx = st.selectbox(
            "Кейс",
            range(len(rows)),
            format_func=lambda i: f"{rows[i].get('id', i)} — {rows[i]['content'][:48]}…",
        )
        meta = rows[idx]
        content = meta["content"]
    else:
        content = st.text_area(
            "Текст або посилання",
            height=160,
            placeholder="Підозрілий допис, стаття-URL або YouTube-посилання…",
        )

    archs = st.multiselect(
        "Архітектури",
        list(ARCHITECTURES),
        default=list(ARCHITECTURES),
        format_func=lambda a: ARCH_LABELS[a],
    )
    run = st.button("ЗАПУСТИТИ", type="primary", use_container_width=True)

# --- Header ------------------------------------------------------------------------

st.markdown(
    title_block(
        "Live Demo",
        "Детекція дезінформації",
        "Один use case — чотири архітектури. Два питання: маніпуляція (форма) і дезінформація (зміст).",
    ),
    unsafe_allow_html=True,
)
st.markdown(
    '<div style="margin-bottom:18px">'
    + pill("LangGraph")
    + pill("Gemini Flash")
    + pill("Tavily")
    + pill("Langfuse")
    + "</div>",
    unsafe_allow_html=True,
)

if content:
    meta_bits = []
    if meta.get("gold_verdict"):
        meta_bits.append(pill(f"gold: {meta['gold_verdict']}", "warn"))
    if meta.get("report_url"):
        url = html.escape(meta["report_url"])
        meta_bits.append(f'<a href="{url}" target="_blank">{pill("EUvsDisinfo debunk")}</a>')
    if _URL_RE.search(content):
        meta_bits.append(pill("needs fetch", "warn"))

    st.markdown(
        panel(
            "<strong>вхід</strong>"
            + (f'<div style="margin:8px 0">{"".join(meta_bits)}</div>' if meta_bits else "")
            + f'<div class="t-input-box">{html.escape(content)}</div>'
        ),
        unsafe_allow_html=True,
    )

# --- Run ---------------------------------------------------------------------------

if run and content and archs:
    st.session_state["results"] = {}
    with st.spinner("screening…"):
        analyzed, note = content, ""
        if _URL_RE.search(content):
            fs = contours.fetch_source(content)
            if fs["fetched"]:
                analyzed, note = fs["text"], f"fetch: {fs['source_type']} ({len(fs['text'])} sym)"
        try:
            profile = contours.screen_manipulation(analyzed).model_dump()
        except Exception as exc:
            profile, analyzed = {"error": str(exc)}, analyzed
        st.session_state["screening"] = {"profile": profile, "analyzed": analyzed, "note": note}

    progress = st.progress(0.0, text="running architectures…")
    for i, arch in enumerate(archs):
        progress.progress(i / len(archs), text=f"{ARCH_LABELS[arch]}…")
        try:
            st.session_state["results"][arch] = run_architecture(arch, content, meta.get("id", "ui"))
        except Exception as exc:
            st.session_state["results"][arch] = {"error": str(exc)}
    progress.progress(1.0, text="done")
    st.session_state["meta"] = meta
    st.session_state["needs_fetch"] = bool(_URL_RE.search(content))

# --- 1. Manipulation panel (shared) ------------------------------------------------

screening = st.session_state.get("screening")
if screening:
    st.markdown(section("Contour 1", "Маніпуляція — форма"), unsafe_allow_html=True)
    prof = screening["profile"]
    if "error" in prof:
        st.error(prof["error"])
    else:
        prob = prof.get("manipulation_probability", 0)
        manip = prob >= 0.5
        techniques = " ".join(pill(t) for t in prof.get("techniques", []))
        note = f'<p class="t-muted">{html.escape(screening["note"])}</p>' if screening["note"] else ""

        st.markdown(
            panel(
                f'<div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:12px">'
                f"<div><span class='t-muted'>manipulation_probability</span><br>"
                f"<span class='t-verdict' style='font-size:1.1rem'>{prob:.2f}</span></div>"
                f"<div>{pill('MANIPULATIVE', 'bad') if manip else pill('CLEAN', 'ok')}</div>"
                f"<div>{techniques}</div>"
                f"</div>"
                f"<p><strong>чому:</strong> {html.escape(prof.get('explanation') or '—')}</p>"
                f"{note}"
                f"<p class='t-muted' style='margin-top:14px'>підсвічені фрагменти:</p>"
                + highlight_markup(screening["analyzed"][:1500], prof.get("triggers", []))
                + ("<p class='t-muted'>…</p>" if len(screening["analyzed"]) > 1500 else "")
            ),
            unsafe_allow_html=True,
        )

# --- 2. Disinformation results, per architecture -----------------------------------

results = st.session_state.get("results")
if results:
    needs_fetch = st.session_state.get("needs_fetch", False)
    st.markdown(section("Contours 2–3", "Дезінформація — зміст"), unsafe_allow_html=True)

    for arch, out in results.items():
        _render_arch_row(arch, out, result_view(out), needs_fetch)

    table_html = _comparison_table(results, needs_fetch)
    if table_html:
        st.markdown(section("Metrics", "Порівняння вартості"), unsafe_allow_html=True)
        st.markdown(
            panel(table_html)
            + '<p class="t-formula">вердикт часто схожий — fetch, cost і depth розходяться</p>',
            unsafe_allow_html=True,
        )
elif not screening:
    st.markdown(
        '<p class="t-muted">обери кейс у sidebar і натисни <strong>ЗАПУСТИТИ</strong></p>',
        unsafe_allow_html=True,
    )
