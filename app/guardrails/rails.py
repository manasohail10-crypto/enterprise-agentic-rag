import os

os.environ.setdefault("NEMOGUARDRAILS_LLM_FRAMEWORK", "langchain")

import logfire
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.integrations.langchain.llm_adapter import LangChainLLMAdapter

from app.gateway.client import get_langchain_llm
from app.guardrails.colang_rules import COLANG_CONTENT, RAIL_INDICATORS, YAML_CONTENT

engine = None


def initialize_rails():
    global engine
    config = RailsConfig.from_content(colang_content=COLANG_CONTENT, yaml_content=YAML_CONTENT)
    llm = LangChainLLMAdapter(get_langchain_llm(feature="guardrails"))
    engine = LLMRails(config, llm=llm)
    logfire.info("guardrails ready")


def guard(message):
    if engine is None:
        logfire.warning("guardrails not initialised, skipping the check")
        return False, None

    with logfire.span("guardrails check"):
        try:
            result = engine.generate(messages=[{"role": "user", "content": message}])
        except Exception:
            logfire.exception("guardrails failed, letting the message through")
            return False, None

    content = result.get("content", "") if isinstance(result, dict) else str(result)

    if any(indicator in content for indicator in RAIL_INDICATORS):
        logfire.info("guardrail fired", query=message[:80])
        return True, content

    return False, None