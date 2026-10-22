# ADR-0002 — Frontend foundation, session storage, and dependency pins

Status: Accepted for the foundation slice. Session storage must be revisited before any shared or public environment.
Date: 2026-10-13

## Decisions
- Frontend: Next.js 15.5.26 (App Router), React 19.0.0, TypeScript 5.6.3, Tailwind CSS 3.4.17.
- Same-origin API: the browser calls `/api/*`; `next.config.mjs` forwards to the backend (`VITA_API_URL`, default `http://localhost:8000`). This avoids CORS configuration.
- Session token is held in `sessionStorage` (per tab). Storage access is wrapped in try/catch; blocked storage shows a clear message instead of failing silently.

## Why not an HttpOnly cookie yet
An HttpOnly cookie is the stronger choice and is required before production. It needs CSRF protection and a decision on same-site policy with the backend origin. Both belong with the first real deployment, not this slice. Recorded as a known gap.

## Dependency pins and advisories (checked 2026-10-13)
- Next.js 15.1.6 (initial install) had multiple critical advisories. Moved to 15.5.26 (published 2026-09-22; the two-week minimum age is met).
- `npm audit` reports one **moderate** advisory on next (15.0.0–15.5.26). The fix is 15.5.27, published 2026-09-30, which is inside the two-week window today. **Action:** upgrade to 15.5.27 on or after 2026-10-14, then rerun `npm audit`.
- PostCSS: Next's bundled copy had a high advisory (≤8.5.22). Pinned to 8.5.27 (published 2026-09-03) through `overrides`.
- New backend dependency: `email-validator` (required by Pydantic's `EmailStr`).

## Consequences
- Client code is not covered by automated end-to-end tests yet. The flow was verified manually through the proxy, and the production build passes. Playwright is planned for Week 9 in the workbook.
