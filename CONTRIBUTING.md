# Contributing to Relay

Thank you for your interest in contributing to Relay!

---

## Architecture Freeze Rules
- We prioritize stability, documentation, and quality control.
- No new runtime capabilities or schema extensions can be introduced without a formal proposal and consensus.

## Setting Up Your Development Environment

1. Clone the repository and navigate to the directory:
   ```bash
   git clone https://github.com/your-username/Relay.git
   cd Relay
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies in editable mode:
   ```bash
   pip install -e ".[dev]"
   ```

## Development Guidelines

- **Write Unit Tests**: Every bug fix or change must include corresponding unit tests in the `tests/` directory.
- **Run Quality Checks**:
  Before submitting a PR, verify all components are fully functional:
  ```bash
  pytest
  relay doctor
  relay evaluate
  ```
- **central versioning**: Respect the centralized versioning schema in `relay/__init__.py`.
