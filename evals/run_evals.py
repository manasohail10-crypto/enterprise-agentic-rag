import argparse
import json
import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("LOGFIRE_CONSOLE_MIN_LOG_LEVEL", "error")

from evals.retrieval_checks import summarize
from evals.runner import load_dataset, run_questions

RESULTS_DIR = Path(__file__).parent / "results"

MINIMUM = {"covered": 0.8, "not_covered": 0.8, "blocked": 1.0}


def print_report(rows, summary):
    print("\n" + "=" * 70)
    print("CHECKS (no AI judge)")
    print("=" * 70)
    for kind, stats in summary["by_type"].items():
        print(f"  {kind:<12} {stats['passed']:>2} of {stats['total']:<2}  ({stats['rate'] * 100:.0f}%)   needs {MINIMUM[kind] * 100:.0f}%")

    if summary["source_hit_by_domain"]:
        print("\n  Right file found, per field:")
        for domain, stats in summary["source_hit_by_domain"].items():
            print(f"    {domain:<14} {stats['hit']} of {stats['total']}")

    print(f"\n  Time per answered question: average {summary['average_seconds']} s, median {summary['median_seconds']} s")

    failed = [row for row in rows if not row["passed"]]
    if failed:
        print("\n  FAILED QUESTIONS")
        for row in failed:
            print(f"    {row['id']}  {row['question']}")
            print(f"        {row['reason']}")
            term = next((step[len("Search Term: "):] for step in row["plan"] if step.startswith("Search Term: ")), "")
            if term:
                print(f"        search term used: {term}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="max questions per type, for a quick test")
    parser.add_argument("--types", default=None, help="for example: covered,blocked")
    parser.add_argument("--no-ragas", action="store_true", help="only run the cheap checks")
    args = parser.parse_args()

    items = load_dataset(limit=args.limit, types=args.types.split(",") if args.types else None)
    print(f"Running {len(items)} questions...\n")

    rows = run_questions(items)
    summary = summarize(rows)
    print_report(rows, summary)

    ragas_scores = None
    if not args.no_ragas:
        try:
            from evals import ragas_metrics

            score_rows = getattr(ragas_metrics, "score_rows", None)
        except ImportError:
            score_rows = None

        if score_rows is None:
            print("\nRAGAS part is not written yet, skipping it.")
        else:
            ragas_scores = score_rows(rows)

    RESULTS_DIR.mkdir(exist_ok=True)
    report_file = RESULTS_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}.json"
    report = {"summary": summary, "ragas": ragas_scores, "rows": rows}
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nReport saved: {report_file}")

    below = [kind for kind, stats in summary["by_type"].items() if stats["rate"] < MINIMUM[kind]]
    if below:
        print(f"Below the minimum: {', '.join(below)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()