import os

os.environ.setdefault("NEMOGUARDRAILS_LLM_FRAMEWORK", "langchain")

import logfire
from nemoguardrails import LLMRails, RailsConfig
from nemoguardrails.integrations.langchain.llm_adapter import LangChainLLMAdapter

from app.gateway.client import get_langchain_llm
from app.guardrails.colang_rules import (
    RAIL_INDICATORS,
    derive_indicators,
    validate_colang,
    validate_yaml,
)

# Note: app.prompts is imported inside initialize_rails(), not here.
# app/prompts/defaults.py imports app.guardrails.colang_rules, which loads this file.
# An import at the top of this file would make a circle and crash the API at start-up.

engine = None
indicators = list(RAIL_INDICATORS)


def build_config(colang, yaml):
    return RailsConfig.from_content(colang_content=colang.text, yaml_content=yaml.text)


def initialize_rails():
    global engine, indicators

    from app.prompts import RAILS_COLANG, RAILS_YAML, load_text

    colang = load_text(RAILS_COLANG)
    yaml = load_text(RAILS_YAML)

    try:
        if colang.source == "langfuse" or yaml.source == "langfuse":
            problems = validate_colang(colang.text) + validate_yaml(yaml.text)
            if problems:
                raise ValueError("; ".join(problems))
        config = build_config(colang, yaml)
    except Exception:  # noqa: BLE001 - on purpose, any problem with the new rules means: use the local rules
        # A bad edit in Langfuse must never weaken the guardrails or stop the API from starting.
        logfire.exception(
            "guardrail rules from Langfuse are not valid, using the local rules",
            colang_version=colang.version,
            yaml_version=yaml.version,
        )
        colang = load_text(RAILS_COLANG, local_only=True)
        yaml = load_text(RAILS_YAML, local_only=True)
        config = build_config(colang, yaml)

    llm = LangChainLLMAdapter(get_langchain_llm(feature="guardrails"))
    engine = LLMRails(config, llm=llm)
    indicators = list(RAIL_INDICATORS) + derive_indicators(colang.text)

    logfire.info(
        "guardrails ready",
        colang_version=colang.version,
        colang_source=colang.source,
        yaml_version=yaml.version,
        yaml_source=yaml.source,
    )


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

    if any(indicator in content for indicator in indicators):
        logfire.info("guardrail fired", query=message[:80])
        return True, content

    return False, None