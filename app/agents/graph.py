import logfire
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.agents.nodes.planner import planner_node
from app.agents.nodes.responder import generate_node
from app.agents.nodes.retriever import retrieve_node
from app.agents.nodes.web_search import web_search_node
from app.agents.state import AgentState
from app.config import setting


def create_checkpointer():
    if not setting.POSTGRES_URI:
        logfire.warning("POSTGRES_URI not set, using in-memory checkpointer")
        return MemorySaver()

    with PostgresSaver.from_conn_string(setting.POSTGRES_URI) as saver:
        saver.setup()

    pool = ConnectionPool(
        conninfo=setting.POSTGRES_URI,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )
    pool.open(wait=True, timeout=10)

    logfire.info("postgres checkpointer ready")
    return PostgresSaver(pool)


def route_planner(state):
    if state["current_query"] == "CONVERSATIONAL":
        return "responder"
    return "retriever"


def route_retriever(state):
    if state["documents"]:
        return "responder"
    if setting.WEB_SEARCH_ENABLED and setting.TAVILY_API_KEY:
        return "web_search"
    return "responder"


def build_graph(checkpointer=None):
    if checkpointer is None:
        checkpointer = create_checkpointer()

    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("retriever", retrieve_node)
    workflow.add_node("web_search", web_search_node)
    workflow.add_node("responder", generate_node)

    workflow.add_edge(START, "planner")
    workflow.add_conditional_edges(
        "planner",
        route_planner,
        {"retriever": "retriever", "responder": "responder"},
    )
    workflow.add_conditional_edges(
        "retriever",
        route_retriever,
        {"responder": "responder", "web_search": "web_search"},
    )
    workflow.add_edge("web_search", "responder")
    workflow.add_edge("responder", END)

    return workflow.compile(checkpointer=checkpointer)