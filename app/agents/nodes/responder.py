import logfire
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import setting
from app.gateway.client import extract_cache_status, portkey_client
from app.prompts import ANSWER, CONVERSATION, load_prompt

MAX_CONTEXT_CHARS = 25000
WEB_NOTE = "I did not find this in the documents. This answer is based on web results:\n\n"


def log_retry(retry_state):
    logfire.warning("LLM call failed, retrying", attempt=retry_state.attempt_number)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    reraise=True,
    before_sleep=log_retry,
)
def call_llm(prompt):
    return portkey_client.chat.completions.with_raw_response.create(
        model=setting.GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )


def build_context(documents):
    context = ""
    for doc in documents:
        if len(context) + len(doc) >= MAX_CONTEXT_CHARS:
            logfire.warning("context cut to fit the token limit")
            break
        context += doc + "\n\n"
    return context


def generate_node(state):
    messages = state["messages"]
    history = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages[:-1]
    )
    question = messages[-1]["content"] if messages else ""
    web_used = "Web Search Used" in state["plan"]

    # The prompt texts now live in Langfuse (backup copies: app/prompts/defaults.py).
    if state["current_query"] == "CONVERSATIONAL":
        prompt = load_prompt(CONVERSATION, history=history, question=question)
    else:
        context = build_context(state.get("documents", []))
        source = "web search results, which are not fully trusted" if web_used else "the company documents"
        prompt = load_prompt(ANSWER, source=source, context=context, history=history, question=question)

    with logfire.span(
        "llm synthesis",
        prompt_name=prompt.name,
        prompt_version=prompt.version,
        prompt_source=prompt.source,
    ):
        raw = call_llm(prompt.text)
    response = raw.parse()
    answer = response.choices[0].message.content
    plan = list(state["plan"])

    if web_used:
        answer = WEB_NOTE + answer

    if extract_cache_status(raw) == "HIT":
        plan.append("Cache: Hit")
        status = "Cache hit, instant response"
    else:
        status = "Response generated"

    return {
        "final_answer": answer,
        "status": status,
        "plan": plan,
        "messages": [{"role": "assistant", "content": answer}],
    }