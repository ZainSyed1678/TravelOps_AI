"""CLI script to train and persist the Flight Ranking ML model."""

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
from app.ml.ranker import FlightRanker


def main():
    logger.info("Initializing flight ranking model training...")
    model_artifact_path = root_dir / "ml" / "models" / "flight_ranker.joblib"
    ranker = FlightRanker(model_path=model_artifact_path)
    ranker._train_baseline_model()

    print("\n" + "=" * 60)
    print("TravelOps AI Flight Ranking Model Training Complete")
    print("=" * 60)
    print(f"Model saved to: {model_artifact_path}")
    print(f"Features: {ranker.extractor.FEATURE_NAMES}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
