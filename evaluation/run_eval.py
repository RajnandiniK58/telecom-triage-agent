"""Evaluate the triage agent against hand-labelled complaints.

Run from the project root (calls the real Gemini model, so it needs GEMINI_API_KEY):

    python -m evaluation.run_eval
    python -m evaluation.run_eval --limit 5            # quick check
    python -m evaluation.run_eval --tag hinglish       # only cases with a tag
    python -m evaluation.run_eval --ids net-01,sim-02  # re-run specific cases
    python -m evaluation.run_eval --delay 20           # slower, for tight rate limits

Tickets where the LLM failed and the fallback decision was used are reported
separately and are NOT counted as right or wrong, because they say something about
your network/API, not about the agent's judgement.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = HERE / "cases.json"
DEFAULT_OUT = HERE / "results" / "latest.json"

PRIORITIES = ["P0", "P1", "P2"]


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def evaluate(
    cases: list[dict[str, Any]],
    predict: Callable[[dict[str, Any]], dict[str, Any]],
    delay: float = 0.0,
    on_result: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Run ``predict`` on every case and score it.

    ``predict(case)`` must return a dict with category, priority, next_tool and
    needs_human_review (the shape of the API response).
    """
    results: list[dict[str, Any]] = []
    for i, case in enumerate(cases):
        started = time.perf_counter()
        try:
            pred = predict(case)
            error = None
        except Exception as exc:  # keep going; one bad case must not stop the run
            pred, error = {}, f"{type(exc).__name__}: {exc}"
        latency = time.perf_counter() - started

        fallback = bool(pred.get("needs_human_review")) or error is not None
        result = {
            "id": case["id"],
            "tags": case.get("tags", []),
            "message": case["message"],
            "expected_category": case["expected_category"],
            "expected_priority": case["expected_priority"],
            "expected_tools": case["expected_tools"],
            "pred_category": pred.get("category"),
            "pred_priority": pred.get("priority"),
            "pred_tool": pred.get("next_tool"),
            "fallback": fallback,
            "error": error,
            "latency_s": round(latency, 2),
        }
        if not fallback:
            result["category_ok"] = result["pred_category"] == result["expected_category"]
            result["priority_ok"] = result["pred_priority"] == result["expected_priority"]
            result["tool_ok"] = result["pred_tool"] in result["expected_tools"]
            result["all_ok"] = (
                result["category_ok"] and result["priority_ok"] and result["tool_ok"]
            )
        results.append(result)
        if on_result:
            on_result(result)
        if delay and i < len(cases) - 1:
            time.sleep(delay)
    return results


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:5.1f}%" if den else "  n/a "


def summarise(results: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in results if not r["fallback"]]
    n = len(scored)
    summary: dict[str, Any] = {
        "total_cases": len(results),
        "scored": n,
        "fallbacks": len(results) - n,
        "category_accuracy": sum(r["category_ok"] for r in scored) / n if n else None,
        "priority_accuracy": sum(r["priority_ok"] for r in scored) / n if n else None,
        "tool_accuracy": sum(r["tool_ok"] for r in scored) / n if n else None,
        "all_correct": sum(r["all_ok"] for r in scored) / n if n else None,
        "avg_latency_s": round(sum(r["latency_s"] for r in results) / len(results), 2)
        if results
        else None,
    }

    # Per expected category
    by_cat: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        by_cat[r["expected_category"]].append(r)
    summary["by_category"] = {
        c: {"n": len(rs), "category_correct": sum(x["category_ok"] for x in rs)}
        for c, rs in sorted(by_cat.items())
    }

    # Per tag
    by_tag: dict[str, list[dict]] = defaultdict(list)
    for r in scored:
        for t in r["tags"]:
            by_tag[t].append(r)
    summary["by_tag"] = {
        t: {
            "n": len(rs),
            "category_correct": sum(x["category_ok"] for x in rs),
            "priority_correct": sum(x["priority_ok"] for x in rs),
        }
        for t, rs in sorted(by_tag.items())
    }

    # Priority confusion matrix: expected -> predicted
    matrix = {e: Counter() for e in PRIORITIES}
    for r in scored:
        matrix[r["expected_priority"]][r["pred_priority"]] += 1
    summary["priority_confusion"] = {e: dict(c) for e, c in matrix.items()}
    return summary


def print_report(results: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    n = summary["scored"]
    print("\n" + "=" * 64)
    print(f"Cases: {summary['total_cases']}   scored: {n}   fallback/errors: {summary['fallbacks']}")
    print("=" * 64)
    if not n:
        print("No case was scored. Check the API key / network and try again.")
        return
    if summary["fallbacks"] > 0.1 * summary["total_cases"]:
        print("WARNING: many cases fell back (rate limit or network). Re-run those with --ids.")

    def line(label: str, key: str) -> None:
        correct = round(summary[key] * n)
        print(f"{label:<22}{_pct(correct, n)}   ({correct}/{n})")

    line("Category accuracy", "category_accuracy")
    line("Priority accuracy", "priority_accuracy")
    line("Tool accuracy", "tool_accuracy")
    line("All three correct", "all_correct")
    print(f"Avg latency           {summary['avg_latency_s']}s")

    print("\nBy expected category (category correct)")
    for cat, d in summary["by_category"].items():
        print(f"  {cat:<18}{d['category_correct']}/{d['n']}")

    print("\nBy tag (category / priority correct)")
    for tag, d in summary["by_tag"].items():
        print(f"  {tag:<14}{d['category_correct']}/{d['n']}   {d['priority_correct']}/{d['n']}")

    print("\nPriority confusion (rows = expected, columns = predicted)")
    print("        " + "".join(f"{p:>5}" for p in PRIORITIES))
    for e in PRIORITIES:
        row = summary["priority_confusion"][e]
        print(f"  {e:<6}" + "".join(f"{row.get(p, 0):>5}" for p in PRIORITIES))

    wrong = [r for r in results if not r["fallback"] and not r["all_ok"]]
    if wrong:
        print(f"\nMismatches ({len(wrong)})")
        for r in wrong:
            bits = []
            if not r["category_ok"]:
                bits.append(f"category {r['pred_category']} (expected {r['expected_category']})")
            if not r["priority_ok"]:
                bits.append(f"priority {r['pred_priority']} (expected {r['expected_priority']})")
            if not r["tool_ok"]:
                bits.append(f"tool {r['pred_tool']} (expected one of {', '.join(r['expected_tools'])})")
            print(f"  [{r['id']}] {r['message'][:70]}")
            print(f"      " + "; ".join(bits))

    failed = [r for r in results if r["fallback"]]
    if failed:
        print(f"\nNot scored (fallback or error): {', '.join(r['id'] for r in failed)}")

    print("\nREADME snippet")
    print(f"| Metric | Result |\n|---|---|")
    print(f"| Category accuracy | {summary['category_accuracy']:.0%} |")
    print(f"| Priority accuracy | {summary['priority_accuracy']:.0%} |")
    print(f"| Tool selection accuracy | {summary['tool_accuracy']:.0%} |")
    print(f"| Evaluated on | {n} hand-labelled complaints |")


def _predict_with_agent(case: dict[str, Any]) -> dict[str, Any]:
    from app.agent import run_triage
    from app.schemas import TriageRequest

    request = TriageRequest(
        customer_id=case["customer_id"],
        message=case["message"],
        location=case.get("location"),
    )
    return run_triage(request).model_dump(mode="json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the telecom triage agent.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, help="only run the first N cases")
    parser.add_argument("--tag", help="only run cases with this tag")
    parser.add_argument("--ids", help="comma-separated case ids to run")
    parser.add_argument(
        "--delay", type=float, default=13.0,
        help="seconds between calls; free-tier gemini-2.5-flash allows ~5 requests/minute",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if args.tag:
        cases = [c for c in cases if args.tag in c.get("tags", [])]
    if args.ids:
        wanted = {i.strip() for i in args.ids.split(",")}
        cases = [c for c in cases if c["id"] in wanted]
    if args.limit:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No cases selected.")

    # Fail fast with a clear message if the key is missing.
    from app.llm import LLMConfigError, get_llm

    try:
        get_llm()
    except LLMConfigError as exc:
        raise SystemExit(str(exc))

    print(f"Running {len(cases)} cases (delay {args.delay}s between calls)...\n")

    def progress(r: dict[str, Any]) -> None:
        if r["fallback"]:
            status = "FALLBACK"
        else:
            status = "ok" if r["all_ok"] else "MISMATCH"
        print(f"  {r['id']:<9}{status:<10}{r['latency_s']}s")

    results = evaluate(cases, _predict_with_agent, delay=args.delay, on_result=progress)
    summary = summarise(results)
    print_report(results, summary)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "summary": summary,
                "results": results,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nSaved details to {args.out}")


if __name__ == "__main__":
    main()
