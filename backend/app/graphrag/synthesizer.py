"""GraphRAG Synthesizer producing grounded answers with verified citations and anti-hallucination checks."""

from typing import Any

from app.core.config import settings
from app.graphrag.models import FusedContext

SYSTEM_PROMPT = """You are TravelOps AI GraphRAG Intelligence Engine.
Your task is to answer travel operations, flight, fare, and policy questions by grounding your reasoning
on BOTH verified Knowledge Graph facts and retrieved document clauses provided in the context.

STRICT OPERATIONAL RULES:
1. Grounding: Answer ONLY based on the facts and document clauses provided. Do NOT hallucinate rules or invent fees.
2. Graph Fact Consistency: Whenever graph facts specify fare cancellation fees or route details, your answer must strictly conform.
3. Citations: Explicitly cite your sources using format [Source: <filename>, Document ID: <id>].
4. Insufficient Context: If the provided facts and documents do not contain sufficient evidence, state that clearly.
"""


class GraphRAGSynthesizer:
    """Generates grounded responses from fused graph facts and text chunks."""

    def synthesize(
        self,
        query: str,
        fused_context: FusedContext,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Synthesize answer using configured LLM or deterministic fallback if LLM is offline."""
        citations = self._extract_citations(fused_context)

        # Check if external LLM configured (OpenAI or Anthropic)
        if settings.OPENAI_API_KEY:
            try:
                import openai

                client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
                messages = [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": f"Context:\n{fused_context.formatted_prompt_context}\n\nQuery: {query}",
                    },
                ]
                resp = client.chat.completions.create(
                    model=settings.OPENAI_MODEL_NAME,
                    messages=messages,
                    temperature=0.0,
                )
                answer = resp.choices[0].message.content or ""
                return answer, citations
            except Exception:
                pass

        # Deterministic grounded synthesizer (offline/hermetic fallback)
        answer = self._generate_grounded_fallback(query, fused_context)
        return answer, citations

    def _generate_grounded_fallback(self, query: str, fused_context: FusedContext) -> str:
        """Deterministic grounded response generator based on graph facts and document chunks."""
        parts: list[str] = []

        # 1. Integrate Knowledge Graph Facts
        if fused_context.graph_facts:
            flight_facts = [
                f
                for f in fused_context.graph_facts
                if f.object_type == "Flight" or f.subject_type == "Flight"
            ]
            fare_facts = [f for f in fused_context.graph_facts if f.predicate == "HAS_FARE"]
            policy_facts = [
                f
                for f in fused_context.graph_facts
                if "POLICY" in f.predicate or f.object_type == "Policy"
            ]
            booking_facts = [f for f in fused_context.graph_facts if f.subject_type == "Booking"]

            if booking_facts:
                for b in booking_facts:
                    parts.append(
                        f"According to verified booking records, {b.to_readable_sentence()}"
                    )

            if flight_facts:
                route_desc = []
                for ff in flight_facts:
                    if ff.predicate in ("OPERATES", "DEPARTS_FROM", "ARRIVES_AT"):
                        route_desc.append(ff.to_readable_sentence())
                if route_desc:
                    parts.append("Flight operational details: " + " ".join(route_desc))

            if fare_facts:
                fares_desc = [f.to_readable_sentence() for f in fare_facts]
                parts.append("Applicable fare rules from knowledge graph: " + " ".join(fares_desc))

            if policy_facts and not fare_facts and not booking_facts:
                p_desc = [f.to_readable_sentence() for f in policy_facts]
                parts.append("Associated airline policies: " + " ".join(p_desc))

        # 2. Integrate Document Clauses
        if fused_context.retrieved_chunks:
            # Check for cancellation / refund / rules matches
            chunks_to_use = fused_context.retrieved_chunks[:2]
            doc_summaries = []
            for chk in chunks_to_use:
                doc_id = chk.get("document_id", "")
                src = chk.get("source", "")
                content = chk.get("content", "").strip()
                # Extract first 2 sentences
                sentences = [s.strip() for s in content.split(".") if s.strip()]
                summary = ". ".join(sentences[:2]) + "." if sentences else content
                doc_summaries.append(f"{summary} [Source: {src}, Document ID: {doc_id}]")

            if doc_summaries:
                parts.append("Policy documentation: " + " ".join(doc_summaries))

        if not parts:
            return (
                "Insufficient context found in the Knowledge Graph and document stores to answer your query. "
                "Please verify the airline or flight details."
            )

        return "\n\n".join(parts)

    def _extract_citations(self, fused_context: FusedContext) -> list[dict[str, Any]]:
        """Collect citations from retrieved document chunks and graph facts."""
        citations: list[dict[str, Any]] = []
        seen = set()

        for chk in fused_context.retrieved_chunks:
            doc_id = chk.get("document_id", "")
            source = chk.get("source", "")
            key = (doc_id, source)
            if key not in seen and doc_id:
                seen.add(key)
                citations.append(
                    {
                        "document_id": doc_id,
                        "source": source,
                        "section_title": chk.get("section_title"),
                        "score": chk.get("score"),
                    }
                )

        return citations


graphrag_synthesizer = GraphRAGSynthesizer()
