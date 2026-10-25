import streamlit as st

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400..700&family=Newsreader:ital,opsz,wght@0,6..72,400..600;1,6..72,400..600&display=swap');

:root {
  --ink: #0F2630;
  --side: #0B1E27;
  --panel: #143341;
  --line: #2A5565;
  --paper: #EAF0EE;
  --muted: #93AEB8;
  --mark: #F0D264;
  --ok: #5FD39A;
  --warn: #F2A65A;
  --bad: #FF7A6B;
  --serif: "Newsreader", Georgia, serif;
  --sans: "Instrument Sans", system-ui, sans-serif;
}

.stApp { background: var(--ink); color: var(--paper); font-family: var(--sans); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"], [data-testid="stDecoration"], footer { display: none; }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 780px; padding-top: 2.5rem; padding-bottom: 8rem; }

[data-testid="stSidebar"] { background: var(--side); border-right: 1px solid var(--line); }
[data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] { padding-top: 2rem; }

.stButton > button, .stDownloadButton > button {
  background: transparent; color: var(--paper); border: 1px solid var(--line);
  border-radius: 10px; font-family: var(--sans); font-weight: 500;
  transition: background .15s ease, border-color .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover { background: var(--panel); border-color: var(--muted); color: var(--paper); }
button:focus-visible, summary:focus-visible { outline: 2px solid var(--mark) !important; outline-offset: 2px; }

.brand { font-family: var(--serif); font-size: 1.7rem; font-weight: 500; letter-spacing: -0.01em; line-height: 1.1; }
.tagline { color: var(--muted); font-size: .9rem; margin: .35rem 0 1.4rem; }

.status { display: flex; align-items: center; gap: .55rem; font-size: .92rem; margin: 1rem 0 .4rem; }
.dot { width: .6rem; height: .6rem; border-radius: 50%; flex: none; background: var(--muted); display: inline-block; }
.dot.ok { background: var(--ok); }
.dot.warn { background: var(--warn); }
.dot.bad { background: var(--bad); }
.detail { display: flex; align-items: center; gap: .55rem; font-size: .88rem; padding: .25rem 0; }
.detail span:last-child { color: var(--muted); margin-left: auto; text-align: right; }

.facts { margin: 1.2rem 0 1rem; border-top: 1px solid var(--line); }
.fact { display: flex; justify-content: space-between; gap: 1rem; padding: .55rem 0; border-bottom: 1px solid var(--line); font-size: .9rem; }
.fact span { color: var(--muted); }
.fact b { font-weight: 500; font-variant-numeric: tabular-nums; }
.mono { font-family: ui-monospace, "Cascadia Mono", Consolas, monospace; font-size: .85rem; }

.hero-title { font-family: var(--serif); font-size: clamp(2.6rem, 8vw, 3.8rem); font-weight: 450; letter-spacing: -0.025em; line-height: 1.02; margin: 7vh 0 1rem; color: var(--paper); }
.hero-text { color: var(--muted); font-size: 1.1rem; line-height: 1.55; max-width: 48ch; margin: 0; }

.st-key-suggestions { margin-top: 2.2rem; border-bottom: 1px solid var(--line); gap: 0; }
.st-key-suggestions .stButton > button {
  width: 100%; justify-content: flex-start; text-align: left; min-height: 0;
  border: 0; border-top: 1px solid var(--line); border-radius: 0; padding: 1rem .25rem;
  transition: background .15s ease, padding-left .15s ease;
}
.st-key-suggestions .stButton > button p { font-family: var(--serif); font-size: 1.25rem; font-weight: 400; text-align: left; }
.st-key-suggestions .stButton > button:hover { background: var(--panel); padding-left: 1rem; }

[data-testid="stChatMessage"] { background: transparent; padding: .8rem 0; gap: .9rem; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background: var(--panel); border-radius: 14px; padding: .9rem 1.1rem; }
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) p { font-weight: 500; }
[class*="st-key-answer"] p, [class*="st-key-answer"] li { font-family: var(--serif); font-size: 1.22rem; line-height: 1.65; max-width: 66ch; }

.thinking { display: flex; align-items: center; gap: .5rem; color: var(--muted); font-family: var(--serif); font-style: italic; font-size: 1.15rem; padding: .3rem 0; }
.thinking i { width: .45rem; height: .45rem; border-radius: 50%; background: var(--mark); animation: pulse 1.2s ease-in-out infinite; }
.thinking i:nth-child(2) { animation-delay: .15s; }
.thinking i:nth-child(3) { animation-delay: .3s; }
@keyframes pulse { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }

.notice { border-left: 3px solid var(--bad); background: var(--panel); border-radius: 0 10px 10px 0; padding: .8rem 1rem; }
.notice b { display: block; margin-bottom: .2rem; }
.notice span { color: var(--muted); font-size: .95rem; }

.chips { margin: .6rem 0 .2rem; }
.chip { display: inline-block; font-size: .82rem; color: var(--muted); border: 1px solid var(--line); border-radius: 999px; padding: .15rem .7rem; margin: 0 .4rem .4rem 0; font-variant-numeric: tabular-nums; }

.passages { margin-top: .8rem; }
.passages-title { color: var(--muted); font-size: .88rem; margin-bottom: .3rem; }
.passage { border-left: 2px solid var(--line); padding: .35rem 0 .35rem .9rem; margin: .5rem 0; }
.passage[open] { border-left-color: var(--mark); }
.passage summary { cursor: pointer; list-style: none; display: flex; gap: .8rem; color: var(--muted); font-size: .92rem; line-height: 1.45; }
.passage summary::-webkit-details-marker { display: none; }
.passage .rank { font-variant-numeric: tabular-nums; color: var(--paper); flex: none; }
.passage[open] .preview { display: none; }
.passage .tag { flex: none; align-self: flex-start; font-size: .7rem; font-weight: 600; letter-spacing: .05em; text-transform: uppercase; color: var(--ink); background: var(--mark); border-radius: 4px; padding: .05rem .4rem; margin-top: .12rem; }
.passage .tag.domain { background: transparent; color: var(--muted); border: 1px solid var(--line); text-transform: none; letter-spacing: 0; font-weight: 500; font-size: .75rem; }
.passage .src { color: var(--muted); font-family: var(--sans); font-size: .85rem; }
.passage .weblink { color: var(--mark); text-decoration: underline; text-underline-offset: 3px; font-family: var(--sans); font-size: .95rem; }
.passage .weblink:hover { color: var(--paper); }
.passage .full { font-family: var(--serif); font-size: 1.05rem; line-height: 1.6; color: var(--paper); margin-top: .6rem; max-width: 66ch; }
mark { color: inherit; background: linear-gradient(180deg, transparent 58%, #C4A43C 58%); padding: 0 .08em; }

[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] { background: var(--ink); }
[data-testid="stChatInput"] { background: var(--panel); border: 1px solid var(--line); border-radius: 16px; }
[data-testid="stChatInput"] > div { background: transparent; }
[data-testid="stChatInput"]:focus-within { border-color: var(--mark); }
[data-testid="stChatInput"] textarea { font-family: var(--sans); color: var(--paper); }

[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 10px; background: transparent; }

@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
"""


def apply():
    st.markdown("<style>" + CSS + "</style>", unsafe_allow_html=True)