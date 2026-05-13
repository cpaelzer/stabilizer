# Stabilizer Design Decisions

## Model Selection (2026-05-13)

### Reasoning
https://openrouter.ai/compare/google/gemini-3.1-pro-preview/x-ai/grok-4.20/z-ai/glm-5.1
=> selecting Grok being capable and quite cheaper

### Coding
https://openrouter.ai/compare/anthropic/claude-opus-4.7/qwen/qwen3.6-plus/deepseek/deepseek-v4-flash
=> Start with qwen3.6 plus which recently gave me good results and is cheaper

## Orchestration Framework Decision (2026-05-13)

We evaluated LangGraph (initially preferred by the user for its graph visualization, state management, and debugging capabilities) against a simple custom `StabilizerOrchestrator`.

**Recommended choice: Custom Python orchestrator with `rich` console output.**

**Rationale**:
- The workflow is fundamentally linear with a small number of conditional filters (safe → applicable → testable). It does not require the complex branching, cycles, or parallelism that justify a full graph framework.
- A custom orchestrator with `rich` Live display, progress bars, detailed phase logging, exclusion reasoning tables, and final summary provides comparable debugging visibility without introducing heavy dependencies (`langgraph`, `langchain`, pydantic v2 integration complexity).
- Keeps the project lightweight, easy for other Ubuntu developers to understand and maintain, and aligned with Canonical engineering culture (favor explicit code over framework magic where deterministic flow suffices).
- "Agents shall use code where deterministic code can do the job and AI where it can't" — this principle strongly favors the simpler approach.
- LangGraph remains a viable future evolution path if the system grows significantly more branching or requires persistent execution tracing.

This decision balances the desire for good observability with long-term maintainability and minimal complexity. The orchestrator will emit clear state transitions, candidate counts, exclusion reasons, and rich-formatted reports throughout execution.

## Dependency Strategy (2026-05-13)

- **Ubuntu archive packages preferred**: `python3-launchpadlib`, `python3-debian`, `python3-rich`, `python3-git`, `devscripts`, `ubuntu-dev-tools`, `python3-pydantic`
- **git-ubuntu**: Installed via snap (`snap install git-ubuntu --classic`), not available in main Ubuntu archive
- **LLM access**: OpenRouter API, with model selection based on task complexity (cheaper for classification, stronger for SRU reasoning and test plan synthesis)

## Output Format (2026-05-13)

- SRU bug templates generated as `.bug` files (not Markdown, not direct Launchpad bug creation)
- Files named after generated bug title (e.g., `Fix-JSON-parsing-edge-case-in-jq-1.7.bug`)
- No default Launchpad team or bug tags included in templates

## Testing Strategy (2026-05-13)

- Start with `jq` (jammy → noble) as primary test case (simplest package, small C utility, excellent version tags, easy test cases)
- Follow with `dovecot` (noble → resolute) and `git` (noble → resolute)
