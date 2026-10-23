# AI-investing-app Repository Notes

## Product and Context

- Daily investment research runs in Codex chat through the repository Skill and Python CLI. Default delivery is Japanese text/Markdown plus saved JSON; do not launch a browser/server, build a new app or deploy unless explicitly requested. See `docs/CODEX_OPERATION.md`.
- The active app is Reflex; treat Streamlit code as archived unless the task explicitly targets the legacy branch.
- Read `progress.md` before non-trivial work and keep it limited to repository state.
- Trace market features through provider -> service or context -> UI -> AI before changing ownership or adding analysis.
- Preserve explicit `unavailable`, insufficient-data, and `research_only` states; do not zero-fill missing evidence or synthesize certainty.
- Keep outputs framed as research and alerts, not direct trade recommendations.
- Update provenance or operations documentation when a source, freshness contract, or availability status changes.

## Validation

- The standard local release gate is `.venv\Scripts\python.exe scripts\check.py`.
- Credentialed live smoke and Browser verification are separate close-out checks when the changed path requires them.

## Publication

- Codex-only research work is preserved on `codex/codex-research-operation`. Completing ordinary research or saving this workflow does not authorize merging into the production branch or deploying the legacy app. Production publication requires a separate explicit request.
- In this repository, an explicit user request to `push` authorizes committing the scoped, validated current-task changes when needed and pushing them directly to `main`.
- Before publishing, verify the intended file set, a clean staging boundary, and that local `main` can advance from `origin/main` without rewriting history.
- Use fast-forward-only publication. Never force-push, rebase published history, or include unrelated changes; stop and ask when the branches diverge, conflicts exist, or task ownership is unclear.
- After a `main` push, monitor the `Quality and deploy` workflow through the private Hugging Face Space verification or confirmed rollback, and report the final result.
