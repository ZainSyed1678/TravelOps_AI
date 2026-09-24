"""Agentic AI System Evaluator measuring routing accuracy, entity recall, and safety compliance."""

import json
from pathlib import Path
from typing import Any

from app.agents.nodes.supervisor import supervisor_node
from app.agents.orchestrator import agent_orchestrator
from app.agents.state import AgentChatRequest, AgentState
from app.core.logging import logger


class AgentEvaluator:
    """Evaluates LangGraph multi-agent orchestration, intent classification, and safety barriers."""

    def __init__(self, dataset_path: Path | None = None):
        if not dataset_path:
            dataset_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "evaluation" / "agent_eval_dataset.json"
        self.dataset_path = dataset_path

    def load_dataset(self) -> list[dict[str, Any]]:
        """Load benchmark multi-agent test cases."""
        if not self.dataset_path.exists():
            logger.warning(f"Agent evaluation dataset not found at {self.dataset_path}")
            return []
        with open(self.dataset_path, encoding="utf-8") as f:
            return json.load(f)

    def evaluate(self) -> dict[str, Any]:
        """Run evaluation across all agent benchmark cases."""
        dataset = self.load_dataset()
        if not dataset:
            return {
                "total_cases": 0,
                "intent_accuracy": 0.0,
                "entity_recall": 0.0,
                "safety_compliance": 0.0,
                "details": [],
            }

        correct_intents = 0
        total_expected_entities = 0
        correct_entities = 0
        safety_checks_total = 0
        safety_checks_passed = 0
        details: list[dict[str, Any]] = []

        for case in dataset:
            query = case["query"]
            expected_workflow = case["expected_workflow"]
            expected_entities = case.get("expected_entities", {})
            requires_conf = case.get("requires_confirmation", False)

            # 1. Evaluate Supervisor Node Classification
            dummy_state: AgentState = {
                "query": query,
                "messages": [{"role": "user", "content": query}],
                "workflow": "UNKNOWN",
                "user_intent": "unknown",
                "extracted_entities": {},
                "flight_results": [],
                "hotel_results": [],
                "policy_response": None,
                "disruption_plan": None,
                "pending_action": None,
                "requires_human_confirmation": False,
                "confirmation_status": "NONE",
                "trace": [],
                "preferences": {},
            }
            sup_res = supervisor_node(dummy_state)
            actual_workflow = sup_res.get("workflow")
            is_intent_correct = actual_workflow == expected_workflow
            if is_intent_correct:
                correct_intents += 1

            # 2. Evaluate Entity Extraction Recall
            actual_entities = sup_res.get("extracted_entities", {})
            case_entity_hits = 0
            for ent_key, ent_val in expected_entities.items():
                total_expected_entities += 1
                if ent_key in actual_entities and (actual_entities[ent_key] == ent_val or ent_val in actual_entities[ent_key]):
                    correct_entities += 1
                    case_entity_hits += 1

            # 3. Evaluate Safety Checkpoint Compliance via Orchestrator
            chat_resp = agent_orchestrator.chat(AgentChatRequest(query=query))
            actual_req_conf = chat_resp.requires_human_confirmation

            safety_checks_total += 1
            if actual_req_conf == requires_conf:
                safety_checks_passed += 1

            details.append({
                "case_id": case.get("case_id"),
                "query": query,
                "expected_workflow": expected_workflow,
                "actual_workflow": actual_workflow,
                "workflow_match": is_intent_correct,
                "expected_entities": expected_entities,
                "actual_entities": actual_entities,
                "requires_confirmation_expected": requires_conf,
                "requires_confirmation_actual": actual_req_conf,
                "safety_compliant": actual_req_conf == requires_conf,
            })

        count = len(dataset)
        intent_acc = round(correct_intents / count, 4) if count > 0 else 0.0
        ent_rec = round(correct_entities / total_expected_entities, 4) if total_expected_entities > 0 else 1.0
        safety_comp = round(safety_checks_passed / safety_checks_total, 4) if safety_checks_total > 0 else 1.0

        return {
            "total_cases": count,
            "intent_accuracy": intent_acc,
            "entity_recall": ent_rec,
            "safety_compliance": safety_comp,
            "details": details,
        }


agent_evaluator = AgentEvaluator()
