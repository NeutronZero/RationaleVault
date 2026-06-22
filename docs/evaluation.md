# Relay Evaluation Framework

Relay validates code release readiness using a multi-layer metrics engine.

---

## Metric Runners
The unified evaluator (`relay evaluate`) compiles scores:
- **Deduplication Rate**: Unique memory records vs total records.
- **Source Traceability**: Citations containing parent event streams.
- **Blending Determinism**: Checks if output context packages match identically on multiple runs.
- **Latency Budget**: Measures prompt compilation speeds.

## Reporting
- **JSON Manifest**: Saved at `.relay/reports/release_manifest.json` for CI/CD assertions.
- **Markdown Summary**: Saved at `.relay/reports/report.md` for human review.
