# Imparency

NGO transparency and social-impact platform. See `docs/spec/imparency-reconciled-spec-v1.md` for scope and `docs/decisions/` for recorded choices.

## What exists

- **Accounts:** register, sign in, sign out (revokes that session), session expiry. Passwords are Argon2id-hashed. Session tokens are random and stored only as SHA-256 hashes.
- **Organizations:** NGO, CSR and individual. The creator becomes owner. Roles are OWNER, ADMIN and MEMBER.
- **Tenant boundary:** non-members receive 404 for any organization resource. Insufficient role returns 403.
- **Verification:** platform reviewers approve or reject organizations. A rejection needs a reason. A decided organization cannot be silently re-decided. Reviewers cannot verify their own organization.
- **NGO profile:** owners and admins edit it. Publication requires verification and lists every blocker at once. Public page at `GET /public/ngos/{id}`, shown only when verified and published.
- **Compliance documents:** private upload (PDF, JPEG, PNG; content-checked; 10 MB default), duplicate refusal per organization, authorized download, stated expiry date (unverified).
- **Document review:** reviewers download, then approve or reject with a required reason. Decisions are immutable (database trigger). History is visible to the organization.
- **Audit:** append-only (database trigger), with correlation IDs. Covers account, organization, verification, profile, document upload, download, review, project and donation actions.
- **NGO projects:** owners and admins create, edit, publish and unpublish projects. Publishing requires verification, same blocker-listing pattern as the profile. Published projects appear in the public feed.
- **Donations:** anyone can donate to a verified, published NGO (optionally to one of its published projects) with a billing address, no account required. A signed-in donor's donations are linked to their account automatically and visible in their dashboard. Donations are append-only (database trigger); money is stored as integer minor units.
- **Verification assist (agentic):** `GET /admin/organizations/{id}/ai-assist` drafts a reviewer-facing summary and flags from the organization's profile and documents. Deterministic by default; calls a model only if `VITA_LLM_API_KEY` is set, and falls back to the deterministic draft on any failure. It is read-only and never decides -- the admin still approves or rejects.
- **Frontend (Next.js):** public landing with a live NGO/project feed and donate links, donate flow (no account), register, sign in, workspace with donation history, organization page, profile editor, projects page, donations-received page, documents page, public NGO page, verification queue (with the AI-assist panel) and document review queue.

## Not yet built
Payment gateway integration (donations are recorded directly, no charge is made), compliance score, RFP intake and matching, proposals, ledger/allocations beyond direct donations, field evidence, outcomes, invitations by email, member removal, password reset, cookie-based sessions, rate limiting, automated browser tests.

## Backend setup

Requires Python 3.11+ (CI tests 3.11 and 3.13) and PostgreSQL 16.

```bash
createdb vitainspire_dev && createdb vitainspire_test
cd backend
cp .env.example .env          # then edit: real credentials stay local, never committed
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head           # schema comes only from migrations
uvicorn app.main:app --reload  # http://localhost:8000/docs
python -m pytest -q            # runs against vitainspire_test; refuses any other database
```

Configuration is read from environment variables with the `VITA_` prefix. There is no default database URL: a missing setting fails at startup.

| Variable | Required | Purpose |
|---|---|---|
| `VITA_DATABASE_URL` | yes | SQLAlchemy URL for PostgreSQL |
| `VITA_STORAGE_DIR` | yes | Private document storage. Must be outside the repository and any web-served folder |
| `VITA_SESSION_TTL_HOURS` | no (168) | Session lifetime |
| `VITA_MAX_UPLOAD_BYTES` | no (10485760) | Upload size limit |
| `VITA_LLM_API_KEY` | no | Enables the live verification-assist model call. Unset means the deterministic draft only -- the feature works either way |
| `VITA_LLM_MODEL` | no (`claude-haiku-4-5-20251001`) | Model used for verification assist, when a key is set |

### Migrations

- Revisions: `0001_baseline` (foundation schema), `0002_profiles_documents_review` (profiles, documents, review decisions, `verified_at`, append-only triggers, and a backfill of `verified_at` from the audit trail), `0003_projects_and_donations` (NGO projects, donations, append-only trigger on `donations`).
- Apply: `alembic upgrade head`. Check for model drift: `alembic check`.
- Verified on 2026-10-13: upgrade, downgrade to `0001_baseline`, and upgrade again on a freshly created database. `0003` verified the same way down to `0002`.
- Before running `0002` on a shared database: take a backup, and confirm no application is writing to `organizations` during the migration.
- Production must revoke `TRUNCATE` and DDL from the application role (see ADR-0003).

### Operator actions

Platform administrators are granted only from the command line, and the grant is audited:

```bash
python -m app.cli grant-platform-admin <email>
```

### Local demo data

`scripts/seed_demo.py` populates `vitainspire_dev` with fictional NGOs, donors and donations through
the real API, so the platform isn't empty while you look at it locally. It refuses to run against
anything other than a database literally named `vitainspire_dev`. Never run it against a shared or
production database -- it is for a developer's own machine only.

```bash
# with the API already running on http://127.0.0.1:8000
python scripts/seed_demo.py
```

No API route can set `is_platform_admin`.

## Frontend setup

Requires Node 22+.

```bash
cd frontend
npm ci
npm run typecheck
npm run build
VITA_API_URL=http://localhost:8000 npm run start   # http://localhost:3000
```

The browser calls `/api/*`, which Next forwards to the backend. The session token is kept in `sessionStorage` for now (see ADR-0002). This must change to HttpOnly cookies before any shared environment.

## Tests

- `python -m pytest -q` (backend, 92 tests): authentication, tenancy, roles, verification, profile publication, document validation and storage, review rules, public visibility, download headers, projects, donations, the public feed, verification assist, and database-level append-only enforcement.
- `npm run typecheck` and `npm run build` (frontend). No automated browser tests yet.
- CI (`.github/workflows/ci.yml`) runs the backend tests, `alembic check`, and the frontend typecheck and build.

## Known gaps (summary)

- Session token in `sessionStorage` (XSS-readable). Cookie migration pending.
- No rate limiting on login or registration. Registration reveals whether an email is registered (409).
- Document storage is local disk. No encryption at rest beyond filesystem permissions, no malware scanning, no retention policy.
- Audit log is append-only per row and per truncate statement, but table owners can still drop it. Production needs privilege separation.
