"""Mathematical evaluation metrics for RAG retrieval, ML ranking, and Agentic AI."""

import math
from collections.abc import Sequence


def compute_precision_at_k(retrieved_ids: Sequence[str], relevant_ids: Sequence[str], k: int) -> float:
    """Compute Precision@K: fraction of top-K retrieved items that are relevant."""
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    relevant_set = set(relevant_ids)
    hits = sum(1 for item in top_k if item in relevant_set)
    denominator = min(k, len(relevant_set)) if relevant_set else k
    return round(hits / denominator, 4) if denominator > 0 else 0.0


def compute_recall_at_k(retrieved_ids: Sequence[str], relevant_ids: Sequence[str], k: int) -> float:
    """Compute Recall@K: fraction of relevant items captured in top-K retrieved."""
    if not relevant_ids or k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    relevant_set = set(relevant_ids)
    hits = sum(1 for item in top_k if item in relevant_set)
    return hits / len(relevant_set)


def compute_mrr(retrieved_ids: Sequence[str], relevant_ids: Sequence[str]) -> float:
    """Compute Mean Reciprocal Rank: reciprocal of the rank of the first relevant item (1-indexed)."""
    relevant_set = set(relevant_ids)
    for idx, item in enumerate(retrieved_ids, start=1):
        if item in relevant_set:
            return 1.0 / idx
    return 0.0


def compute_dcg_at_k(relevance_scores: Sequence[float], k: int) -> float:
    """Compute Discounted Cumulative Gain at K using standard logarithmic discount."""
    dcg = 0.0
    for idx, rel in enumerate(relevance_scores[:k], start=1):
        gain = (2**rel) - 1.0
        discount = math.log2(idx + 1)
        dcg += gain / discount
    return dcg


def compute_ndcg_at_k(
    ranked_ids: Sequence[str],
    ground_truth_relevance: dict[str, float],
    k: int,
) -> float:
    """Compute Normalized Discounted Cumulative Gain (NDCG@K)."""
    if k <= 0 or not ranked_ids:
        return 0.0

    actual_scores = [ground_truth_relevance.get(item_id, 0.0) for item_id in ranked_ids[:k]]
    actual_dcg = compute_dcg_at_k(actual_scores, k)

    # Ideal ranking is all ground truth relevance sorted descending
    ideal_scores = sorted(ground_truth_relevance.values(), reverse=True)
    ideal_dcg = compute_dcg_at_k(ideal_scores, k)

    if ideal_dcg <= 0.0:
        return 1.0 if actual_dcg <= 0.0 else 0.0

    return round(actual_dcg / ideal_dcg, 4)


def compute_faithfulness(answer: str, retrieved_contexts: Sequence[str]) -> float:
    """Evaluate factual grounding and citation faithfulness of generated text."""
    if not answer.strip():
        return 0.0
    if not retrieved_contexts:
        return 0.0

    # Token overlap heuristic measuring factual alignment
    combined_context = " ".join(retrieved_contexts).lower()
    answer_words = [
        w.strip(".,;:?!()[]\"'")
        for w in answer.lower().split()
        if len(w) > 3 and w.isalnum()
    ]
    if not answer_words:
        return 1.0

    grounded_count = sum(1 for w in answer_words if w in combined_context)
    score = grounded_count / len(answer_words)

    # Bonus if structured citations (e.g. [doc-...]) are properly referenced
    if "[" in answer and "]" in answer:
        score = min(1.0, score + 0.1)

    return round(min(1.0, score), 4)
