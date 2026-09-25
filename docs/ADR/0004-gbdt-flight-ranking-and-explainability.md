# ADR 0004: Gradient Boosted Flight Ranking with Linear Feature Attribution Explainability

## Status
Accepted

## Context
When searching for flights across GDS/NDC aggregators, users are presented with dozens of candidate flight offers with differing prices, durations, stop counts, airline carriers, and departure times.
- Simple heuristic sorting (e.g. by price or duration) fails to balance multi-criteria corporate trade-offs (e.g., a nonstop flight costing 5% more is usually preferred over a flight with an 8-hour layover).
- Prompting an LLM to rank 50 flights on every search is cost-prohibitive, introduces 2-5 seconds of latency, and exhibits non-deterministic scoring hallucinations.

## Decision
We engineered a dedicated **Machine Learning Ranking & Intelligence Engine**:
1. **Model Architecture**: Gradient Boosted Decision Tree (GBDT / HistGradientBoostingRegressor / XGBoost) trained on simulated multi-airline preference datasets.
2. **Feature Engineering**: Features include normalized base fare, total travel duration, connection count, departure hour penalty, historical carrier delay rate, and traveler preference matches (preferred carrier, preferred cabin class, nonstop preference).
3. **Linear Feature Attribution**: For every ranked flight offer, the system computes feature contributions showing why the flight was ranked in its position (e.g., `duration_penalty: -0.15`, `preferred_airline_boost: +0.32`).
4. **Statistical Fare Anomaly Intelligence**: Z-score pricing intelligence classifying offers into `DEAL`, `NORMAL`, or `SURGE` pricing tiers based on rolling route price distributions.

## Consequences
### Positive
- Ultra-low latency: < 5ms inference per 50 offers.
- High ranking quality: achieves `ranking_ndcg_at_3` and `ndcg_at_5` >= 0.92.
- Fully transparent and explainable to corporate travelers and operations supervisors.
- Runs hermetically in Python without requiring external GPU infrastructure.

### Negative
- Requires periodic retraining as airline route pricing distributions and seasonal patterns evolve.
