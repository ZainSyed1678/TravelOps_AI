"""Evaluation and benchmark REST API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from app.evaluation.runner import EvaluationReport, evaluation_runner

router = APIRouter()


@router.post(
    "/run",
    response_model=EvaluationReport,
    status_code=status.HTTP_200_OK,
    summary="Execute comprehensive AI evaluation benchmarks",
    description="Runs automated evaluation across RAG retrieval, ML ranking, and Agent compliance, persisting the report and checking against acceptance thresholds.",
)
async def run_evaluation_suite() -> EvaluationReport:
    """Trigger full evaluation run across RAG, ML, and Agents."""
    report = evaluation_runner.run_all()
    return report


@router.get(
    "/latest",
    response_model=EvaluationReport,
    status_code=status.HTTP_200_OK,
    summary="Retrieve latest evaluation report",
    description="Returns the most recently executed evaluation benchmark report and threshold status.",
)
async def get_latest_evaluation_report() -> EvaluationReport:
    """Retrieve the latest evaluation report from memory or disk."""
    report = evaluation_runner.get_latest_report()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No evaluation runs found. Execute /api/v1/eval/run first.",
        )
    return report


@router.get(
    "/benchmarks",
    summary="Retrieve evaluation benchmark thresholds and metrics",
    description="Returns configured acceptance thresholds for RAG, ML ranking, and Agent compliance.",
)
async def get_benchmark_thresholds() -> dict[str, Any]:
    """Retrieve configured acceptance thresholds."""
    return {
        "thresholds": [
            {
                "metric_name": k,
                "target_threshold": v[0],
                "comparison": v[1],
            }
            for k, v in evaluation_runner.DEFAULT_THRESHOLDS.items()
        ],
        "suites": ["rag_retrieval_and_synthesis", "learning_to_rank_ml", "multi_agent_safety"],
    }
