import sys

from app.config import setting
from app.prompts.defaults import DEFAULT_PROMPTS
from app.prompts.manager import get_client


def run_seed(force=False):
    """Uploads every prompt. Returns a dict like {"rag-planner": "created", ...}."""
    from langfuse.api import NotFoundError

    client = get_client()
    if client is None:
        sys.exit("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY are not set. Add them to .env first.")

    label = setting.PROMPT_LABEL
    results = {}

    for name, text in DEFAULT_PROMPTS.items():
        existing = None
        try:
            existing = client.get_prompt(name, label=label, type="text", cache_ttl_seconds=0, max_retries=0)
        except NotFoundError:
            pass  # not there yet, we create it below
        # Any other error (wrong keys, no internet) stops the script here, so we never create by mistake.

        if existing is not None and not force:
            same = existing.prompt == text
            results[name] = "already there, same text" if same else "already there, different text (kept)"
            continue

        created = client.create_prompt(
            name=name,
            prompt=text,
            labels=[label],
            type="text",
            commit_message="Seed from app/prompts/defaults.py",
        )
        results[name] = f"created version {created.version}"

    return results


def main():
    force = "--force" in sys.argv
    print(f"Langfuse: {setting.LANGFUSE_BASE_URL}  label: {setting.PROMPT_LABEL}  force: {force}")
    for name, result in run_seed(force).items():
        print(f"  {name:24} {result}")


if __name__ == "__main__":
    main()