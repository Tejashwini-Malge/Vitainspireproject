# Imparency — working rules for coding agents

Authoritative spec: `docs/spec/imparency-reconciled-spec-v1.md`. Decisions are recorded in `docs/decisions/`.

## Non-negotiables
- Authorization is server-side. Every org-scoped route calls `require_membership`. Non-members get 404.
- Money is integer minor units. The ledger is append-only; corrections are reversing entries.
- Audit rows are written in the same transaction as the action they record. Never commit an audit row alone.
- Deterministic code decides eligibility, scores, money totals and state transitions. AI output is a proposal with sources, and needs a human before use.
- Public projections include only approved public data. No fixtures presented as real activity.
- No new dependency without naming it and the reason in the PR description.

## Data
- Schema changes go through Alembic revisions only (`backend/migrations`). Never edit a released revision; add a new one.
- Run `alembic check` before opening a PR. A non-empty result means models and migrations disagree.
- Append-only tables (`audit_events`, `document_review_decisions`) are protected by database triggers. Do not weaken them to make a test pass.
- Storage files live outside the repository. Never commit `.env` or uploaded files.

## Commands
- Backend tests: `cd backend && python -m pytest -q` (requires Postgres at `vitainspire_test`; see README).
- Tests refuse to run against any database not named `vitainspire_test`.

## Process
- One issue at a time. Branches under 2 days. PRs under ~400 net changed lines.
- Auth, tenancy, consent, finance and permissions need peer review.
