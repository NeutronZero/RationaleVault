# Relay Graph Projection

The Knowledge Graph projects objects and relations into a structured topological map.

---

## Projection Rules
- **Nodes**: Formed by hashing knowledge type, title, and version (`sha256(type + title + version)`).
- **Edges**: Formed by detecting topic overlaps, tag intersections, or explicit contradictions.
- **Deterministic ID**: The graph ID is a SHA-256 hash computed over sorted nodes and edges, guaranteeing reproducibility.

## Exports
Relay supports exporting graphs for analysis:
- **Mermaid**: Flowcharts for markdown documentation.
- **GraphML**: Standard XML format for tools like Gephi.
- **JSON**: Native serialization format.
