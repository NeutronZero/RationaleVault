# RationaleVault Release Validation Checklist

Before releasing a new version of RationaleVault (e.g. `v1.0.0`), the following checks must be executed and validated.

---

## 1. Automated Tests & Diagnostics

- [ ] **Run Unit Tests**: All 283 tests must be collected. 269 pass; 14 are expected skips (require live PostgreSQL connection, marked with `@pytest.mark.db`).
  ```bash
  pytest
  ```
- [ ] **Run CLI Doctor**: Checks database connectivity, assets, and active projection chain.
  ```bash
  rationalevault doctor
  ```
- [ ] **Run CLI Evaluator**: Ensures all metrics (completeness, precision, density) pass exit gates.
  ```bash
  rationalevault evaluate
  ```

---

## 2. Examples Validation

- [ ] **Event → Memory Flow**: Confirm `examples/basic_memory/main.py` executes successfully.
- [ ] **Memory → Knowledge → Graph Flow**: Confirm `examples/knowledge_synthesis/main.py` executes successfully.
- [ ] **Context → Compiler → Handoff Flow**: Confirm `examples/multi_agent_handoff/main.py` executes successfully.

---

## 3. Distribution & Packaging

- [ ] **Build Wheel Package**: Builds `.whl` and `.tar.gz` distribution packages.
  ```bash
  python -m build
  ```
- [ ] **Clean Install Verification**: Installs the built wheel locally in a clean virtual environment and runs doctor.
  ```bash
  pip install dist/*.whl
  rationalevault doctor
  ```
- [ ] **Release Manifest Verification**: Confirms that `.rationalevault/reports/release_manifest.json` contains:
  ```json
  {
    "rationalevault_version": "1.0.0rc2",
    "schema_version": "1.0"
  }
  ```

---

## 4. Documentation & Metadata

- [ ] Centralized version in `rationalevault/__init__.py` is updated.
- [ ] `CHANGELOG.md` is updated with changes for the release.
- [ ] `README.md` positioning and installation steps are verified.
- [ ] Architecture diagrams match the current system layout.
