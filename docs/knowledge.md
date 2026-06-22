# RationaleVault Knowledge Layer

Knowledge represents synthesized facts distilled from memories and events.

---

## Synthesis
Knowledge synthesis merges fragmented memories into high-level facts.
- **Provenance chains** link knowledge objects back to source memory and event IDs.
- **Evidence strength** is derived from supporting memory counts.

## Contradiction Checking
When new knowledge is synthesized, RationaleVault scans the store for logical conflicts (e.g. conflicting architectural principles). If a contradiction is detected, a `KNOWLEDGE_CONTRADICTION` event is appended to the ledger, flagging it for agent resolution.
