import operator
from typing import Annotated, TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[dict], operator.add]
    current_query: str
    documents: list[str]
    doc_sources: list[dict]
    web_sources: list[dict]
    plan: list[str]
    status: str
    final_answer: str