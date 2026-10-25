from statistics import median

from app.config import setting


def web_is_on():
    return bool(setting.TAVILY_API_KEY) and setting.WEB_SEARCH_ENABLED


def says_unknown(answer):
    text = answer.lower()
    return "do not know" in text or "don't know" in text


def check_row(row):
    if row["error"]:
        return False, "error: " + row["error"][:80]

    kind = row["type"]
    files = sorted({item["source"] for item in row["doc_sources"]})

    if kind == "blocked":
        if row["blocked"]:
            return True, "ok"
        return False, "the guard did not block it"

    if row["blocked"]:
        return False, "the guard blocked a good question"

    if kind == "covered":
        if row["expected_source"] not in files:
            return False, f"expected {row['expected_source']}, got {files or 'no documents'}"
        if row["web_sources"]:
            return False, "used the web, but the documents have the answer"
        if says_unknown(row["answer"]):
            return False, "right file found, but the answer says it does not know"
        return True, "ok"

    if kind == "not_covered":
        if files:
            return False, f"used document passages: {files}"
        if web_is_on() and not row["web_sources"]:
            return False, "web search is on, but no web result was used"
        if not web_is_on() and not says_unknown(row["answer"]):
            return False, "web search is off, so it should say it does not know"
        return True, "ok"

    return False, f"unknown type {kind}"


def summarize(rows):
    for row in rows:
        row["passed"], row["reason"] = check_row(row)

    by_type = {}
    for row in rows:
        stats = by_type.setdefault(row["type"], {"total": 0, "passed": 0})
        stats["total"] += 1
        stats["passed"] += row["passed"]
    for stats in by_type.values():
        stats["rate"] = round(stats["passed"] / stats["total"], 2)

    by_domain = {}
    for row in rows:
        if row["type"] != "covered":
            continue
        files = {item["source"] for item in row["doc_sources"]}
        stats = by_domain.setdefault(row["domain"], {"total": 0, "hit": 0})
        stats["total"] += 1
        stats["hit"] += row["expected_source"] in files

    times = [row["seconds"] for row in rows if not row["blocked"] and not row["error"]]

    return {
        "by_type": by_type,
        "source_hit_by_domain": by_domain,
        "average_seconds": round(sum(times) / len(times), 1) if times else None,
        "median_seconds": round(median(times), 1) if times else None,
        "passed": sum(row["passed"] for row in rows),
        "total": len(rows),
    }