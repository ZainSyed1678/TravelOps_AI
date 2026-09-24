"""Flight ranking engine utilizing Gradient Boosting (XGBoost/sklearn) and explainability."""

from pathlib import Path

import joblib
import numpy as np

from app.core.logging import logger
from app.ml.features import FlightFeatureExtractor, feature_extractor
from app.ml.schemas import FeatureImpact, RankedFlightOffer, UserPreferences
from app.providers.schemas import ProviderFlightOffer


class FlightRanker:
    """Learning-to-Rank flight options engine with feature attribution explainability."""

    def __init__(
        self,
        extractor: FlightFeatureExtractor | None = None,
        model_path: Path | None = None,
    ):
        self.extractor = extractor or feature_extractor
        self.model_path = model_path or (
            Path(__file__).resolve().parents[3] / "ml" / "models" / "flight_ranker.joblib"
        )
        self.model = None
        self._load_or_train_model()

    def _load_or_train_model(self) -> None:
        """Load persisted model artifact if present, or train and save a baseline model."""
        if self.model_path.exists():
            try:
                self.model = joblib.load(self.model_path)
                logger.info(f"Loaded trained flight ranker model from {self.model_path}")
                return
            except Exception as exc:
                logger.warning(f"Could not load model from {self.model_path}: {exc}")

        # Train a robust baseline model
        self._train_baseline_model()

    def _train_baseline_model(self) -> None:
        """Train a gradient boosted regressor on synthetic historical flight choice data."""
        logger.info("Training baseline flight ranking model...")
        np.random.seed(42)
        n_samples = 1500

        # Features: [price_ratio, duration_ratio, stops, dep_conv, arr_conv, reputation, is_refundable, pref_match]
        price_ratio = np.random.uniform(0.6, 1.8, n_samples)
        duration_ratio = np.random.uniform(1.0, 2.5, n_samples)
        stops = np.random.choice([0, 1, 2], p=[0.55, 0.35, 0.10], size=n_samples)
        dep_conv = np.random.uniform(0.3, 1.0, n_samples)
        arr_conv = np.random.uniform(0.3, 1.0, n_samples)
        reputation = np.random.uniform(0.7, 0.95, n_samples)
        is_refundable = np.random.choice([0.0, 1.0], p=[0.6, 0.4], size=n_samples)
        pref_match = np.random.choice([0.0, 1.0], p=[0.8, 0.2], size=n_samples)

        X = np.column_stack(
            [
                price_ratio,
                duration_ratio,
                stops,
                dep_conv,
                arr_conv,
                reputation,
                is_refundable,
                pref_match,
            ]
        )

        # Ground truth utility formula (simulating traveler choice behavior)
        # Higher is better: penalize high price & long duration & stops; reward convenience & reputation
        utility = (
            100.0
            - (price_ratio - 1.0) * 35.0
            - (duration_ratio - 1.0) * 25.0
            - stops * 20.0
            + (dep_conv - 0.5) * 18.0
            + (arr_conv - 0.5) * 10.0
            + (reputation - 0.8) * 20.0
            + is_refundable * 8.0
            + pref_match * 15.0
            + np.random.normal(0, 3.0, n_samples)
        )
        y = np.clip(utility, 0.0, 100.0)

        # Train with XGBoost if available, else sklearn GradientBoostingRegressor
        try:
            import xgboost as xgb

            model = xgb.XGBRegressor(
                n_estimators=60,
                max_depth=4,
                learning_rate=0.08,
                random_state=42,
            )
            model.fit(X, y)
            self.model = model
            logger.info("Trained XGBoost flight ranking model.")
        except Exception:
            from sklearn.ensemble import GradientBoostingRegressor

            model = GradientBoostingRegressor(
                n_estimators=50,
                max_depth=4,
                learning_rate=0.08,
                random_state=42,
            )
            model.fit(X, y)
            self.model = model
            logger.info("Trained Scikit-Learn GradientBoostingRegressor flight ranking model.")

        # Persist model
        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(self.model, self.model_path)
            logger.info(f"Persisted flight ranker model artifact to {self.model_path}")
        except Exception as exc:
            logger.warning(f"Failed to persist model artifact: {exc}")

    def rank_flight_offers(
        self,
        offers: list[ProviderFlightOffer],
        preferences: UserPreferences | None = None,
    ) -> list[RankedFlightOffer]:
        """Score, explain, and rank flight offers according to traveler utility."""
        if not offers:
            return []

        prefs = preferences or UserPreferences()
        X = self.extractor.extract_batch_features(offers, preferences=prefs)

        raw_scores = self.model.predict(X)

        # Apply preference calibration
        adjusted_scores: list[float] = []
        for i, raw_score in enumerate(raw_scores):
            score = float(raw_score)
            price_ratio = X[i, 0]
            duration_ratio = X[i, 1]
            stops = X[i, 2]
            pref_match = X[i, 7]

            # Price sensitivity adjustment
            if prefs.price_sensitivity > 1.0 and price_ratio > 1.0:
                score -= (price_ratio - 1.0) * (prefs.price_sensitivity - 1.0) * 15.0
            elif prefs.price_sensitivity > 1.0 and price_ratio < 1.0:
                score += (1.0 - price_ratio) * (prefs.price_sensitivity - 1.0) * 15.0

            # Duration sensitivity adjustment
            if prefs.duration_sensitivity > 1.0:
                score -= (duration_ratio - 1.0) * (prefs.duration_sensitivity - 1.0) * 12.0

            # Strict non-stop preference penalty
            if prefs.prefer_nonstop and stops > 0:
                score -= stops * 12.0

            if pref_match > 0.5:
                score += 8.0

            adjusted_scores.append(float(np.clip(score, 5.0, 99.0)))

        # Build explainability score breakdown for each offer
        ranked_items: list[RankedFlightOffer] = []
        prices = [o.total_price for o in offers]
        median_price = float(np.median(prices))

        for idx, (offer, final_score) in enumerate(zip(offers, adjusted_scores, strict=True)):
            breakdown = self._generate_score_breakdown(
                offer=offer,
                features=X[idx],
                median_price=median_price,
                preferences=prefs,
            )
            ranked_items.append(
                RankedFlightOffer(
                    rank=0,  # Assigned after sorting
                    score=round(final_score, 1),
                    offer=offer,
                    score_breakdown=breakdown,
                )
            )

        # Sort descending by score
        ranked_items.sort(key=lambda r: r.score, reverse=True)

        # Assign 1-indexed ranks
        for rank, item in enumerate(ranked_items, start=1):
            item.rank = rank

        return ranked_items

    def _generate_score_breakdown(
        self,
        offer: ProviderFlightOffer,
        features: np.ndarray,
        median_price: float,
        preferences: UserPreferences,
    ) -> list[FeatureImpact]:
        """Generate human-readable feature attribution explanations."""
        impacts: list[FeatureImpact] = []
        price = offer.total_price
        stops = int(features[2])
        dep_conv = features[3]
        reputation = features[5]
        is_refundable = features[6]
        pref_match = features[7]

        # 1. Stops impact
        if stops == 0:
            impacts.append(
                FeatureImpact(
                    feature="Stops",
                    impact=+18.0,
                    explanation="Direct non-stop flight minimizes travel time and risk of layover delays.",
                )
            )
        else:
            impacts.append(
                FeatureImpact(
                    feature="Stops",
                    impact=-15.0 * stops,
                    explanation=f"{stops} stop(s) significantly increases total journey duration.",
                )
            )

        # 2. Price impact
        pct_diff = ((price - median_price) / median_price) * 100.0
        if pct_diff <= -10.0:
            impacts.append(
                FeatureImpact(
                    feature="Fare Price",
                    impact=+14.0,
                    explanation=f"Very competitive fare ({abs(pct_diff):.0f}% below route median).",
                )
            )
        elif pct_diff >= +15.0:
            impacts.append(
                FeatureImpact(
                    feature="Fare Price",
                    impact=-16.0,
                    explanation=f"Premium fare ({pct_diff:.0f}% higher than route median).",
                )
            )
        else:
            impacts.append(
                FeatureImpact(
                    feature="Fare Price",
                    impact=+4.0,
                    explanation="Fair market price close to route average.",
                )
            )

        # 3. Schedule Convenience
        if dep_conv >= 0.90:
            impacts.append(
                FeatureImpact(
                    feature="Departure Schedule",
                    impact=+10.0,
                    explanation="Prime departure window (convenient morning or early evening schedule).",
                )
            )
        elif dep_conv <= 0.35:
            impacts.append(
                FeatureImpact(
                    feature="Departure Schedule",
                    impact=-12.0,
                    explanation="Redeye or inconvenient late-night departure hour.",
                )
            )

        # 4. Carrier Reputation
        if reputation >= 0.90:
            impacts.append(
                FeatureImpact(
                    feature="Airline Rating",
                    impact=+8.0,
                    explanation=f"Top-tier carrier rating ({offer.airline_code}) with strong on-time record.",
                )
            )

        # 5. Refundability
        if is_refundable > 0.5:
            impacts.append(
                FeatureImpact(
                    feature="Refundability",
                    impact=+6.0,
                    explanation="Refundable ticket provides booking flexibility in case of changes.",
                )
            )

        # 6. Preferred Airline
        if pref_match > 0.5:
            impacts.append(
                FeatureImpact(
                    feature="Preferred Carrier",
                    impact=+10.0,
                    explanation=f"Matches your preferred airline preference ({preferences.preferred_airline}).",
                )
            )

        return impacts


flight_ranker = FlightRanker()
