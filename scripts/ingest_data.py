"""CLI script for running batch data ingestion across all domains."""

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
from ingestion.pipelines.runner import IngestionRunner


def main():
    parser = argparse.ArgumentParser(description="TravelOps AI Data Ingestion Pipeline Runner")
    parser.add_argument(
        "--force", action="store_true", help="Force reprocessing even if document checksum matches"
    )
    args = parser.parse_args()

    logger.info("Initializing TravelOps AI Ingestion Runner...")
    runner = IngestionRunner()
    results = runner.run_all(force=args.force)

    print("\n" + "=" * 90)
    print(
        f"{'DOCUMENT TYPE':<22} | {'SOURCE':<35} | {'STATUS':<10} | {'RECORDS':<8} | {'TIME (ms)':<10}"
    )
    print("=" * 90)

    for r in results:
        print(
            f"{r.document_type.value:<22} | {r.source:<35} | {r.status:<10} | {r.records_count:<8} | {r.duration_ms:<10}"
        )

    print("=" * 90 + "\n")


if __name__ == "__main__":
    main()
