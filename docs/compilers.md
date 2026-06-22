# RationaleVault Agent Compilers

Compilers transform context packages into format blocks targeted at specific AI models.

---

## Registry
RationaleVault supports multiple compilers via a dynamic registry:
- **Claude**: Compiles a rich Markdown block optimized for Claude Code.
- **Cursor**: Compiles structured XML blocks for Cursor's codebase indexer.
- **OpenCode**: Formats output for open source code models.

## Usage
Select a compiler by passing the model name:
```python
from rationalevault.compilers.registry import get_context_compiler

compiler = get_context_compiler("claude")
output = compiler.compile(context_package)
# Pass output.rendered_content to your agent prompt
```
