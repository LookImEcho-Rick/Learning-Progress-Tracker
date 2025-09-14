# AGENT.md

## Mission
This agent builds and maintains the **Learning Progress Tracker** web app. It must not only generate code, but also keep the **documentation files** in sync with the project.

## Documentation Workflow
Whenever the agent adds or modifies code, it must:
1. Update `README.md` with any new usage instructions.
2. Update `DOCS/USER_GUIDE.md` for changes to the user-facing experience.
3. Update `DOCS/ARCHITECTURE.md` for changes to modules, flows, or data models.
4. Update `ROADMAP.md` with newly proposed features or changes in priority.
5. Update `CHANGELOG.md` under **Unreleased** with a clear, human-readable summary.

## Files to Maintain
- `README.md`
- `DOCS/USER_GUIDE.md`
- `DOCS/ARCHITECTURE.md`
- `ROADMAP.md`
- `CHANGELOG.md`

## Coding Standards
- Python 3.10+
- PySide6 for desktop UI
- SQLite for persistence
- Visualizations via Matplotlib

## Project Rules
- On launch: auto-load saved data or initialize a new DB.
- Always show today’s blank entry.
- Store all data locally.
- Provide visual insights (not just raw numbers).
- Maintain clean, modern UI/UX.

## Roadmap Policy
The agent must refine `ROADMAP.md` over time:
- Add new features it thinks will help.
- Move completed items to the changelog.
- Keep the plan realistic and scoped.

## Testing
Agent should ensure:
- Core features are testable.
- Week calculation logic works across month/year boundaries.
- Data loads and saves correctly.

## Commit Style
Each change should be small, coherent, and accompanied by doc updates.
