"""Travel ML Flight Ranker Evaluator computing NDCG@K and ranking metrics."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logging import logger
from app.evaluation.metrics import compute_ndcg_at_k
from app.ml.ranker import flight_ranker
from app.ml.schemas import UserPreferences
from app.providers.schemas import ProviderFlightOffer


class RankingEvaluator:
    """Evaluates Learning-to-Rank flight utility models against benchmark scenarios."""

    def __init__(self, dataset_path: Path | None = None):
        if not dataset_path:
            dataset_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "evaluation" / "ranking_eval_dataset.json"
        self.dataset_path = dataset_path

    def load_dataset(self) -> list[dict[str, Any]]:
        """Load ranking scenarios with candidate offers and ground truth relevance."""
        if not self.dataset_path.exists():
            logger.warning(f"Ranking evaluation dataset not found at {self.dataset_path}")
            return []
        with open(self.dataset_path, encoding="utf-8") as f:
            return json.load(f)

    def evaluate(self) -> dict[str, Any]:
        """Rank candidate offers for each scenario and compute NDCG@3 and NDCG@5."""
        dataset = self.load_dataset()
        if not dataset:
            return {
                "total_scenarios": 0,
                "ndcg_at_3": 0.0,
                "ndcg_at_5": 0.0,
                "pairwise_accuracy": 0.0,
                "details": [],
            }

        ndcg3_scores: list[float] = []
        ndcg5_scores: list[float] = []
        pairwise_correct: int = 0
        total_pairs: int = 0
        details: list[dict[str, Any]] = []

        for scen in dataset:
            prefs_dict = scen.get("preferences", {})
            prefs = UserPreferences(**prefs_dict)
            ground_truth = scen.get("ground_truth_relevance", {})

            # Reconstruct ProviderFlightOffer objects
            offers: list[ProviderFlightOffer] = []
            for o in scen.get("candidate_offers", []):
                offers.append(
                    ProviderFlightOffer(
                        id=o["id"],
                        provider_name=o.get("provider_name", "MOCK"),
                        flight_number=o["flight_number"],
                        airline_code=o["airline_code"],
                        airline_name=o["airline_name"],
                        origin_airport=o["origin_airport"],
                        destination_airport=o["destination_airport"],
                        departure_time=datetime.fromisoformat(o["departure_time"]),
                        arrival_time=datetime.fromisoformat(o["arrival_time"]),
                        duration_minutes=o["duration_minutes"],
                        stops=o.get("stops", 0),
                        base_fare=o["base_fare"],
                        taxes=o["taxes"],
                        total_price=o["total_price"],
                        currency=o.get("currency", "INR"),
                        is_refundable=o.get("is_refundable", False),
                    )
                )

            # Rank offers with ML engine
            ranked = flight_ranker.rank_flight_offers(offers, preferences=prefs)
            ranked_ids = [item.offer.id for item in ranked]

            n3 = compute_ndcg_at_k(ranked_ids, ground_truth, k=3)
            n5 = compute_ndcg_at_k(ranked_ids, ground_truth, k=5)
            ndcg3_scores.append(n3)
            ndcg5_scores.append(n5)

            # Compute pairwise rank concordance
            for i in range(len(ranked_ids)):
                for j in range(i + 1, len(ranked_ids)):
                    id_a, id_b = ranked_ids[i], ranked_ids[j]
                    rel_a = ground_truth.get(id_a, 0.0)
                    rel_b = ground_truth.get(id_b, 0.0)
                    if rel_a != rel_b:
                        total_pairs += 1
                        if rel_a > rel_b:
                            pairwise_correct += 1

            details.append({
                "scenario_id": scen.get("scenario_id"),
                "name": scen.get("name"),
                "ranked_ids": ranked_ids,
                "ndcg_at_3": n3,
                "ndcg_at_5": n5,
            })

        count = len(dataset)
        pairwise_acc = round(pairwise_correct / total_pairs, 4) if total_pairs > 0 else 1.0

        return {
            "total_scenarios": count,
            "ndcg_at_3": round(sum(ndcg3_scores) / count, 4),
            "ndcg_at_5": round(sum(ndcg5_scores) / count, 4),
            "pairwise_accuracy": pairwise_acc,
            "details": details,
        }


ranking_evaluator = RankingEvaluator()
