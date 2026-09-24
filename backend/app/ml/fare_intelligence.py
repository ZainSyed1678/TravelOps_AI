"""Fare intelligence and anomaly detection engine for airline route pricing."""


from app.ml.schemas import FareAnomalyRequest, FareAnomalyResponse

# Historical route pricing baselines (mean, std, median, min, max in INR)
ROUTE_PRICING_BASELINES: dict[str, dict[str, float]] = {
    "BOM-DXB": {
        "mean": 21500.0,
        "std": 4200.0,
        "median": 20800.0,
        "min": 14200.0,
        "max": 38000.0,
    },
    "DXB-BOM": {
        "mean": 21000.0,
        "std": 4000.0,
        "median": 20500.0,
        "min": 14000.0,
        "max": 37500.0,
    },
    "DEL-LHR": {
        "mean": 58000.0,
        "std": 9500.0,
        "median": 56500.0,
        "min": 42000.0,
        "max": 95000.0,
    },
    "BOM-DOH": {
        "mean": 24000.0,
        "std": 4500.0,
        "median": 23500.0,
        "min": 16500.0,
        "max": 42000.0,
    },
    "DEL-DXB": {
        "mean": 22000.0,
        "std": 4300.0,
        "median": 21200.0,
        "min": 14800.0,
        "max": 39000.0,
    },
    "BOM-SIN": {
        "mean": 26000.0,
        "std": 4800.0,
        "median": 25200.0,
        "min": 18000.0,
        "max": 46000.0,
    },
}


class FareIntelligenceService:
    """Evaluates quoted fares against historical price distributions to identify deals and surge pricing."""

    def evaluate_fare_anomaly(self, request: FareAnomalyRequest) -> FareAnomalyResponse:
        """Classify quoted fare into DEAL, NORMAL, or SURGE with confidence and recommendations."""
        route_key = f"{request.origin.upper()}-{request.destination.upper()}"
        baseline = self._get_route_baseline(route_key, request.cabin_class)

        fare = request.fare_amount
        median = baseline["median"]
        mean = baseline["mean"]
        std = baseline["std"]
        min_fare = baseline["min"]
        max_fare = baseline["max"]

        pct_diff = ((fare - median) / median) * 100.0
        z_score = (fare - mean) / max(1.0, std)

        # Classification logic
        if pct_diff <= -12.0 or z_score <= -1.0:
            classification = "DEAL"
            recommendation = (
                f"Great Value Deal: Quoted fare is {abs(pct_diff):.1f}% below route median (₹{median:,.0f}). "
                "Strong recommendation to book immediately before inventory sells out."
            )
            confidence = min(0.98, 0.70 + abs(z_score) * 0.15)
        elif pct_diff >= +18.0 or z_score >= 1.25:
            classification = "SURGE"
            recommendation = (
                f"Surge Pricing Alert: Quoted fare is {pct_diff:.1f}% above historical median (₹{median:,.0f}). "
                "Consider flexible travel dates (+/- 2 days) or flying with an alternate carrier."
            )
            confidence = min(0.96, 0.70 + z_score * 0.12)
        else:
            classification = "NORMAL"
            recommendation = (
                f"Standard Market Fare: Quoted fare is within expected route variance "
                f"({pct_diff:+.1f}% compared to historical median ₹{median:,.0f})."
            )
            confidence = 0.85

        if classification in ("SURGE", "DEAL"):
            try:
                from app.observability.metrics import record_fare_anomaly

                record_fare_anomaly(route_key)
            except Exception:
                pass

        return FareAnomalyResponse(
            route=route_key,
            fare_amount=fare,
            currency=request.currency,
            classification=classification,
            historical_median=median,
            historical_min=min_fare,
            historical_max=max_fare,
            percentage_difference=round(pct_diff, 1),
            recommendation=recommendation,
            confidence=round(confidence, 2),
        )

    def _get_route_baseline(self, route_key: str, cabin_class: str) -> dict[str, float]:
        """Fetch baseline statistics, scaling for business/first cabin classes if applicable."""
        multiplier = 1.0
        cabin_upper = cabin_class.upper()
        if cabin_upper == "BUSINESS":
            multiplier = 2.8
        elif cabin_upper == "FIRST":
            multiplier = 4.5
        elif cabin_upper == "PREMIUM_ECONOMY":
            multiplier = 1.5

        if route_key in ROUTE_PRICING_BASELINES:
            base = ROUTE_PRICING_BASELINES[route_key]
        else:
            # Fallback estimation for arbitrary international/domestic route
            base = {
                "mean": 30000.0,
                "std": 6000.0,
                "median": 29000.0,
                "min": 18000.0,
                "max": 55000.0,
            }

        return {k: round(v * multiplier, 2) for k, v in base.items()}


fare_intelligence = FareIntelligenceService()
