# ADR 0001: Hybrid RAG & GraphRAG Subgraph Fusion for Airline Policy Retrieval

## Status
Accepted

## Context
Commercial aviation and corporate travel policies are highly structured, relational, and conditional:
1. Cancellation penalties, change fees, and baggage rules depend strictly on fare basis codes, cabin classes, operating carrier agreements, and route jurisdictions.
2. Standard dense vector retrieval (semantic search) struggles with exact entity constraints, multi-hop rule relationships (e.g., *Is flight AI915 operated by Air India or an interline partner, and which airline's baggage policy governs leg 2?*), and subtle negation clauses.
3. Pure Knowledge Graphs provide deterministic relationship traversal but lack fuzzy natural-language understanding for colloquial queries.

## Decision
We adopted a **Hybrid GraphRAG architecture** combining:
- **Dense Vector Search**: Qdrant vector database using structure-aware chunking preserving markdown headers and table layouts, reranked by a Cross-Encoder.
- **Relational Knowledge Graph**: Neo4j graph model consisting of 12 travel domain entity types and 14 relationship types, queried using Cypher and multi-hop entity traversal (with in-memory NetworkX DiGraph fallback).
- **Fusion Synthesizer**: A grounded synthesizer node that fuses graph-extracted deterministic facts (fees, operating carriers, constraints) with vector-retrieved text passages to produce accurate answers with provenance citations and faithfulness scoring.

## Consequences
### Positive
- Resolves complex multi-hop policy dependencies that pure vector RAG misses.
- Achieved `rag_precision_at_3` of 1.00 and `rag_faithfulness` of 0.76+ in automated evaluations.
- Complete citation provenance linking each synthesized claim to source document IDs and graph entities.
- Zero-downtime fallback to NetworkX and local vector indexing if external database services are unreachable.

### Negative
- Requires maintaining dual ingestion pipelines (vector chunking + graph entity-relationship extraction).
- Slightly increased query latency (vector retrieval + graph traversal executed concurrently).
