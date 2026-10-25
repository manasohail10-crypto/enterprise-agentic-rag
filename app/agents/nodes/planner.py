import logfire

from app.gateway.client import get_langchain_llm

llm = get_langchain_llm(feature="planner")


def planner_node(state):
    messages = state["messages"]
    history = "\n".join(
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
        for m in messages[:-1]
    )
    question = messages[-1]["content"] if messages else ""

    prompt = f"""You are the planner of a document question answering assistant.

CONVERSATION HISTORY:
{history}

LATEST MESSAGE:
{question}

Decide what to do:
1. Reply with exactly: CONVERSATIONAL
   when the latest message is a greeting, thanks or small talk, or when it only asks to change or repeat what was already said in the conversation history.
   Examples: "explain that again in simpler words", "make it shorter", "summarize your last answer", "what is my name".
2. Otherwise the message asks for new facts that need the documents. Reply with one short, clear search query.
   If the message uses words like "it" or "that", write the query so that it makes sense on its own, using the conversation history.
   If the message also contains a new question, always choose this option.

Reply with ONLY the word CONVERSATIONAL or the search query."""

    with logfire.span("planner decision"):
        decision = llm.invoke(prompt).content.strip()
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