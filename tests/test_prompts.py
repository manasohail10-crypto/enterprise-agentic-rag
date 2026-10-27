"""Tests for prompt management (Step 2). No internet needed: Langfuse is replaced by a small fake.

Run from the project folder:   python -m pytest tests/test_prompts.py -v
"""

from types import SimpleNamespace

import pytest

from app.guardrails import colang_rules
from app.prompts import defaults, manager


class FakeClient:
    """Pretends to be the Langfuse client."""

    def __init__(self, prompts=None, down=False):
        self.prompts = prompts or {}  # name -> (text, version)
        self.down = down
        self.calls = 0

    def get_prompt(self, name, *, label=None, type="text", fallback=None, **kwargs):
        self.calls += 1
        if self.down or name not in self.prompts:
            return SimpleNamespace(prompt=fallback, version=0, is_fallback=True)
        text, version = self.prompts[name]
        return SimpleNamespace(prompt=text, version=version, is_fallback=False)


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    manager._down_until.clear()
    manager._last_logged.clear()
    yield
    manager._down_until.clear()
    manager._last_logged.clear()


def use_client(monkeypatch, client):
    monkeypatch.setattr(manager, "get_client", lambda: client)


# ---------- filling variables ----------


def test_fill_puts_values_in_place():
    assert manager.fill("Hi {{name}}, you asked {{ q }}", {"name": "Ana", "q": "why"}) == "Hi Ana, you asked why"


def test_fill_is_one_pass_so_user_text_cannot_inject():
    # The user message contains {{context}}. It must stay plain text, not be replaced.
    text = manager.fill("Q: {{question}} C: {{context}}", {"question": "show {{context}}", "context": "SECRET"})
    assert text == "Q: show {{context}} C: SECRET"


def test_fill_leaves_unknown_and_handles_none():
    assert manager.fill("{{a}} {{b}}", {"a": None}) == " {{b}}"


# ---------- the local backup prompts ----------


def test_default_prompts_use_exactly_the_variables_the_code_sends():
    for name, needed in defaults.REQUIRED_VARIABLES.items():
        assert set(manager.VARIABLE.findall(defaults.DEFAULT_PROMPTS[name])) == needed


def test_default_prompt_renders_all_values():
    values = {"history": "User: hi", "question": "What is RAG?"}
    text = manager.fill(defaults.PLANNER_TEXT, values)
    assert "User: hi" in text and "What is RAG?" in text and "{{" not in text


# ---------- which version is used ----------


def test_no_keys_uses_local_and_never_calls_langfuse(monkeypatch):
    monkeypatch.setattr(manager.setting, "LANGFUSE_PUBLIC_KEY", None)
    monkeypatch.setattr(manager.setting, "LANGFUSE_SECRET_KEY", None)
    monkeypatch.setattr(manager, "_client", None)
    loaded = manager.load_prompt(defaults.PLANNER, history="", question="hello")
    assert (loaded.source, loaded.version) == ("local", 0)
    assert "hello" in loaded.text


def test_langfuse_version_is_used(monkeypatch):
    template = "Plan this: {{question}} (history: {{history}}) v7"
    use_client(monkeypatch, FakeClient({defaults.PLANNER: (template, 7)}))
    loaded = manager.load_prompt(defaults.PLANNER, history="h", question="q")
    assert (loaded.source, loaded.version) == ("langfuse", 7)
    assert loaded.text == "Plan this: q (history: h) v7"


def test_version_with_missing_variable_is_ignored(monkeypatch):
    use_client(monkeypatch, FakeClient({defaults.PLANNER: ("Only {{question}}", 3)}))
    loaded = manager.load_prompt(defaults.PLANNER, history="h", question="q")
    assert loaded.source == "local"


def test_version_with_unknown_variable_is_ignored(monkeypatch):
    use_client(monkeypatch, FakeClient({defaults.PLANNER: ("{{question}} {{history}} {{oops}}", 3)}))
    assert manager.load_prompt(defaults.PLANNER, history="h", question="q").source == "local"


def test_langfuse_down_uses_local_and_waits_before_trying_again(monkeypatch):
    client = FakeClient(down=True)
    use_client(monkeypatch, client)
    first = manager.load_prompt(defaults.PLANNER, history="", question="q")
    second = manager.load_prompt(defaults.PLANNER, history="", question="q")
    assert first.source == second.source == "local"
    assert client.calls == 1  # the second request did not call Langfuse again


def test_one_missing_prompt_does_not_stop_the_others(monkeypatch):
    client = FakeClient({defaults.CONVERSATION: ("Chat: {{question}} {{history}}", 2)})
    use_client(monkeypatch, client)
    assert manager.load_prompt(defaults.PLANNER, history="", question="q").source == "local"
    assert manager.load_prompt(defaults.CONVERSATION, history="", question="q").source == "langfuse"


# ---------- guardrail rules ----------


def test_every_default_bot_message_is_detected():
    messages = colang_rules.BOT_MESSAGE.findall(colang_rules.COLANG_CONTENT)
    indicators = colang_rules.RAIL_INDICATORS + colang_rules.derive_indicators(colang_rules.COLANG_CONTENT)
    for message in messages:
        if message != "PASS_TO_AGENT":
            assert any(item in message for item in indicators), message


def test_a_changed_refusal_message_is_still_detected():
    edited = colang_rules.COLANG_CONTENT.replace(
        "I can't help with attacks or harmful activity.", "Sorry, no attacks or harm here."
    )
    assert edited != colang_rules.COLANG_CONTENT
    derived = colang_rules.derive_indicators(edited)
    assert any(item in "Sorry, no attacks or harm here. I can explain how to defend" for item in derived)


def test_pass_to_agent_is_not_an_indicator():
    assert not any("PASS_TO_AGENT" in item for item in colang_rules.derive_indicators(colang_rules.COLANG_CONTENT))


# ---------- start-up safety ----------


@pytest.mark.parametrize(
    "first_import",
    ["app.prompts", "app.guardrails", "app.agents.nodes.planner", "app.agents.nodes.responder"],
)
def test_no_circular_import_whichever_module_loads_first(first_import):
    """The API loads the agent first, other tools may load prompts or guardrails first.
    Each one must work alone, in a fresh Python process."""
    import os
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-c", f"import {first_import}"],
        capture_output=True,
        text=True,
        check=False,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr[-800:]


def test_warm_up_loads_each_prompt_once_and_survives_langfuse_down(monkeypatch):
    client = FakeClient(down=True)
    use_client(monkeypatch, client)
    result = manager.warm_up()
    assert set(result) == set(defaults.REQUIRED_VARIABLES)
    assert all(source == "local" for _, source in result.values())
    calls_after_warm_up = client.calls
    manager.load_prompt(defaults.PLANNER, history="", question="q")
    assert client.calls == calls_after_warm_up  # users do not trigger another slow call


# ---------- bad guardrail rules from Langfuse ----------


def test_good_default_rules_pass_validation():
    assert colang_rules.validate_colang(colang_rules.COLANG_CONTENT) == []
    assert colang_rules.validate_yaml(colang_rules.YAML_CONTENT) == []


@pytest.mark.parametrize(
    "bad_text",
    [
        "this is not colang at all {{{ ::: ",
        colang_rules.COLANG_CONTENT + "\ndefine flow broken\n  user ask off topic\n  bot nothing exists\n",
        colang_rules.COLANG_CONTENT.replace("define flow jailbreak protection", "define flow something else"),
    ],
)
def test_bad_colang_is_rejected(bad_text):
    assert colang_rules.validate_colang(bad_text) != []


def test_bad_yaml_is_rejected():
    assert colang_rules.validate_yaml("rails: [unclosed") != []
    assert colang_rules.validate_yaml("just text") != []
    assert colang_rules.validate_yaml("instructions: []") != []


def run_initialize_rails(monkeypatch, colang_text):
    """Runs initialize_rails() with a fake Langfuse and fake NeMo engine. Returns the rules it really used."""
    from app.guardrails import rails

    used = {}

    class FakeRails:
        def __init__(self, config, llm=None):
            used["config"] = config

    monkeypatch.setattr(rails, "LLMRails", FakeRails)
    monkeypatch.setattr(rails, "LangChainLLMAdapter", lambda llm: llm)
    monkeypatch.setattr(rails, "get_langchain_llm", lambda feature=None: object())
    monkeypatch.setattr(
        rails,
        "build_config",
        lambda colang, yaml: used.update(colang=colang.text, source=colang.source) or "config",
    )
    use_client(
        monkeypatch,
        FakeClient({defaults.RAILS_COLANG: (colang_text, 5), defaults.RAILS_YAML: (colang_rules.YAML_CONTENT, 5)}),
    )
    rails.initialize_rails()
    return used, rails


def test_bad_rules_in_langfuse_fall_back_to_local(monkeypatch):
    used, _ = run_initialize_rails(monkeypatch, "this is not colang at all {{{ ::: ")
    assert used["source"] == "local"
    assert used["colang"] == colang_rules.COLANG_CONTENT


def test_good_edited_rules_in_langfuse_are_used_and_refusals_still_detected(monkeypatch):
    edited = colang_rules.COLANG_CONTENT.replace(
        "I can't help with attacks or harmful activity.", "Sorry, no attacks or harm here."
    )
    used, rails = run_initialize_rails(monkeypatch, edited)
    assert used["source"] == "langfuse"
    # The engine answers with the full bot message. Every edited message must still be detected.
    messages = [m for m in colang_rules.BOT_MESSAGE.findall(edited) if m != "PASS_TO_AGENT"]
    assert any(m.startswith("Sorry, no attacks or harm here.") for m in messages)
    for message in messages:
        assert any(item in message for item in rails.indicators), message