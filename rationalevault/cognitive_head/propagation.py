from __future__ import annotations
from rationalevault.cognitive_head.belief import Belief
from rationalevault.cognitive_head.assessment import EvidenceAssessment
from rationalevault.cognitive_head.config import ReasoningConfig

class PropagationEngine:
    @staticmethod
    def propagate_beliefs(
        beliefs: list[Belief],
        concept_id_to_belief_id: dict[str, str],
        support_graph: dict[str, list[str]],
        config: ReasoningConfig = ReasoningConfig()
    ) -> list[Belief]:
        # Clean up support graph to only include nodes that exist in our beliefs
        valid_concepts = set(concept_id_to_belief_id.keys())
        
        # Build adjacency lists and in-degree counts for topological sort
        adj: dict[str, list[str]] = {cid: [] for cid in valid_concepts}
        in_degree: dict[str, int] = {cid: 0 for cid in valid_concepts}
        
        for src, targets in support_graph.items():
            if src not in valid_concepts:
                continue
            for tgt in targets:
                if tgt not in valid_concepts:
                    continue
                # src supports tgt -> tgt depends on src
                adj[src].append(tgt)
                in_degree[tgt] += 1
                
        # Kahn's algorithm for topological sorting and cycle detection
        queue = [cid for cid, deg in in_degree.items() if deg == 0]
        topo_order = []
        
        while queue:
            # Sort queue to ensure deterministic order (order independence)
            queue.sort()
            curr = queue.pop(0)
            topo_order.append(curr)
            for neighbor in adj[curr]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        # Check for cycles
        if len(topo_order) != len(valid_concepts):
            # Cycle detected. Terminate propagation.
            return beliefs

        # Map concept_id to Belief object for easy updates
        belief_map: dict[str, Belief] = {}
        for b in beliefs:
            for cid, bid in concept_id_to_belief_id.items():
                if bid == b.belief_id:
                    belief_map[cid] = b
                    break

        # List of parents for each node to build dependent list
        for src, targets in adj.items():
            src_belief = belief_map.get(src)
            if src_belief:
                for tgt in targets:
                    tgt_belief = belief_map.get(tgt)
                    if tgt_belief and tgt_belief.belief_id not in src_belief.dependent_belief_ids:
                        src_belief.dependent_belief_ids.append(tgt_belief.belief_id)
                src_belief.dependent_belief_ids.sort()

        # Topological traversal to propagate confidence
        for parent_cid in topo_order:
            parent_belief = belief_map.get(parent_cid)
            if not parent_belief:
                continue
                
            parent_final = parent_belief.final_confidence
            # Attenuated penalty from this parent using config value
            penalty = (parent_final - 1.0) * config.attenuation
            
            for child_cid in adj[parent_cid]:
                child_belief = belief_map.get(child_cid)
                if not child_belief:
                    continue
                
                new_adjustment = min(child_belief.propagated_adjustment, penalty)
                new_final = max(0.0, min(1.0, child_belief.local_confidence + new_adjustment))
                
                old_assessment = child_belief.assessment
                new_assessment = EvidenceAssessment(
                    base_confidence=old_assessment.base_confidence,
                    agreement_score=old_assessment.agreement_score,
                    corroboration_score=old_assessment.corroboration_score,
                    contradiction_penalty=old_assessment.contradiction_penalty,
                    staleness_penalty=old_assessment.staleness_penalty,
                    propagated_adjustment=new_adjustment,
                    local_confidence=child_belief.local_confidence,
                    final_confidence=new_final
                )
                
                child_belief.propagated_adjustment = new_adjustment
                child_belief.final_confidence = new_final
                child_belief.assessment = new_assessment

        return beliefs
