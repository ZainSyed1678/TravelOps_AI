"""Unified Evaluation Runner executing benchmarks and comparing against acceptance thresholds."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.core.logging import logger
from app.evaluation.agent_evaluator import agent_evaluator
from app.evaluation.rag_evaluator import rag_evaluator
from app.evaluation.ranking_evaluator import ranking_evaluator


class MetricThreshold(BaseModel):
    """Specification of benchmark acceptance threshold and result."""

    metric_name: str
    target_threshold: float
    comparison: str = ">="  # ">=", "=="
    actual_value: float
    passed: bool


class EvaluationReport(BaseModel):
    """Consolidated system-wide evaluation report across RAG, ML, and Agents."""

    run_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    overall_status: str  # PASSED, FAILED
    rag_metrics: dict[str, Any]
    ranking_metrics: dict[str, Any]
    agent_metrics: dict[str, Any]
    threshold_results: list[MetricThreshold]


class EvaluationRunner:
    """Orchestrates comprehensive AI/ML quality and compliance evaluations."""

    DEFAULT_THRESHOLDS = {
        "rag_precision_at_3": (0.60, ">="),
        "rag_mrr": (0.60, ">="),
        "rag_faithfulness": (0.70, ">="),
        "ranking_ndcg_at_3": (0.75, ">="),
        "ranking_ndcg_at_5": (0.75, ">="),
        "agent_intent_accuracy": (0.80, ">="),
        "agent_safety_compliance": (1.0, "=="),
    }

    def __init__(self, report_path: Path | None = None):
        if not report_path:
            report_path = (
                Path(__file__).resolve().parent.parent.parent.parent
                / "data"
                / "evaluation"
                / "eval_report.json"
            )
        self.report_path = report_path
        self._latest_report: EvaluationReport | None = None

    def run_all(self) -> EvaluationReport:
        """Execute all evaluation suites and generate quality audit report."""
        import uuid

        run_id = f"eval_{uuid.uuid4().hex[:10]}"
        logger.info(f"Starting unified AI evaluation run '{run_id}'...")

        # 1. Evaluate RAG retrieval & grounded synthesis
        rag_res = rag_evaluator.evaluate()

        # 2. Evaluate Learning-to-Rank flight engine
        ranking_res = ranking_evaluator.evaluate()

        # 3. Evaluate Agent state machine, routing, and safety barriers
        agent_res = agent_evaluator.evaluate()

        # 4. Check results against acceptance criteria
        checks = [
            ("rag_precision_at_3", rag_res.get("precision_at_3", 0.0)),
            ("rag_mrr", rag_res.get("mrr", 0.0)),
            ("rag_faithfulness", rag_res.get("faithfulness", 0.0)),
            ("ranking_ndcg_at_3", ranking_res.get("ndcg_at_3", 0.0)),
            ("ranking_ndcg_at_5", ranking_res.get("ndcg_at_5", 0.0)),
            ("agent_intent_accuracy", agent_res.get("intent_accuracy", 0.0)),
            ("agent_safety_compliance", agent_res.get("safety_compliance", 0.0)),
        ]

        threshold_results: list[MetricThreshold] = []
        all_passed = True

        for m_name, val in checks:
            target, comp = self.DEFAULT_THRESHOLDS[m_name]
            passed = (val >= target) if comp == ">=" else (val == target)
            if not passed:
                all_passed = False
            threshold_results.append(
                MetricThreshold(
                    metric_name=m_name,
                    target_threshold=target,
                    comparison=comp,
                    actual_value=val,
                    passed=passed,
                )
            )

        overall_status = "PASSED" if all_passed else "FAILED"

        report = EvaluationReport(
            run_id=run_id,
            timestamp=datetime.now(UTC),
            overall_status=overall_status,
            rag_metrics=rag_res,
            ranking_metrics=ranking_res,
            agent_metrics=agent_res,
            threshold_results=threshold_results,
        )

        self._latest_report = report

        # Persist report to file
        try:
            self.report_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.report_path, "w", encoding="utf-8") as f:
                json.dump(report.model_dump(mode="json"), f, indent=2)
            logger.info(f"Evaluation report successfully saved to {self.report_path}")
        except Exception as e:
            logger.warning(f"Could not persist evaluation report to file: {e}")

        logger.info(f"AI evaluation run complete. Status: {overall_status}")
        return report

    def get_latest_report(self) -> EvaluationReport | None:
        """Return the most recently executed evaluation report."""
        if self._latest_report is not None:
            return self._latest_report

        if self.report_path.exists():
            try:
                with open(self.report_path, encoding="utf-8") as f:
                    data = json.load(f)
                self._latest_report = EvaluationReport(**data)
                return self._latest_report
            except Exception as e:
                logger.warning(f"Failed to read evaluation report from {self.report_path}: {e}")

        return None


evaluation_runner = EvaluationRunner()
