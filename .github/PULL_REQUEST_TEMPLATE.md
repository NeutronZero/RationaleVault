## Description
Provide a summary of the changes and the problem solved.

## Related Issues
Fixes #[issue-number]

## Verification Checklist
All submissions must pass the following release gates:

- [ ] **pytest passes**: All 283 unit and integration tests run successfully.
- [ ] **relay doctor passes**: The diagnostics suite verifies database connections and projection chains.
- [ ] **relay evaluate passes**: The evaluation pipeline successfully verifies exit gates.
- [ ] **Wheel build check**: `python -m build` compiles the project correctly without errors.
- [ ] **Documentation updated**: Any interface or logic changes are documented in the `docs/` folder.
