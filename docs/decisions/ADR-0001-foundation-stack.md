# ADR-0001 — Foundation stack and first-slice scope

Status: Accepted (provisional until stakeholder confirms D1–D10 in the spec)
Date: 2026-10-13

## Context
The repository was empty. The spec lists Next.js, FastAPI, PostgreSQL and a preference to assess Prisma. No prior code exists to be compatible with.

## Decision
- Backend: FastAPI + SQLAlchemy 2 + psycopg 3 on PostgreSQL 16. SQLAlchemy is used instead of Prisma because the backend is Python and the spec's worker and AI code is Python.
- Auth: opaque server-side session tokens. Only SHA-256 hashes are stored, so sessions are revocable per device. Passwords use Argon2id.
- Background work: to be a Postgres job table with `SKIP LOCKED` workers. Not implemented in this slice.
- Frontend: Next.js App Router + TypeScript + Tailwind (see the frontend slice).
- Surfaces: one deployable app with audience route areas (spec D3, recommended option).
- First slice: identity, tenancy, membership, admin verification, audit. Chosen because every other pilot feature depends on these and the pilot gate requires 100% pass on tenant and role negative tests.

## Consequences
- Migrations are not yet in place. `create_all` is used for dev and test only. Adding Alembic is a required step before any shared environment.
- Session tokens are bearer tokens. Browser usage needs a cookie strategy (HttpOnly, Secure, SameSite) before production; deferred and recorded as a known gap.
- Email-validator is a new dependency, added for email field validation.

## Alternatives considered
- Prisma with a Node backend: rejected for this slice (split-language stack for Python-first AI and workers).
- JWT: rejected because revocation would need a denylist, which is the same state as sessions with more code.

## Update 2026-10-13
- Frontend stack and session storage: see ADR-0002.
