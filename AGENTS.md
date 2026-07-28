# AI-investing-app Repository Notes

## Product and Context

- The active app is Reflex; treat Streamlit code as archived unless the task explicitly targets the legacy branch.
- Read `progress.md` before non-trivial work and keep it limited to repository state.
- Trace market features through provider -> service or context -> UI -> AI before changing ownership or adding analysis.
- Preserve explicit `unavailable`, insufficient-data, and `research_only` states; do not zero-fill missing evidence or synthesize certainty.
- Keep outputs framed as research and alerts, not direct trade recommendations.
- Update provenance or operations documentation when a source, freshness contract, or availability status changes.

## Validation

- The standard local release gate is `.venv\Scripts\python.exe scripts\check.py`.
- Credentialed live smoke and Browser verification are separate close-out checks when the changed path requires them.
