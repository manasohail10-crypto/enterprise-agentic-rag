import streamlit as st

import styles
from client import DEFAULT_URL, ApiError, ask, get_health
from components import (
    BOT_AVATAR,
    brand_html,
    details_html,
    export_markdown,
    notice_html,
    render_answer,
    render_hero,
    show_message,
    stats_html,
    status_html,
    thinking_html,
)

st.set_page_config(page_title="Enterprise RAG", page_icon=":material/menu_book:", initial_sidebar_state="expanded")
styles.apply()

state = st.session_state
state.setdefault("messages", [])
state.setdefault("thread_id", None)
state.setdefault("pending", None)


def pick(text):
    state.pending = text


def new_chat():
    state.messages = []
    state.thread_id = None


@st.cache_data(ttl=30, show_spinner=False)
def cached_health(url):
    return get_health(url)


api_url = state.get("api_url", DEFAULT_URL)
show_steps = state.get("show_steps", True)
show_passages = state.get("show_passages", True)

question = st.chat_input("Ask about security, money, health, DevOps, privacy law or AI") or state.pending
state.pending = None

if not state.messages and not question:
    render_hero(pick)

for index, message in enumerate(state.messages):
    show_message(index, message, show_steps, show_passages)

if question:
    state.messages.append({"role": "user", "content": question})
    show_message(len(state.messages) - 1, state.messages[-1], show_steps, show_passages)

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        holder = st.empty()
        holder.markdown(thinking_html(), unsafe_allow_html=True)
        try:
            result = ask(api_url, question, state.thread_id)
        except ApiError as error:
            holder.markdown(notice_html("Could not get an answer", str(error)), unsafe_allow_html=True)
            state.messages.append({"role": "assistant", "error": str(error)})
        else:
            holder.empty()
            state.thread_id = result["thread_id"]
            render_answer(len(state.messages), result, show_steps, show_passages, animate=True)
            state.messages.append({"role": "assistant", "result": result})

with st.sidebar:
    st.markdown(brand_html(), unsafe_allow_html=True)
    st.button("New chat", on_click=new_chat)

    health = cached_health(api_url)
    st.markdown(status_html(health, api_url), unsafe_allow_html=True)
    if health:
        with st.expander("Service details"):
            st.markdown(details_html(health), unsafe_allow_html=True)

    st.markdown(stats_html(state.messages, state.thread_id), unsafe_allow_html=True)

    st.toggle("Show how it searched", value=True, key="show_steps")
    st.toggle("Show passages", value=True, key="show_passages")
    st.download_button(
        "Download chat",
        data=export_markdown(state.messages),
        file_name="chat.md",
        mime="text/markdown",
        disabled=not state.messages,
    )

    with st.expander("Connection"):
        st.text_input("API address", value=DEFAULT_URL, key="api_url")