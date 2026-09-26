"""CLI script to execute TravelOps AI evaluation benchmarks across RAG, ML, and Agents."""

import argparse
import sys
from pathlib import Path

# Add project root and backend to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.logging import logger
from app.evaluation.runner import EvaluationRunner


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TravelOps AI Evaluation Benchmarks")
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Path to save evaluation report JSON (defaults to data/evaluation/eval_report.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero status if any acceptance threshold fails",
    )
    args = parser.parse_args()

    report_path = Path(args.output) if args.output else None
    runner = EvaluationRunner(report_path=report_path)

    logger.info("Executing comprehensive AI/ML quality evaluation suite...")
    report = runner.run_all()

    print("\n" + "=" * 70)
    print("                  TRAVELOPS AI EVALUATION REPORT")
    print("=" * 70)
    print(f"Run ID:        {report.run_id}")
    print(f"Timestamp:     {report.timestamp.isoformat()}")
    print(
        f"Overall Status: [{'PASS' if report.overall_status == 'PASSED' else 'FAIL'}] {report.overall_status}"
    )
    print("-" * 70)
    print(f"{'METRIC NAME':<28} | {'TARGET':<8} | {'ACTUAL':<8} | {'STATUS'}")
    print("-" * 70)

    for item in report.threshold_results:
        symbol = "[PASS]" if item.passed else "[FAIL]"
        comp_str = f"{item.comparison} {item.target_threshold:.2f}"
        print(f"{item.metric_name:<28} | {comp_str:<8} | {item.actual_value:<8.4f} | {symbol}")

    print("=" * 70)
    print(f"Report written to: {runner.report_path}")
    print("=" * 70 + "\n")

    if args.strict and report.overall_status != "PASSED":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
