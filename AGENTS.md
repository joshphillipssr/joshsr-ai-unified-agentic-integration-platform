# AGENTS Instructions: agentic-community-mcp-gateway-registry

Scope:
- Applies only to this repository.

Repository-specific defaults:
- For standard validation in `codex-control`, run `make test-green-container`.
- Use `make test-full-container` only when broader coverage is required; it is long-running and may depend on additional integration prerequisites.
- Prefer repository venv execution for Python tests (`.venv/bin/python -m pytest`) and repository workflows (`scripts/run-container-validation.sh`).
- Do not rely on system `pytest` in container contexts.

Operational note:
- If container Python tooling drifts, run `just codex-container-python-stack` from `/Users/josh/Projects/joshphillipssr/codex-workspace` to restore the venv-first baseline.
- Auth-path runbook: run `make check-registry-auth-path` (expects unauthenticated `401` from `/api/auth/me`); if it returns `500`, inspect registry nginx logs for `connect() failed ... auth-server`.
