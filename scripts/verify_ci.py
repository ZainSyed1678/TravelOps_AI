"""Comprehensive local CI pipeline verification runner.

Executes all continuous integration stages locally before pushing to git:
1. Lint & Code Quality (ruff)
2. Backend Test Suite (pytest)
3. AI/ML Quality & Safety Benchmarks (EvaluationRunner in strict mode)
4. Frontend Typecheck & Production Build (npm run build)
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


class Colors:
    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    END = "\033[0m"


def run_stage(name: str, cmd: list[str], cwd: Path | None = None) -> tuple[bool, float, str]:
    """Execute a single CI pipeline stage."""
    print(f"\n{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}Stage: {name}{Colors.END}")
    print(f"Command: {' '.join(cmd)}")
    print(f"Directory: {cwd or ROOT_DIR}")
    print(f"{Colors.CYAN}{'-'*70}{Colors.END}")

    start = time.time()
    try:
        res = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
            shell=sys.platform == "win32",
        )
        duration = time.time() - start
        success = res.returncode == 0

        # Print output preview
        if res.stdout:
            stdout_lines = res.stdout.strip().splitlines()
            for line in stdout_lines[-15:]:
                print(f"  {line}")
        if not success and res.stderr:
            print(f"{Colors.RED}STDERR Error:{Colors.END}")
            for line in res.stderr.strip().splitlines()[-10:]:
                print(f"  {line}")

        status_text = f"{Colors.GREEN}[PASSED]{Colors.END}" if success else f"{Colors.RED}[FAILED]{Colors.END}"
        print(f"Result: {status_text} ({duration:.2f}s)")
        return success, duration, "" if success else (res.stderr or res.stdout)

    except Exception as exc:
        duration = time.time() - start
        print(f"{Colors.RED}Exception occurred: {exc}{Colors.END}")
        return False, duration, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser(description="TravelOps AI Local CI Pipeline Verification Runner")
    parser.add_argument("--skip-eval", action="store_true", help="Skip AI evaluation benchmarks")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend build step")
    args = parser.parse_args()

    # Enable ANSI colors on Windows terminal if needed
    os.system("")

    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("=" * 70)
    print("      TRAVELOPS AI - LOCAL CONTINUOUS INTEGRATION VERIFIER")
    print("=" * 70)
    print(f"{Colors.END}")

    stages: list[tuple[str, list[str], Path | None]] = [
        ("Linting (Ruff Check)", ["ruff", "check", "."], ROOT_DIR),
        ("Backend Pytest Suite", ["pytest", "backend/tests", "-q"], ROOT_DIR),
    ]

    if not args.skip_eval:
        stages.append((
            "AI/ML Quality Benchmarks",
            [sys.executable, "scripts/run_evaluations.py", "--strict"],
            ROOT_DIR,
        ))

    if not args.skip_frontend and FRONTEND_DIR.exists():
        stages.append((
            "Frontend Typecheck & Build",
            ["npm", "run", "build"],
            FRONTEND_DIR,
        ))

    results = []
    overall_success = True

    pipeline_start = time.time()
    for name, cmd, cwd in stages:
        success, duration, error = run_stage(name, cmd, cwd)
        results.append((name, success, duration, error))
        if not success:
            overall_success = False
            break

    total_duration = time.time() - pipeline_start

    print(f"\n{Colors.BOLD}{Colors.HEADER}")
    print("=" * 70)
    print("                 CI VERIFICATION SUMMARY")
    print("=" * 70)
    print(f"{Colors.END}")
    print(f"{'STAGE NAME':<35} | {'STATUS':<10} | {'DURATION'}")
    print("-" * 70)

    for name, success, dur, _ in results:
        status_col = f"{Colors.GREEN}PASS{Colors.END}" if success else f"{Colors.RED}FAIL{Colors.END}"
        print(f"{name:<35} | {status_col:<19} | {dur:.2f}s")

    print("-" * 70)
    overall_str = f"{Colors.GREEN}ALL STAGES PASSED{Colors.END}" if overall_success else f"{Colors.RED}PIPELINE FAILED{Colors.END}"
    print(f"Overall Result: {overall_str} (Total: {total_duration:.2f}s)\n")

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())
