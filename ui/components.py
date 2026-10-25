import html
import re
import time

import streamlit as st

USER_AVATAR = ":material/person:"
BOT_AVATAR = ":material/menu_book:"

SUGGESTIONS = [
    "What is the 3-2-1 backup rule?",
    "How long do I have to report a data breach?",
    "What is the rule of 72?",
    "How many hours of sleep do adults need?",
    "What is a Kubernetes Pod?",
]

SERVICE_NAMES = {
    "postgres": "Chat memory",
    "qdrant": "Vector database",
    "llm_gateway": "Language model",
    "jina_embeddings": "Embeddings",
    "jina_reranker": "Reranker",
    "logfire": "Tracing",
}

STOP_WORDS = {
    "what", "with", "that", "this", "from", "have", "does", "about", "into", "your", "their",
    "which", "when", "where", "there", "should", "would", "could", "definition", "explain",
}


def search_term(plan):
    for step in plan or []:
        if step.startswith("Search Term: "):
            return step[len("Search Term: "):]
    return ""


def keywords(term):
    words = re.findall(r"[a-z]{4,}", term.lower())
    return sorted({word for word in words if word not in STOP_WORDS}, key=len, reverse=True)


def highlight(text, words):
    safe = html.escape(text)
    if words:
        pattern = r"\b(" + "|".join(re.escape(word) for word in words) + r")\w*"
        safe = re.sub(pattern, lambda match: "<mark>" + match.group(0) + "</mark>", safe, flags=re.I)
    return safe.replace("\n", "<br>")


def chips_html(result):
    plan = result.get("thought_process") or []
    sources = result.get("sources") or []
    chips = []

    if result.get("blocked"):
        chips.append("Answered by a guardrail")
    elif "Intent: Conversational" in plan:
        chips.append("Answered from the conversation")
    elif "Web Search Used" in plan:
        term = search_term(plan)
        if term:
            chips.append("Searched the web for &ldquo;" + html.escape(term) + "&rdquo;")
        chips.append(f"{len(sources)} web result{'' if len(sources) == 1 else 's'} read")
    elif "Web Search: No Results" in plan:
        chips.append("Nothing in the documents or on the web")
    elif "No Context Found" in plan:
        chips.append("No matching passages")
    else:
        term = search_term(plan)
        if term:
            chips.append("Searched for &ldquo;" + html.escape(term) + "&rdquo;")
        chips.append(f"{len(sources)} passage{'' if len(sources) == 1 else 's'} read")

    if "Cache: Hit" in plan:
        chips.append("Served from cache")
    chips.append(f"{result.get('seconds', 0):.1f} s")

    return '<div class="chips">' + "".join(f'<span class="chip">{chip}</span>' for chip in chips) + "</div>"


def web_link(item):
    title = html.escape(item.get("title") or "Web page")
    url = item.get("url") or ""
    if not url.startswith(("http://", "https://")):
        return title
    return f'<a class="weblink" href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{title}</a>'


def passages_html(result):
    sources = result.get("sources") or []
    if not sources:
        return ""

    web = result.get("web_sources") or []
    files = result.get("doc_sources") or []
    from_web = len(web) == len(sources)
    from_files = not from_web and len(files) == len(sources)

    words = keywords(search_term(result.get("thought_process")))
    items = []
    for rank, text in enumerate(sources, 1):
        heading = ""
        tag = ""
        if from_web:
            heading = web_link(web[rank - 1]) + "<br>"
            tag = '<span class="tag">Web</span>'
            text = text.split("\n", 1)[1] if "\n" in text else text
        elif from_files:
            info = files[rank - 1]
            heading = f'<span class="src">{html.escape(info.get("source", "unknown"))}</span><br>'
            tag = f'<span class="tag domain">{html.escape(info.get("domain", "general"))}</span>'
        preview = " ".join(text.split())[:170]
        items.append(
            '<details class="passage"><summary>'
            f'<span class="rank">{rank}</span>{tag}'
            f'<span class="preview">{highlight(preview, words)}&hellip;</span>'
            "</summary>"
            f'<div class="full">{heading}{highlight(text, words)}</div>'
            "</details>"
        )
    title = "Based on these web results" if from_web else "Based on these passages"
    return f'<div class="passages"><div class="passages-title">{title}</div>' + "".join(items) + "</div>"


def thinking_html():
    return '<div class="thinking"><i></i><i></i><i></i>Reading the documents</div>'


def notice_html(title, message):
    return f'<div class="notice"><b>{html.escape(title)}</b><span>{html.escape(message)}</span></div>'


def brand_html():
    return '<div class="brand">Enterprise RAG</div><div class="tagline">Answers from your indexed documents</div>'


def status_html(health, url):
    if health is None:
        return f'<div class="status"><i class="dot bad"></i>API not reachable at {html.escape(url)}</div>'

    checks = health[1].get("checks", {})
    down = [name for name, text in checks.items() if not text.startswith("ok")]
    if down:
        return f'<div class="status"><i class="dot warn"></i>{len(down)} of {len(checks)} services need attention</div>'
    return '<div class="status"><i class="dot ok"></i>All services running</div>'


def details_html(health):
    rows = []
    for name, text in health[1].get("checks", {}).items():
        good = text.startswith("ok")
        note = text.split(": ", 1)[1] if ": " in text else text
        rows.append(
            f'<div class="detail"><i class="dot {"ok" if good else "bad"}"></i>'
            f"<span>{SERVICE_NAMES.get(name, name)}</span><span>{html.escape(note)}</span></div>"
        )
    return "".join(rows)


def stats_html(messages, thread_id):
    results = [message["result"] for message in messages if "result" in message]
    average = f"{sum(r['seconds'] for r in results) / len(results):.1f} s" if results else "none yet"
    chat_id = thread_id[:8] if thread_id else "not started"
    rows = [("Questions answered", str(len(results)), ""), ("Average time", average, ""), ("Chat ID", chat_id, " mono")]
    body = "".join(f'<div class="fact"><span>{key}</span><b class="{extra.strip()}">{value}</b></div>' for key, value, extra in rows)
    return '<div class="facts">' + body + "</div>"


def export_markdown(messages):
    lines = ["# Chat export", ""]
    for message in messages:
        if message["role"] == "user":
            lines += [f"**You:** {message['content']}", ""]
        elif "result" in message:
            lines += [f"**Assistant:** {message['result']['answer']}", ""]
            names = sorted({item["source"] for item in message["result"].get("doc_sources") or [] if item.get("source")})
            if names:
                lines += ["Sources: " + ", ".join(names), ""]
            links = [item for item in message["result"].get("web_sources") or [] if item.get("url", "").startswith(("http://", "https://"))]
            for item in links:
                lines.append(f"- [{item['title'].replace('[', '').replace(']', '')}]({item['url']})")
            if links:
                lines.append("")
    return "\n".join(lines)


def stream_words(text):
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.02)


def render_hero(on_pick):
    st.markdown('<h1 class="hero-title">Ask the documents.</h1>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-text">Answers come from your documents first. If the documents have nothing, it searches the web and tells you. Every answer shows its sources.</p>',
        unsafe_allow_html=True,
    )
    with st.container(key="suggestions"):
        for text in SUGGESTIONS:
            st.button(text, key=text, on_click=on_pick, args=(text,))


def render_answer(index, result, show_steps, show_passages, animate=False):
    with st.container(key=f"answer_{index}"):
        if animate:
            st.write_stream(stream_words(result["answer"]))
        else:
            st.markdown(result["answer"])

    footer = (chips_html(result) if show_steps else "") + (passages_html(result) if show_passages else "")
    if footer:
        st.markdown(footer, unsafe_allow_html=True)


def show_message(index, message, show_steps, show_passages):
    if message["role"] == "user":
        with st.chat_message("user", avatar=USER_AVATAR):
            st.markdown(message["content"])
        return

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        if "error" in message:
            st.markdown(notice_html("Could not get an answer", message["error"]), unsafe_allow_html=True)
        else:
            render_answer(index, message["result"], show_steps, show_passages)