import uuid

import logfire

from app.agents.graph import build_graph
from app.config import setting
from app.guardrails import guard, initialize_rails
from app.prompts import warm_up
from app.request_context import set_request_id
from app.services.health.connection_checker import check_all_connections, log_connection_summary

agent = None


def start(strict=False):
    global agent
    if agent is not None:
        return

    logfire.configure(token=setting.LOGFIRE_TOKEN, send_to_logfire="if-token-present")

    initialize_rails()
    warm_up()
    graph = build_graph()

    results = check_all_connections()
    healthy = log_connection_summary(results)
    if strict and not healthy:
        failed = [name for name, result in results.items() if not result.healthy]
        raise RuntimeError(f"unhealthy services: {', '.join(failed)}")

    agent = graph


def ask(question, thread_id=None):
    if agent is None:
        raise RuntimeError("call start() before ask()")

    thread_id = thread_id or str(uuid.uuid4())
    request_id = str(uuid.uuid4())
    set_request_id(request_id)

    with logfire.span("ask", request_id=request_id, thread_id=thread_id):
        blocked, reply = guard(question)
        if blocked:
            return {
                "question": question,
                "answer": reply,
                "thought_process": ["Intent: Guardrails Fired", "Retrieval: Skipped"],
                "status": "Blocked by guardrails",
                "sources": [],
                "doc_sources": [],
                "web_sources": [],
                "blocked": True,
                "thread_id": thread_id,
                "request_id": request_id,
            }

        output = agent.invoke(
            {
                "messages": [{"role": "user", "content": question}],
                "current_query": question,
                "documents": [],
                "doc_sources": [],
                "web_sources": [],
                "plan": ["Start"],
                "status": "Starting",
            },
            config={"configurable": {"thread_id": thread_id}},
        )

        return {
            "question": question,
            "answer": output.get("final_answer"),
            "thought_process": output.get("plan"),
            "status": output.get("status"),
            "sources": output.get("documents", []),
            "doc_sources": output.get("doc_sources", []),
            "web_sources": output.get("web_sources", []),
            "blocked": False,
            "thread_id": thread_id,
            "request_id": request_id,
        }


if __name__ == "__main__":
    start()
    chat_id = str(uuid.uuid4())

    while True:
        text = input("\nYou: ").strip()
        if text.lower() in ("exit", "quit"):
            break
        if not text:
            continue
        result = ask(text, chat_id)
        print("Bot:", result["answer"])
        print("Steps:", " > ".join(result["thought_process"] or []))
        for item in result["web_sources"]:
            print("Web:", item["title"], "-", item["url"])