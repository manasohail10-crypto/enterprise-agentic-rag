import json
import time
import uuid
from pathlib import Path

from app.main import ask, start

DATASET_FILE = Path(__file__).parent / "dataset.json"
PAUSE_SECONDS = 2


def load_dataset(limit=None, types=None):
    items = json.loads(DATASET_FILE.read_text(encoding="utf-8"))

    if types:
        items = [item for item in items if item["type"] in types]

    if limit:
        counts = {}
        kept = []
        for item in items:
            counts[item["type"]] = counts.get(item["type"], 0) + 1
            if counts[item["type"]] <= limit:
                kept.append(item)
        items = kept

    return items


def run_questions(items):
    start()
    rows = []

    for number, item in enumerate(items, 1):
        started = time.perf_counter()
        row = {**item, "answer": "", "contexts": [], "doc_sources": [], "web_sources": [], "plan": [], "blocked": False, "error": None}

        try:
            result = ask(item["question"], thread_id=str(uuid.uuid4()))
            row.update(
                answer=result["answer"] or "",
                contexts=result.get("sources", []),
                doc_sources=result.get("doc_sources", []),
                web_sources=result.get("web_sources", []),
                plan=result.get("thought_process") or [],
                blocked=result["blocked"],
            )
        except Exception as error:
            row["error"] = f"{type(error).__name__}: {error}"

        row["seconds"] = round(time.perf_counter() - started, 1)
        rows.append(row)
        print(f"[{number}/{len(items)}] {row['id']} {row['type']:<12} {row['seconds']:>5} s  {item['question'][:60]}")

        if number < len(items):
            time.sleep(PAUSE_SECONDS)

    return rows