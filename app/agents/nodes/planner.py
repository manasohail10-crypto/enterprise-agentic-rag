import logfire

from app.gateway.client import get_langchain_llm
from app.prompts import PLANNER, load_prompt

llm = get_langchain_llm(feature="planner")


def planner_node(state):
    messages = state["messages"]
    history = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages[:-1]
    )
    question = messages[-1]["content"] if messages else ""

    prompt = load_prompt(PLANNER, history=history, question=question)

    with logfire.span(
        "planner decision",
        prompt_name=prompt.name,
        prompt_version=prompt.version,
        prompt_source=prompt.source,
    ):
        decision = llm.invoke(prompt.text).content.strip()
        logfire.info("intent identified", decision=decision)

    if decision.strip("\"'. ").upper() == "CONVERSATIONAL":
        return {
            "current_query": "CONVERSATIONAL",
            "status": "Answering from the conversation",
            "plan": ["Intent: Conversational", "Retrieval: Skipped"],
        }

    query = decision or question
    return {
        "current_query": query,
        "status": f"Searching for: {query}",
        "plan": ["Intent: Technical", f"Search Term: {query}"],
    }