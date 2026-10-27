"""Loads prompts from Langfuse, and falls back to the local copy when it cannot.

How it behaves:
  - Keys not set            -> uses the local prompts, never calls the internet.
  - Langfuse works          -> uses the version that has the label "production"
                               (Langfuse keeps it for 60 seconds, so changes go live within a minute).
  - Langfuse is down        -> uses the local prompts, and does not retry that prompt for 2 minutes,
                               so users are not slowed down. The prompts are also loaded once when the
                               API starts (warm_up), so a slow Langfuse is felt at start-up, not by users.
  - A bad version in Langfuse (a needed {{variable}} is missing, or a new unknown one appears)
                            -> ignores it and uses the local prompt, and writes a warning.
"""

import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import logfire

from app.config import setting
from app.prompts.defaults import DEFAULT_PROMPTS, REQUIRED_VARIABLES

COOLDOWN_SECONDS = 120
FETCH_TIMEOUT_SECONDS = 3
FETCH_RETRIES = 0

VARIABLE = re.compile(r"\{\{\s*(\w+)\s*\}\}")

_client = None
_client_lock = threading.Lock()
_down_until = {}
_last_logged = {}


class LoadedPrompt:
    """One prompt, ready to send to the model."""

    def __init__(self, text, name, version, source):
        self.text = text  # the final text
        self.name = name  # for example "rag-planner"
        self.version = version  # 0 means the local copy
        self.source = source  # "langfuse" or "local"


def langfuse_enabled():
    return bool(setting.LANGFUSE_PUBLIC_KEY and setting.LANGFUSE_SECRET_KEY)


def get_client():
    """Makes the Langfuse client once. Returns None when the keys are not set."""
    global _client
    if not langfuse_enabled():
        return None
    with _client_lock:
        if _client is None:
            from langfuse import Langfuse

            _client = Langfuse(
                public_key=setting.LANGFUSE_PUBLIC_KEY,
                secret_key=setting.LANGFUSE_SECRET_KEY,
                base_url=setting.LANGFUSE_BASE_URL,
                tracing_enabled=False,  # we only use prompt management, tracing stays in Logfire
                timeout=FETCH_TIMEOUT_SECONDS,
            )
    return _client


def fill(template, variables):
    """Puts the values into {{name}} places, in one pass.
    A value is never searched again, so a user message that contains "{{context}}" stays as plain text.
    A {{name}} that has no value is left as it is."""

    def replace(match):
        name = match.group(1)
        if name not in variables:
            return match.group(0)
        value = variables[name]
        return "" if value is None else str(value)

    return VARIABLE.sub(replace, template)


def is_usable(name, template):
    """True when the template uses exactly the variables the code sends."""
    needed = REQUIRED_VARIABLES.get(name)
    if needed is None:
        return bool(template.strip())
    used = set(VARIABLE.findall(template))
    if used != needed:
        logfire.warning(
            "prompt version ignored, its variables do not match the code",
            prompt=name,
            missing=sorted(needed - used),
            unknown=sorted(used - needed),
        )
        return False
    return True


def fetch(name):
    """Returns (template, version, source) for one prompt."""
    local = DEFAULT_PROMPTS[name]
    client = get_client()

    if client is None or time.monotonic() < _down_until.get(name, 0.0):
        return local, 0, "local"

    try:
        prompt = client.get_prompt(
            name,
            label=setting.PROMPT_LABEL,
            type="text",
            fallback=local,
            max_retries=FETCH_RETRIES,
            fetch_timeout_seconds=FETCH_TIMEOUT_SECONDS,
        )
    except Exception:  # noqa: BLE001 - on purpose, a Langfuse problem must never break a user request
        logfire.exception("could not load prompt from Langfuse, using the local one", prompt=name)
        _down_until[name] = time.monotonic() + COOLDOWN_SECONDS
        return local, 0, "local"

    if prompt.is_fallback:
        # The SDK already used our local text because Langfuse could not be reached or the prompt does not exist.
        _down_until[name] = time.monotonic() + COOLDOWN_SECONDS
        return local, 0, "local"

    if not is_usable(name, prompt.prompt):
        _down_until[name] = time.monotonic() + COOLDOWN_SECONDS
        return local, 0, "local"

    return prompt.prompt, prompt.version, "langfuse"


def note_version(name, version, source):
    """Writes one log line each time the version in use changes (not on every request)."""
    if _last_logged.get(name) != (version, source):
        _last_logged[name] = (version, source)
        # The details are inside the message text, because the console log shows only the message.
        logfire.info(
            "prompt in use: {prompt} version {version} from {source}",
            prompt=name,
            version=version,
            source=source,
            label=setting.PROMPT_LABEL,
        )


def load_prompt(name, **variables):
    """Gets a prompt and fills in its {{variables}}. Use this for prompts sent to the model."""
    template, version, source = fetch(name)
    note_version(name, version, source)
    return LoadedPrompt(fill(template, variables), name, version, source)


def load_text(name, local_only=False):
    """Gets a prompt as it is, with no filling. Use this for the guardrail rules."""
    if local_only:
        return LoadedPrompt(DEFAULT_PROMPTS[name], name, 0, "local")
    template, version, source = fetch(name)
    note_version(name, version, source)
    return LoadedPrompt(template, name, version, source)


def warm_up():
    """Loads every prompt once, in parallel, when the API starts.
    This fills the Langfuse cache, writes the versions to the log, and if Langfuse is down
    the waiting happens here (at start-up) and not during a user request."""
    names = [name for name in DEFAULT_PROMPTS if name in REQUIRED_VARIABLES]
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        results = list(pool.map(fetch, names))
    for name, (_, version, source) in zip(names, results):
        note_version(name, version, source)
    return {name: (version, source) for name, (_, version, source) in zip(names, results)}