#!/usr/bin/env python3
"""
Run evaluation on a set of questions with expected answers.

Usage:
  python scripts/run_eval.py [--questions tests/eval_questions.json]
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--questions",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tests",
            "eval_questions.json",
        ),
        help="Path to eval_questions.json",
    )
    args = parser.parse_args()

    with open(args.questions, "r", encoding="utf-8") as f:
        questions = json.load(f)

    from src.core.orchestrator import process_query

    passed = 0
    failed = 0
    for i, item in enumerate(questions):
        q = item["question"]
        expected = item.get("expected_contains", [])
        print(f"\n[{i + 1}/{len(questions)}] {q[:60]}...")
        try:
            response = process_query(q)
            found = [e for e in expected if e.lower() in response.lower()]
            if found:
                passed += 1
                print(f"  PASS (found: {found})")
            else:
                failed += 1
                print(f"  FAIL (expected any of: {expected})")
                print(f"  Response: {response[:200]}...")
        except Exception as e:
            failed += 1
            print(f"  ERROR: {e}")

    total = passed + failed
    print(f"\n--- Results: {passed}/{total} passed ({100 * passed / total if total else 0:.1f}%)")


if __name__ == "__main__":
    main()
