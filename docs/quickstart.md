# Relay Quickstart

Welcome to Relay! This guide will get you set up and running with event-sourced cognitive memory in less than 5 minutes.

---

## 1. Installation

Install Relay in development mode:
```bash
pip install -e ".[dev]"
```

## 2. Initialize a Project

Initialize the Relay directory structure inside your workspace:
```bash
relay init
```
This initializes a local `.relay/` folder containing the default SQLite memory store (`relay.db`), rule engines, and configuration files.

## 3. Verify Health with the Doctor CLI

Run active diagnostics to verify that everything is configured correctly and the end-to-end projection chain is functioning:
```bash
relay doctor
```
Expected output:
```text
=== Relay Doctor ===
Relay version: 1.0.0rc2
Generated at:  ...

  Event Store            [PASS]   : Connected to SQLiteEventStore
  Memory Store           [PASS]   : Connected to MarkdownMemoryProvider
  Knowledge Store        [PASS]   : Connected to MarkdownKnowledgeProvider
  Evaluation Assets      [PASS]   : Benchmarks folder found
  Evaluation Thresholds  [PASS]   : Successfully instanced EvaluationThresholds
  Graph Projection       [PASS]   : Graph engine loaded successfully
  Compiler Registry      [PASS]   : Successfully registered compilers
  Projection Chain       [PASS]   : Pipeline fully functional
-----------------------------------------------------------------
Overall Result: PASS
```

## 4. Run the Evaluation Suite

Run the full unified evaluation suite to measure the quality metrics of the memory ledger:
```bash
relay evaluate
```
This builds and checks quality scores (such as completeness, keyword precision, redundancy, and graph density) against hard exit gates. A report summary will be created in `.relay/reports/release_manifest.json` and `.relay/reports/report.md`.

## 5. Execute Examples

Check out the executable examples to see how the system operates under different layers:
- **Event to Memory Extraction**: `python examples/basic_memory/main.py`
- **Memory to Knowledge Graph Projection**: `python examples/knowledge_synthesis/main.py`
- **Context Compilation and Adapter Rendering**: `python examples/multi_agent_handoff/main.py`
