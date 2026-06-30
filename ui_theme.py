"""Terminal CRT theme for the demo UI."""

from __future__ import annotations

import html

TERMINAL_CSS = """
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Share+Tech+Mono&display=swap');

:root {
  --t-bg: #000000;
  --t-green: #2df05a;
  --t-green-dim: #41bd61;
  --t-green-soft: rgba(45, 240, 90, 0.55);
  --t-line: rgba(45, 240, 90, 0.40);
  --t-line-soft: rgba(45, 240, 90, 0.20);
  --t-fill: rgba(45, 240, 90, 0.06);
  --t-amber: #f0b73a;
  --t-rose: #ff5d52;
}

.stApp {
  background: var(--t-bg) !important;
  color: var(--t-green-dim) !important;
  font-family: "IBM Plex Mono", monospace !important;
}

.stApp::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 9998;
  pointer-events: none;
  background: repeating-linear-gradient(
    0deg,
    rgba(0,0,0,0) 0px,
    rgba(0,0,0,0) 2px,
    rgba(0,0,0,0.22) 3px,
    rgba(0,0,0,0) 4px
  );
}

.stApp::after {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 9997;
  pointer-events: none;
  background: radial-gradient(ellipse 95% 88% at 50% 50%, transparent 58%, rgba(0,0,0,0.55) 100%);
}

.block-container { padding-top: 2.8rem !important; max-width: 1180px !important; }

h1, h2, h3, h4 {
  font-family: "Share Tech Mono", monospace !important;
  color: var(--t-green) !important;
  text-shadow: 0 0 9px rgba(45, 240, 90, 0.35) !important;
  font-weight: 400 !important;
}

p, li, label, .stMarkdown, span { color: var(--t-green-dim); }
strong { color: var(--t-green) !important; }
code {
  color: var(--t-green) !important;
  background: var(--t-fill) !important;
  border: 1px solid var(--t-line-soft) !important;
  border-radius: 0 !important;
  padding: 1px 5px !important;
}

[data-testid="stSidebar"] {
  background: #000 !important;
  border-right: 1px solid var(--t-line) !important;
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  font-size: 0.95rem !important;
}

.stButton > button[kind="primary"],
.stButton > button[kind="primary"]:focus:not(:active) {
  background: transparent !important;
  color: var(--t-green) !important;
  border: 1px solid var(--t-green) !important;
  border-radius: 0 !important;
  font-family: "IBM Plex Mono", monospace !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.06em !important;
  box-shadow: 0 0 10px rgba(45, 240, 90, 0.12) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--t-fill) !important;
  color: var(--t-green) !important;
  border-color: var(--t-green) !important;
  box-shadow: 0 0 14px rgba(45, 240, 90, 0.2) !important;
}
.stButton > button[kind="secondary"] {
  background: transparent !important;
  color: var(--t-green) !important;
  border: 1px solid var(--t-line) !important;
  border-radius: 0 !important;
}

.stTextInput input, .stTextArea textarea, .stSelectbox > div > div,
[data-baseweb="select"] > div, [data-baseweb="popover"] {
  background: #020802 !important;
  color: var(--t-green-dim) !important;
  border-color: var(--t-line) !important;
  border-radius: 0 !important;
  font-family: "IBM Plex Mono", monospace !important;
}

.stRadio label, .stMultiSelect label { font-size: 0.82rem !important; }

/* multiselect — outline chips, not filled */
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  background: #020802 !important;
  border-color: var(--t-line) !important;
  border-radius: 0 !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"],
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
  background: transparent !important;
  background-color: transparent !important;
  border: 1px solid var(--t-green) !important;
  border-radius: 0 !important;
  box-shadow: none !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] span,
[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
  color: var(--t-green) !important;
  background: transparent !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"] svg,
[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {
  fill: var(--t-green-soft) !important;
}
[data-testid="stMultiSelect"] [data-baseweb="tag"]:hover,
[data-testid="stMultiSelect"] span[data-baseweb="tag"]:hover {
  background: var(--t-fill) !important;
  border-color: var(--t-green) !important;
}

/* selectbox + dropdown menus — outline highlight, not filled */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
  background: #020802 !important;
  border-color: var(--t-line) !important;
}

[data-baseweb="popover"],
[data-baseweb="menu"] {
  background: #020802 !important;
  border: 1px solid var(--t-line) !important;
  border-radius: 0 !important;
}

[data-baseweb="menu"] ul,
[data-baseweb="popover"] ul {
  background: #020802 !important;
}

[data-baseweb="menu"] li,
[data-baseweb="menu"] [role="option"],
[data-baseweb="popover"] li,
[data-baseweb="popover"] [role="option"] {
  background: transparent !important;
  background-color: transparent !important;
  color: var(--t-green-dim) !important;
  border: 1px solid transparent !important;
  border-radius: 0 !important;
  font-family: "IBM Plex Mono", monospace !important;
}

[data-baseweb="menu"] li:hover,
[data-baseweb="menu"] [role="option"]:hover,
[data-baseweb="popover"] li:hover,
[data-baseweb="popover"] [role="option"]:hover,
[data-baseweb="menu"] li[aria-selected="true"],
[data-baseweb="menu"] [role="option"][aria-selected="true"],
[data-baseweb="popover"] li[aria-selected="true"],
[data-baseweb="popover"] [role="option"][aria-selected="true"],
[data-baseweb="menu"] li[data-highlighted="true"],
[data-baseweb="menu"] [role="option"][data-highlighted="true"],
[data-baseweb="popover"] li[data-highlighted="true"],
[data-baseweb="popover"] [role="option"][data-highlighted="true"] {
  background: transparent !important;
  background-color: transparent !important;
  color: var(--t-green) !important;
  border-color: var(--t-green) !important;
}

[data-baseweb="menu"] li > div,
[data-baseweb="popover"] li > div,
[data-baseweb="option"] > div {
  background: transparent !important;
  color: inherit !important;
}

/* baseweb injects highlight layer on focused option */
[data-baseweb="menu"] [data-baseweb="highlight"],
[data-baseweb="popover"] [data-baseweb="highlight"] {
  background-color: transparent !important;
  background: transparent !important;
  border: 1px solid var(--t-green) !important;
  border-radius: 0 !important;
  box-shadow: 0 0 8px rgba(45, 240, 90, 0.15) !important;
}

[data-baseweb="menu"] li::before,
[data-baseweb="popover"] li::before {
  background: transparent !important;
}

[data-testid="stMetric"] {
  background: var(--t-fill) !important;
  border: 1px solid var(--t-line-soft) !important;
  padding: 10px 12px !important;
  border-radius: 0 !important;
}
[data-testid="stMetricLabel"] { color: var(--t-green-soft) !important; font-size: 0.72rem !important; }
[data-testid="stMetricValue"] { color: var(--t-green) !important; font-family: "IBM Plex Mono", monospace !important; }

.stProgress > div > div {
  background: var(--t-green) !important;
  border-radius: 0 !important;
}
.stProgress > div {
  background: var(--t-line-soft) !important;
  border-radius: 0 !important;
}

div[data-testid="stExpander"] {
  border: 1px solid var(--t-line-soft) !important;
  border-radius: 0 !important;
  background: #020802 !important;
}
div[data-testid="stExpander"] summary { color: var(--t-green) !important; }

.stAlert {
  border-radius: 0 !important;
  border: 1px solid var(--t-line) !important;
  background: var(--t-fill) !important;
}
[data-testid="stAlertContainer"] p { color: var(--t-green-dim) !important; }

hr { border-color: var(--t-line-soft) !important; }

.stDataFrame { border: 1px solid var(--t-line) !important; border-radius: 0 !important; }

/* terminal components */
.t-sys {
  position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
  padding: 10px 24px 8px;
  font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--t-green-soft);
  background: rgba(0,0,0,0.92);
  border-bottom: 1px solid var(--t-line-soft);
  pointer-events: none;
}
.t-sys b { color: var(--t-green); }

.t-rail {
  position: fixed; top: 0; left: 0; right: 0; z-index: 10000;
  display: flex; gap: 2px; height: 3px;
}
.t-rail span { flex: 1; background: var(--t-line-soft); opacity: 0.5; }
.t-rail span.on { opacity: 1; background: var(--t-green); box-shadow: 0 0 8px var(--t-green); }

.t-kicker {
  display: flex; align-items: center; gap: 8px;
  margin: 0 0 10px;
  font-size: 0.72rem; font-weight: 600;
  letter-spacing: 0.14em; text-transform: uppercase;
  color: var(--t-green);
}
.t-kicker::before { content: ">"; font-weight: 700; }

.t-lede {
  color: var(--t-green-dim) !important;
  font-size: 0.92rem !important;
  line-height: 1.45 !important;
  margin: 0 0 18px !important;
}

.t-panel {
  position: relative;
  margin: 14px 0;
  padding: 18px 20px;
  border: 1px solid var(--t-line);
  background: rgba(45, 240, 90, 0.022);
  box-shadow: 0 0 40px rgba(45, 240, 90, 0.04);
}
.t-panel::before, .t-panel::after {
  content: "";
  position: absolute;
  width: 11px; height: 11px;
  border: 1px solid var(--t-green);
  pointer-events: none;
}
.t-panel::before { top: 6px; left: 6px; border-right: 0; border-bottom: 0; }
.t-panel::after { bottom: 6px; right: 6px; border-left: 0; border-top: 0; }

.t-panel h3, .t-panel h4 {
  margin: 0 0 10px !important;
  font-size: 1rem !important;
}

.t-pill {
  display: inline-block;
  padding: 3px 9px;
  margin: 2px 4px 2px 0;
  border: 1px solid var(--t-line);
  color: var(--t-green);
  font-size: 0.72rem;
  letter-spacing: 0.02em;
}

.t-badge-ok   { color: var(--t-green); border-color: var(--t-green); background: transparent; }
.t-badge-warn { color: var(--t-amber); border-color: var(--t-amber); background: transparent; }
.t-badge-bad  { color: var(--t-rose); border-color: var(--t-rose); background: transparent; }
.t-badge-muted{ color: var(--t-green-soft); border-color: var(--t-line-soft); background: transparent; }

.t-verdict {
  font-family: "Share Tech Mono", monospace;
  font-size: 1.35rem;
  color: var(--t-green);
  text-shadow: 0 0 10px rgba(45,240,90,0.45);
}

.t-input-box {
  line-height: 1.65;
  padding: 12px 14px;
  border: 1px solid var(--t-line);
  border-left: 3px solid var(--t-green);
  background: #020802;
  color: var(--t-green-dim);
  font-size: 0.88rem;
  word-break: break-word;
}

.t-highlight mark {
  background: rgba(240, 183, 58, 0.2);
  color: var(--t-amber);
  padding: 0 2px;
  border-bottom: 1px solid var(--t-amber);
}

.t-stats {
  font-size: 0.78rem;
  line-height: 1.7;
  color: var(--t-green-dim);
}
.t-stats b { color: var(--t-green); }

.t-formula {
  margin: 12px 0;
  padding: 12px 14px;
  border: 1px solid var(--t-line);
  border-left: 3px solid var(--t-green);
  background: var(--t-fill);
  color: var(--t-green);
  font-size: 0.82rem;
}
.t-formula::before { content: "// "; color: var(--t-green-soft); }

.t-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.78rem;
  margin-top: 8px;
}
.t-table th, .t-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--t-line-soft);
  text-align: left;
}
.t-table th { color: var(--t-green); font-weight: 600; border-bottom-color: var(--t-line); }
.t-table td { color: var(--t-green-dim); }
.t-table td:first-child { color: var(--t-green); font-weight: 500; }
.t-table .bad { color: var(--t-rose); font-weight: 600; }

.t-muted { color: var(--t-green-soft) !important; font-size: 0.78rem !important; }

a { color: var(--t-green) !important; }
a:hover { text-shadow: 0 0 8px rgba(45,240,90,0.4); }

#MainMenu, footer, header { visibility: hidden; }
"""


def inject(streamlit_module) -> None:
    streamlit_module.markdown(f"<style>{TERMINAL_CSS}</style>", unsafe_allow_html=True)
    streamlit_module.markdown(
        '<div class="t-rail"><span class="on"></span><span class="on"></span><span></span><span></span></div>'
        '<div class="t-sys">&gt; SYS://<b>DISINFO_DEMO</b> &middot; LIVE_COMPARE</div>',
        unsafe_allow_html=True,
    )


def kicker(text: str) -> str:
    return f'<div class="t-kicker">{html.escape(text)}</div>'


def title_block(kicker_text: str, heading: str, lede: str = "") -> str:
    parts = [kicker(kicker_text), f"<h1>{html.escape(heading)}</h1>"]
    if lede:
        parts.append(f'<p class="t-lede">{html.escape(lede)}</p>')
    return "\n".join(parts)


def section(kicker_text: str, heading: str) -> str:
    return f'{kicker(kicker_text)}<h2 style="margin-top:0">{html.escape(heading)}</h2>'


def panel(inner: str) -> str:
    return f'<div class="t-panel">{inner}</div>'


def pill(text: str, variant: str = "") -> str:
    cls = f"t-pill t-badge-{variant}" if variant else "t-pill"
    return f'<span class="{cls}">{html.escape(text)}</span>'


def verdict_label(canon: str) -> str:
    labels = {
        "likely_disinformation": ("DISINFO", "bad"),
        "mixed": ("MIXED", "warn"),
        "unverified": ("UNVERIFIED", "muted"),
        "likely_reliable": ("RELIABLE", "ok"),
    }
    text, variant = labels.get(canon, ("UNKNOWN", "muted"))
    return pill(text, variant)


def highlight_markup(text: str, spans: list[str]) -> str:
    import re

    safe = html.escape(text)
    pats = sorted({html.escape(s.strip()) for s in spans if s and s.strip()}, key=len, reverse=True)
    if not pats:
        return f'<div class="t-input-box t-highlight">{safe}</div>'
    pattern = re.compile("|".join(re.escape(p) for p in pats), re.IGNORECASE)
    body = pattern.sub(
        lambda m: f"<mark>{m.group(0)}</mark>",
        safe,
    )
    return f'<div class="t-input-box t-highlight">{body}</div>'
