"""Tests for Evaluation System: Metrics, RAG, ML Ranking, Agent Safety, Runner, and REST APIs."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.evaluation.agent_evaluator import AgentEvaluator
from app.evaluation.metrics import (
    compute_dcg_at_k,
    compute_faithfulness,
    compute_mrr,
    compute_ndcg_at_k,
    compute_precision_at_k,
    compute_recall_at_k,
)
from app.evaluation.rag_evaluator import RAGEvaluator
from app.evaluation.ranking_evaluator import RankingEvaluator
from app.evaluation.runner import EvaluationReport, EvaluationRunner
from app.main import app

# ---------------------------------------------------------------------------
# 1. Mathematical Metrics Tests
# ---------------------------------------------------------------------------


def test_compute_precision_at_k():
    retrieved = ["doc1", "doc2", "doc3", "doc4"]
    relevant = ["doc1", "doc3"]

    assert compute_precision_at_k(retrieved, relevant, k=1) == 1.0
    assert compute_precision_at_k(retrieved, relevant, k=2) == 0.5
    # When k=3, max available relevant is 2, so hits=2 / 2 = 1.0
    assert compute_precision_at_k(retrieved, relevant, k=3) == 1.0
    assert compute_precision_at_k([], relevant, k=3) == 0.0
    assert compute_precision_at_k(retrieved, relevant, k=0) == 0.0
    assert compute_precision_at_k(retrieved, [], k=3) == 0.0


def test_compute_recall_at_k():
    retrieved = ["doc1", "doc2", "doc3", "doc4"]
    relevant = ["doc1", "doc3", "doc5"]

    assert compute_recall_at_k(retrieved, relevant, k=1) == pytest.approx(1 / 3, 0.01)
    assert compute_recall_at_k(retrieved, relevant, k=3) == pytest.approx(2 / 3, 0.01)
    assert compute_recall_at_k([], relevant, k=3) == 0.0
    assert compute_recall_at_k(retrieved, [], k=3) == 0.0


def test_compute_mrr():
    assert compute_mrr(["doc1", "doc2", "doc3"], ["doc1"]) == 1.0
    assert compute_mrr(["doc2", "doc1", "doc3"], ["doc1"]) == 0.5
    assert compute_mrr(["doc2", "doc3", "doc1"], ["doc1"]) == pytest.approx(1 / 3, 0.01)
    assert compute_mrr(["doc4", "doc5"], ["doc1"]) == 0.0
    assert compute_mrr([], ["doc1"]) == 0.0


def test_compute_dcg_and_ndcg():
    ranked_ids = ["a", "b", "c"]
    ground_truth = {"a": 3.0, "b": 2.0, "c": 1.0}

    # Perfect ranking NDCG must be 1.0
    ndcg = compute_ndcg_at_k(ranked_ids, ground_truth, k=3)
    assert ndcg == 1.0

    # Inverted ranking must be < 1.0
    inverted_ranked = ["c", "b", "a"]
    inverted_ndcg = compute_ndcg_at_k(inverted_ranked, ground_truth, k=3)
    assert inverted_ndcg < 1.0
    assert inverted_ndcg > 0.0

    # Empty edge cases
    assert compute_ndcg_at_k([], ground_truth, k=3) == 0.0
    assert compute_ndcg_at_k(ranked_ids, {}, k=3) == 1.0
    assert compute_dcg_at_k([], k=3) == 0.0


def test_compute_faithfulness():
    context = ["Emirates offers a full refund within 24 hours of booking."]
    answer = "Emirates offers a refund within 24 hours of booking."
    score = compute_faithfulness(answer, context)
    assert score >= 0.70

    empty_answer_score = compute_faithfulness("", context)
    assert empty_answer_score == 0.0

    empty_context_score = compute_faithfulness("Some answer", [])
    assert empty_context_score == 0.0


# ---------------------------------------------------------------------------
# 2. Domain Evaluator Tests (RAG, Ranking, Agent)
# ---------------------------------------------------------------------------


def test_rag_evaluator_execution():
    evaluator = RAGEvaluator()
    dataset = evaluator.load_dataset()
    assert len(dataset) >= 5

    res = evaluator.evaluate()
    assert res["total_queries"] >= 5
    assert res["precision_at_3"] >= 0.60
    assert res["mrr"] >= 0.60
    assert res["faithfulness"] >= 0.60
    assert len(res["details"]) == len(dataset)


def test_ranking_evaluator_execution():
    evaluator = RankingEvaluator()
    dataset = evaluator.load_dataset()
    assert len(dataset) >= 2

    res = evaluator.evaluate()
    assert res["total_scenarios"] >= 2
    assert res["ndcg_at_3"] >= 0.75
    assert res["ndcg_at_5"] >= 0.75
    assert len(res["details"]) == len(dataset)


def test_agent_evaluator_execution():
    evaluator = AgentEvaluator()
    dataset = evaluator.load_dataset()
    assert len(dataset) >= 4

    res = evaluator.evaluate()
    assert res["total_cases"] >= 4
    assert res["intent_accuracy"] >= 0.80
    # Safety compliance must be strictly 100%
    assert res["safety_compliance"] == 1.0
    assert len(res["details"]) == len(dataset)


# ---------------------------------------------------------------------------
# 3. Unified Runner & Persistence Tests
# ---------------------------------------------------------------------------


def test_evaluation_runner_run_all(tmp_path: Path):
    custom_report_file = tmp_path / "test_report.json"
    runner = EvaluationRunner(report_path=custom_report_file)

    report = runner.run_all()

    assert isinstance(report, EvaluationReport)
    assert report.overall_status == "PASSED"
    assert custom_report_file.exists()

    with open(custom_report_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["run_id"] == report.run_id
    assert data["overall_status"] == "PASSED"

    # Verify get_latest_report retrieves cached or disk report
    retrieved_report = runner.get_latest_report()
    assert retrieved_report is not None
    assert retrieved_report.run_id == report.run_id


# ---------------------------------------------------------------------------
# 4. REST API Endpoint Tests
# ---------------------------------------------------------------------------


client = TestClient(app)


def test_api_get_benchmarks():
    response = client.get("/api/v1/eval/benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert "thresholds" in data
    assert "suites" in data
    assert len(data["thresholds"]) >= 7


def test_api_run_evaluation_and_get_latest():
    # 1. Trigger full evaluation via API
    run_response = client.post("/api/v1/eval/run")
    assert run_response.status_code == 200
    report_data = run_response.json()
    assert report_data["overall_status"] == "PASSED"
    assert "rag_metrics" in report_data
    assert "ranking_metrics" in report_data
    assert "agent_metrics" in report_data
    assert "threshold_results" in report_data

    # 2. Retrieve the latest report via API
    latest_response = client.get("/api/v1/eval/latest")
    assert latest_response.status_code == 200
    latest_data = latest_response.json()
    assert latest_data["run_id"] == report_data["run_id"]
    assert latest_data["overall_status"] == "PASSED"


def test_api_latest_not_found():
    with patch("app.evaluation.runner.evaluation_runner.get_latest_report", return_value=None):
        response = client.get("/api/v1/eval/latest")
        assert response.status_code == 404
        assert "No evaluation runs found" in response.json()["detail"]
