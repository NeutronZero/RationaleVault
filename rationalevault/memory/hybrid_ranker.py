from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from rationalevault.memory.models import MemoryRecord
from rationalevault.memory.ranking import HybridRetrievalScore, compute_retrieval_score
from rationalevault.projections.bm25 import BM25IndexState
from rationalevault.projections.graph import GraphState


@dataclass(frozen=True)
class RankingConfig:
    lexical_weight: float = 0.5
    graph_weight: float = 0.5
    priority_weight: float = 0.2
    recency_weight: float = 0.1


class KnowledgeGraphScorer:
    """Computes a connectivity score for a memory record within the Knowledge Graph."""

    @staticmethod
    def score(record: MemoryRecord, query_tokens: list[str], graph_state: GraphState) -> tuple[float, list[str], int]:
        # 1. Identify matched graph nodes matching query tokens
        matched_nodes = []
        for node_id, node in graph_state.nodes.items():
            node_title_lower = node.title.lower()
            if any(token in node_title_lower or any(token in tag.lower() for tag in node.tags) for token in query_tokens):
                matched_nodes.append(node_id)

        if not matched_nodes:
            return 0.0, [], 0

        # 2. Map memory record to graph nodes (via direct ID match or event provenance overlap)
        record_nodes = []
        record_seqs = {int(eid) for eid in record.source_event_ids if eid.isdigit()}
        for node_id in graph_state.nodes:
            if node_id == record.id:
                record_nodes.append(node_id)
            else:
                node_seqs = set(graph_state.provenance.get(node_id, []))
                if record_seqs & node_seqs:
                    record_nodes.append(node_id)

        if not record_nodes:
            return 0.0, matched_nodes, 0

        # 3. Calculate traversal distance score (direct = 1.0, 1-hop neighbor = 0.5)
        best_score = 0.0
        best_depth = 999

        for r_node in record_nodes:
            if r_node in matched_nodes:
                best_score = max(best_score, 1.0)
                best_depth = min(best_depth, 0)
                continue

            # Check neighbors
            neighbors = set()
            for edge in graph_state.adjacency.get(r_node, []):
                neighbors.add(edge.target)
            for edge in graph_state.reverse_adjacency.get(r_node, []):
                neighbors.add(edge.source)

            matching_neighbors = neighbors & set(matched_nodes)
            if matching_neighbors:
                best_score = max(best_score, 0.5)
                best_depth = min(best_depth, 1)

        depth = best_depth if best_depth != 999 else 0
        return best_score, matched_nodes, depth


class SignalFusionRanker:
    """Stateless fusion engine that normalizes and blends retrieval signals deterministically."""

    @staticmethod
    def rank(
        candidates: list[MemoryRecord],
        query_tokens: list[str],
        bm25_index: BM25IndexState,
        graph_state: Optional[GraphState] = None,
        config: RankingConfig = RankingConfig()
    ) -> list[tuple[MemoryRecord, HybridRetrievalScore]]:
        if not candidates:
            return []

        # 1. Compute raw scores
        raw_lexical: dict[str, float] = {}
        raw_graph: dict[str, float] = {}
        matched_nodes_map: dict[str, list[str]] = {}
        depth_map: dict[str, int] = {}

        for r in candidates:
            raw_lexical[r.id] = bm25_index.score(r.id, query_tokens)
            if graph_state:
                g_score, nodes, depth = KnowledgeGraphScorer.score(r, query_tokens, graph_state)
                raw_graph[r.id] = g_score
                matched_nodes_map[r.id] = nodes
                depth_map[r.id] = depth
            else:
                raw_graph[r.id] = 0.0
                matched_nodes_map[r.id] = []
                depth_map[r.id] = 0

        # 2. Min-max normalization (0 to 1) across the candidate set
        max_lex = max(raw_lexical.values()) if raw_lexical else 0.0
        min_lex = min(raw_lexical.values()) if raw_lexical else 0.0
        lex_range = max_lex - min_lex

        max_graph = max(raw_graph.values()) if raw_graph else 0.0
        min_graph = min(raw_graph.values()) if raw_graph else 0.0
        graph_range = max_graph - min_graph

        norm_lexical: dict[str, float] = {}
        norm_graph: dict[str, float] = {}

        for r in candidates:
            if lex_range > 0.0:
                norm_lexical[r.id] = (raw_lexical[r.id] - min_lex) / lex_range
            else:
                norm_lexical[r.id] = 1.0 if raw_lexical[r.id] > 0.0 else 0.0

            if graph_range > 0.0:
                norm_graph[r.id] = (raw_graph[r.id] - min_graph) / graph_range
            else:
                norm_graph[r.id] = 1.0 if raw_graph[r.id] > 0.0 else 0.0

        # 3. Blend signals with RankingConfig and priority/recency
        scored_candidates: list[tuple[MemoryRecord, HybridRetrievalScore]] = []
        for r in candidates:
            # Base retrieval score properties (priority, recency, confidence)
            base_score = compute_retrieval_score(r)
            
            # Weighted combination of normalized lexical and graph scores
            fused_score = (
                config.lexical_weight * norm_lexical[r.id]
                + config.graph_weight * norm_graph[r.id]
                + config.priority_weight * base_score.priority
                + config.recency_weight * base_score.recency
                + base_score.lifecycle_penalty
            )

            hybrid_score = HybridRetrievalScore(
                total=fused_score,
                lexical=raw_lexical[r.id],
                lexical_normalized=norm_lexical[r.id],
                graph=raw_graph[r.id],
                graph_normalized=norm_graph[r.id],
                priority=base_score.priority,
                recency=base_score.recency,
                references=base_score.references,
                confidence=base_score.confidence,
                lifecycle_penalty=base_score.lifecycle_penalty,
                matched_nodes=matched_nodes_map[r.id],
                matched_lexical_terms=query_tokens,
                traversal_depth=depth_map[r.id]
            )
            scored_candidates.append((r, hybrid_score))

        # 4. Deterministic stable sorting (total score DESC -> priority DESC -> record ID ASC)
        def sort_key(item: tuple[MemoryRecord, HybridRetrievalScore]) -> tuple[float, float, str]:
            rec, hs = item
            return (-hs.total, -hs.priority, rec.id)

        scored_candidates.sort(key=sort_key)
        return scored_candidates
