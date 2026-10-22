# Imparency — Reconciled Specification v1

**Status:** Draft for review. Not yet validated against the repository.
**Date:** 2026-10-13
**Sources:** `Social_Impact_Exchange_12_Week_Pilot_Project_Plan.xlsx` (the "workbook"); Imparency 2.0 brief (the "brief").
**Repository audit:** NOT PERFORMED. The linked folder `D:\Vitainspire` lists as empty to the session tools, the device shell failed to start, and `~/vitainspire` is not connected. Every statement about current implementation status below is therefore **unverified**.

---

## 0. How to read this document

- **Pilot priority** is for the original 12-week pilot scope (workbook). **Product priority** is for the broader Imparency vision (brief).
- Priority codes: **P0** build for pilot; **P1** build after pilot or if a decision promotes it; **P2** defer; **P3** do not build.
- "Decision Dn" refers to Section 8. Items marked **Decision** must not be built until confirmed.

---

## 1. Business objectives (from the workbook)

1. **Production-shaped pilot.** Deliver a complete NGO ↔ CSR/Donor ↔ Beneficiary journey without manual database intervention.
2. **Timeline.** 10 weeks to Pilot Ready, then 2 weeks of controlled pilot and stabilization (total 12 weeks).
3. **Core value loop.** CSR funding → eligible, ranked NGO matches → proposal → commitment and payment → milestones → field evidence → verification → governed outcomes → approved impact report.
4. **Delivery discipline.** Working, reviewed, tested, merged, staging-deployed behavior counts as progress. Code volume does not. One coding issue per intern at a time; branches live under 2 days; PRs under ~400 net lines; sensitive work (auth, tenancy, consent, finance, permissions) requires peer review.

The brief adds the public-facing mission: direct donors, registered community members, CSR organisations, NGO credibility, and accountable agentic automation. The workbook does not cover public donation, the public homepage, or the Public Trust Timeline.

---

## 2. Worksheet-by-worksheet requirements inventory

| Worksheet | Contents | Notes |
|---|---|---|
| **Executive Plan** | Objective, timeline, three owners, weekly rhythm, progress rule, WIP, branch and PR limits, integration and sensitive-work rules | Defines the team model: Intern 1 (Admin/Platform), Intern 2 (NGO/Program), Intern 3 (Donor/CSR/AI/Integration). |
| **weekly Demo** | Weeks 1–12: what each owner must demonstrate, plus an integrated Friday proof | Each week has a demo gate. Week 1 needs all three portals on staging with real persistence. |
| **12-Week Roadmap** | Dated plan, 24 Aug to 13 Nov 2026. Milestones: W2 tenancy/onboarding, W4 RFP→shortlist, W6 FUNDED project, W7 evidence, W8 impact, W9 RC1, W10 Pilot Ready, W11 controlled pilot, W12 baseline | Dates are as written in the file. Not re-validated. |
| **Alternate-Day Targets** | 108 measurable checkpoints (Mon/Wed/Fri per week per owner), each with dependency and acceptance evidence | **Every one of the 108 Status cells reads "Not Started".** The tracker was never updated, so the file cannot show progress. |
| **Dependencies** | 9 producer→consumer contracts with required-by week and fallback | Critical: Auth/Tenant/Role (W2), NGO/Project schema (W4), FundingOpportunity + MatchResult (W4), Eligibility API (W4), ApprovalRequest API (W5), Finance ledger (W6), Evidence review contract (W7), Metric Registry (W8), Approved Outcome API (W8). |
| **Pilot Scope** | 12 Build/Defer decisions with priority | P0: onboarding, admin verification, tenancy/RBAC, RFP intake, AI extraction, two-stage matching, proposals/approvals, funding/reconciliation, milestones/offline evidence, consent/feedback, outcome/impact, audit/ops. Defer: full FCRA money movement, production e-sign, advanced ML fraud, social publishing, multilingual, ERP, blockchain, autonomous donor outreach. |
| **Tooling & Claude** | Root CLAUDE.md, implement-issue and review-pr skills, GitHub Projects/branch protection, CI, contract-first schemas, AI eval fixtures, approval state-machine tests, idempotency tests, offline sync tests, Playwright, OpenTelemetry, role UAT | Good engineering practice. Several items (CLAUDE.md, skills, Playwright, OTel) need checking against the repo. |
| **Definition of Done** | Issue DoD (9 items) and Pilot Gate (8 items): 0 open P0/P1; 100% tenant/role negative tests; 100% critical E2E; duplicate webhook/idempotency; AI failure retry visibility; backup/restore tested; monitoring and rollback runbook; critical journey works without SQL edits | The pilot gate is the acceptance standard for this specification. |

---

## 3. Reconciliation matrix

Legend — Source: **WB** workbook, **BR** brief, **REC** recommendation from this review.

| # | Requirement | Source | Intended user | Pilot priority | Product priority | Dependencies | Acceptance criteria | Conflict / risk |
|---|---|---|---|---|---|---|---|---|
| R1 | Multi-tenant org model, RBAC, membership | WB (W2, P0); BR §2, §9 | All | P0 | P0 | None (foundation) | Cross-tenant read/write denied in 100% of negative tests; role matrix enforced server-side | Blocks all streams; highest-risk security area |
| R2 | Individual donor account | BR §2B, §3 | Donor | P1 (D1) | P0 | R1, identity | Registration gives value beyond donation; personal workspace | Brief wants it first-class; not in workbook |
| R3 | NGO onboarding + profile | WB (W2–3); BR §4 | NGO | P0 | P0 | R1 | Profile saved and reloaded; verification state shown | Brief profile is much richer than the pilot profile |
| R4 | CSR organisation onboarding, team, roles | WB (W2); BR §2C | CSR | P0 | P0 | R1 | Org-level roles; invitations; verified state | Brief says no "donor dashboard with logo" |
| R5 | Admin verification queue (human trust gate) | WB (W2, P0); BR §2E | Admin | P0 | P0 | R1, R3, R4 | Approve/reject requires reason; state change audited; org sees new status | Reviewer capacity is a bottleneck |
| R6 | Document upload, secure storage, metadata | WB (W2–3); BR §6, §9 | NGO, Admin | P0 | P0 | Object storage | Type and size validated; signed short-lived URLs; access checked per request | Malware scanning not specified (D9) |
| R7 | Compliance score (PAN 15, Reg 20, 12A 15, 80G 15, FCRA 20, Impact 15) | BR §6 | NGO, Admin | P1 (indicator only) | P0 | R6; legal rules (D6) | Deterministic code; weights sum to 100; optional docs not penalised | Workbook has no score. Score must not be read as legitimacy |
| R8 | Compliance document states (missing, pending, active, expiring, expired, rejected, n/a) | BR §6 | NGO, Admin | P1 | P0 | R6, R7 | State machine tests; each transition audited | FCRA "5-year" rule unverified (D6) |
| R9 | Expiry tracking and reminders | BR §6, §12 | NGO | P1 | P0 | R8, scheduler | Reminders idempotent; no duplicate sends | Needs notification channel (D9) |
| R10 | RFP / opportunity intake, manual and document-assisted | WB (W3–4, P0) | CSR | P0 | P0 | R4, R6 | Versioned opportunity; source file linked | None significant |
| R11 | AI requirements extraction with human correction | WB (P0); BR §7 | CSR | P0 | P0 | Job runtime (R19) | Output validated against schema; each field has confidence and source; corrections stored; eval set passes | Hallucinated requirements. Must show source text |
| R12 | Two-stage matching: deterministic eligibility, then project-fit ranking | WB (W4, P0); BR §1, §6 | CSR, NGO | P0 | P0 | R3 capability data, R10 | Ineligible NGO rejected with reason; eligible NGO ranked with explanation | Eligibility rules are the highest-value business logic |
| R13 | Shortlist and human review | WB (W4) | CSR | P0 | P0 | R12 | Human selects; decision recorded | None |
| R14 | Proposal versions, change requests, approvals | WB (W5, P0) | NGO, CSR | P0 | P0 | ApprovalRequest (R20) | v1 → change request → v2 → approve works; no bypass of gate | Approval state machine must be tested |
| R15 | Funding commitment, payment recording, reconciliation (ledger) | WB (W6, P0) | CSR, Admin | P0 (sandbox/manual) | P0 | Ledger model | Append-only ledger; integer minor units; duplicate payment event produces one entry; unmatched payment → exception | Money math errors. No balances computed in UI |
| R16 | Milestone allocation approval → project FUNDED | WB (W6) | NGO, CSR | P0 | P0 | R14, R15 | Allocation needs approval; project state derived from ledger | Depends on R15 |
| R17 | Milestones and field tasks | WB (W7) | NGO field | P0 | P0 | R16 | Task assigned; milestone status changes with evidence | None |
| R18 | Mobile field evidence: photo, GPS, note | WB (W7) | NGO field | P0 | P0 | R6, R17 | Captured on mobile; GPS and capture time stored | Device GPS accuracy varies |
| R19 | Offline capture and sync (no duplicates) | WB (W7); Tooling | NGO field | P0 (basic) | P0 | R18 | Network-off capture; reconnect syncs once; idempotency key per capture | Largest technical risk for field use |
| R20 | ApprovalRequest primitive | WB (W5) | All | P0 | P0 | R1 | Generic; used by R14, R16, R22 | Build first (W5) |
| R21 | Job runtime: durable queue, retries, replay, failed-job view | WB (W4, W9); BR §7, §8 | Admin, Eng | P0 | P0 | Postgres | Retry, replay and failed-job visibility shown in ops console | Shape decided by stack audit (D7) |
| R22 | Evidence verification queue; duplicate, GPS, metadata flags | WB (W7); BR §6 | Admin | P0 | P0 | R18 | Flags are leads for review; never auto-reject without human | Deterministic flags only (WB defers ML fraud) |
| R23 | Beneficiary cohort, consent, withdrawal | WB (W3, W7, P0) | NGO, Beneficiary | P0 | P0 | R3 | Consent recorded with scope and version; withdrawal blocks new publication | Personal data. Needs retention rule (D9) |
| R24 | Beneficiary feedback and grievance triage | WB (W7) | NGO, Admin | P0 (basic) | P1 | R23 | Feedback routed to queue; grievance tracked to closure | Scope to be confirmed |
| R25 | Governed outcome metrics (registry, definitions, periods) | WB (W8, P0); BR §4 | NGO, Admin | P0 | P0 | R23, R18 | Metric has definition and period; missing data yields INSUFFICIENT_DATA, not a number | Must not fabricate results |
| R26 | Impact approval and approved report | WB (W8); BR §4 | Admin, Donor | P0 | P0 | R25, R20 | Report contains only approved assertions; approval audited | Brief requires human approval before publishing |
| R27 | Donor / CSR impact dashboard and report view | WB (W8); BR §2C | Donor, CSR | P0 | P0 | R26 | Shows approved data only | Confirm dashboard scope (D1) |
| R28 | Donor follow, updates, notifications with opt-out | WB (W7); BR §2B | Donor | P0 (notifications) | P1 | R2 | Opt-out honored; only approved content sent | Needs email adapter (D9) |
| R29 | AI grounded proposal assistant | WB (W5); BR §4 | NGO, CSR | P0 | P0 | Retrieval over approved records | Every claim cites a record; unsupported claims flagged | Hallucination risk |
| R30 | Audit log for critical actions | WB (P0); BR §6 | Admin | P0 | P0 | R1 | Actor, action, resource, timestamp, approval reference; tested per critical transition | Must be append-only |
| R31 | Observability: correlation IDs, structured logs, traces, agent-run records | WB (W9); BR §7, §8 | Admin, Eng | P0 | P0 | R21 | Failure in staging visible in dashboard with correlation ID | Tooling choice (D7) |
| R32 | Backup, restore, rollback runbook | WB (W9–10, DoD) | Admin | P0 | P0 | Environment | Restore tested and evidenced | Not yet verified |
| R33 | Accessibility and mobile behavior | WB (W9); BR §10 | All | P0 | P0 | UI | Keyboard path; focus; contrast; no horizontal scroll at 360px | Needs audit |
| R34 | Public NGO profile (read-only, verified fields only) | BR §4, §5 | Public | P1 (D1) | P0 | R5 | Shows only approved public fields; no fixtures presented as real | Fake-data risk |
| R35 | Public homepage with donor and NGO entry points | BR §5 | Public | P1 | P0 | R34 | No unverified platform statistics | Brief copy is a starting point only |
| R36 | Public Trust Timeline | BR §6 | Public | P1 | P0 | R5, R26, approved events | Only approved public events; no private data | Needs event policy |
| R37 | Direct donation without registration (Razorpay) | BR §3 | Public donor | Defer (D2) | P0 | Payments, webhooks (R38) | Server-side verification; duplicate webhooks produce one transaction | Payment correctness; not in workbook |
| R38 | Verified payment webhooks, idempotency | BR §3, §8; WB DoD | Eng | P0 (ledger ingest) | P0 | R15 | Replay of same webhook is a no-op; signature verified | Same engine as R15 |
| R39 | Guest donation claim to account | BR §3 | Donor | P2 | P1 | R2, R37 | Ownership verified (e.g. OTP to donor contact); never inferred from email alone | Account-takeover risk |
| R40 | Automated agent: compliance certificate extraction and review task | BR §7 (first workflow) | NGO, Admin | P1 (D4) | P0 | R21, R11 | Same runtime as R11; reviewer approves; audit written | Not in workbook pilot scope |
| R41 | Agent: evidence and claim assessment | BR §7 | Admin | P2 | P1 | R22, R25 | Source-referenced; no accusation | Keep as flags until evidence is proven |
| R42 | Agent: Risk Intelligence briefs | BR §7 | Admin | P2 | P2 | R22 | Leads only | WB defers advanced ML fraud |
| R43 | Agent: NGO operations (deadlines, reminders) | BR §7 | NGO | P1 | P1 | R9 | Mostly deterministic scheduler; AI optional | None |
| R44 | Data retention, deletion, DPDP-aligned privacy | BR §9 | All | P0 policy needed before real beneficiary data | P0 | Legal (D9) | Documented retention per data class; deletion procedure tested | Legal input required |
| R45 | Full FCRA money movement | WB (Defer) | — | Defer | P2 | Legal | — | Do not implement |
| R46 | Production e-signature | WB (Stub/Defer) | CSR | P1 stub | P1 | — | Store executed agreement only | — |
| R47 | Automated social publishing | WB (Defer) | NGO | P2 | P2 | — | Draft-only if useful | — |
| R48 | Autonomous donor outreach | WB (Defer) | Donor | P2 | P2 | — | Human-reviewed communication only | — |
| R49 | ERP / accounting integration | WB (Defer) | Admin | P2 | P2 | R15 | Export and reconciliation interface first | — |
| R50 | Blockchain audit anchor | WB (Defer) | — | P3 | P3 | — | No pilot value | — |

---

## 4. Proposed product architecture and domain model

### 4.1 Architecture

**Shape:** modular monolith. One deployable backend and one frontend, with clear module boundaries. Separate services only when a measured need appears (for example, the worker pool).

**Stack (provisional):**
- Frontend: Next.js App Router, TypeScript, Tailwind (per brief). **Verify against repo (D7).**
- Backend: FastAPI (per brief). Prisma is listed in the brief as something to assess. Keep it only if the audit confirms version compatibility. **Verify against repo (D7).**
- Database: PostgreSQL, with row-level tenant scoping enforced in the data layer.
- Files: S3-compatible object storage, private bucket, signed URLs.
- Background work: a Postgres-backed job table with `SELECT … FOR UPDATE SKIP LOCKED` workers. This is the simplest option that gives durability, retries and replay. Adopt a separate queue only when throughput or latency requires it.
- Payments: a provider adapter. Sandbox and manual adapters in the pilot. Razorpay adapter behind the same interface (D2).
- AI: a model gateway with structured (schema-validated) outputs, prompt and model versions recorded per run, and no direct data access. Data access goes through typed tools with explicit permissions.
- Observability: correlation IDs across API, jobs and AI calls; structured logs; traces; agent-run records.

**Surfaces:** one deployable app with separate route areas: public, donor, CSR, NGO, admin (D3). The workbook names three portals; this design keeps them as areas in one app. This reduces deployment and auth duplication. It does not change the permission model.

### 4.2 Module boundaries

| Module | Owns | Does not own |
|---|---|---|
| Identity & Tenancy | Users, sessions, orgs, memberships, roles, invitations | Business records inside orgs |
| Compliance | Documents, document states, compliance score, expiry | Legal determinations |
| NGO Profile & Programs | Profile, capabilities, projects, initiatives, milestones | Funding amounts |
| Beneficiaries & Consent | Cohorts, consent records, withdrawals, feedback, grievances | Public display of personal data |
| Opportunities & Matching | RFPs, opportunities, requirements, eligibility rules, fit scores, shortlists | Eligibility decisions made by AI |
| Proposals & Approvals | Proposal versions, change requests, ApprovalRequest, SLA | Money |
| Finance | Commitments, ledger (append-only), payment events, reconciliation, allocations | UI balance math |
| Field & Evidence | Tasks, captures, offline sync, evidence, flags, verification decisions | Outcome values |
| Outcomes & Impact | Metric registry, outcome calculations, impact assertions, reports | Unapproved claims |
| Public Trust | Approved public events, public profile projections | Private records |
| Donations (deferred) | Donation intents, provider events, transactions | Ledger entries for pilot |
| Agents & Workflows | Definitions, runs, steps, tool calls, approvals requested | Authorization decisions |
| Notifications | Templates, deliveries, opt-outs | Business state |
| Audit | Append-only event log | — |

### 4.3 Core domain entities (new or to verify against repo)

- **Tenancy:** `Organization` (type: NGO | CSR | Individual), `Membership` (user, org, role), `Invitation`, `Role`.
- **Compliance:** `ComplianceDocument` (type, file ref, extracted fields, state, valid-from, valid-to), `ComplianceAssessment` (score inputs, computed score, computed at, rules version), `VerificationDecision` (reviewer, decision, reason).
- **Programs:** `Initiative` (sector, geography, budget, beneficiaries, eligibility inputs, outcomes), `Project`, `Milestone`.
- **Beneficiaries:** `Cohort`, `ConsentRecord` (scope, version, granted/withdrawn), `Feedback`, `Grievance`.
- **Matching:** `Opportunity` (versioned), `RequirementSet` (extracted, with source references and corrections), `EligibilityResult` (rule id, pass/fail, reason), `FitScore` (inputs, model or formula version), `Shortlist`.
- **Proposals:** `Proposal` and `ProposalVersion`, `ChangeRequest`, `ApprovalRequest` (subject, state, approver, SLA).
- **Finance:** `Commitment`, `LedgerEntry` (append-only, integer minor units, idempotency key), `PaymentEvent` (provider, provider event id, unique), `ReconciliationMatch`, `Allocation`, `FinanceException`.
- **Field & Evidence:** `FieldTask`, `Capture` (client capture id, GPS, time, device), `EvidenceAsset`, `EvidenceFlag` (duplicate, GPS, metadata), `VerificationDecision`.
- **Outcomes:** `Metric` (definition, unit, period, source rules, version), `OutcomeValue` (computed, with input references), `ImpactAssertion` (approved or not), `ImpactReport` and `ReportVersion`.
- **Platform:** `WorkflowExecution`, `WorkflowStep`, `AgentRun` (model version, prompt version, tokens, cost, status), `AuditEvent`, `Notification`.

### 4.4 Invariants that must be enforced in code and tested

1. Every tenant-owned row carries an org identifier, and every query is scoped by it.
2. The ledger is append-only. Corrections are reversing entries. Money is stored as integer minor units.
3. A provider event with the same provider event id is processed once.
4. A project becomes FUNDED only from ledger-backed, approved allocations.
5. A consequential state change (verification, approval, allocation, publication, impact approval) requires an ApprovalRequest or an authorized human action. It writes an audit event in the same transaction.
6. Deterministic code produces eligibility results, compliance scores, and money totals. AI outputs are stored as proposals with source references and require human confirmation before use.
7. Public projections include only records with an approved public visibility state.

---

## 5. Phased agentic automation plan

Principles: agents prepare work, cite sources, and request approval. They do not change authoritative state. Each run is durable, retryable, observable, and runs with the permissions of a named service identity or the requesting user.

**Shared runtime (Phase A, weeks 4–5).** Job table, retries with backoff, idempotency keys, timeouts and cancellation, step records, AgentRun records, failed-job view, replay. Built once. Used by RFP extraction, certificate extraction, and impact drafting.

| Phase | Capability | Output | Human gate | Deterministic parts | Pilot? |
|---|---|---|---|---|---|
| A1 | RFP requirements extraction | Structured requirement set with source text and confidence | CSR corrects and confirms | Schema and required-field validation | P0 (W4) |
| A2 | Grounded proposal assistant | Draft text that cites approved records | NGO/CSR edits and submits | Retrieval limited to the user's permitted records | P0 (W5) |
| A3 | Impact report drafting | Draft report; INSUFFICIENT_DATA where measurements are missing | Admin approves each assertion | Metric calculations in code | P0 (W8) |
| A4 | NGO operations reminders | Deadlines and follow-ups | None for reminders; sends are logged | Scheduler, not an LLM | P1 |
| B1 | Compliance certificate extraction, and the brief's first complete workflow | Extracted fields, comparison with records, review task | Reviewer approves, rejects, or requests information | Field format checks, comparison rules, state transitions | P1 (D4) |
| B2 | Evidence claim assessment | Source-referenced assessment and flags | Human decision required | Duplicate and GPS checks | P2 |
| B3 | Risk briefs | Investigation leads | Human only | Flags from rules | P2 |
| C1 | Donor and CSR Q&A over approved records | Cited answers | None (read only) | Permission-scoped retrieval | P2 |

**Brief workflow (compliance certificate, steps 1–13)** is the reference design for all agent work. The workflow must demonstrate duplicate event handling, model failure recovery, retry, interrupted execution, and authorization checks. It is the ideal first test case for the shared runtime, which is why B1 is recommended for the pilot (D4).

**Evaluation.** Fixed datasets for RFP extraction, matching, and outcome cases. Checks: schema validity, missing required fields, hard-rule violations, and unsupported claims. Record baseline on first run. Do not state accuracy until measured.

**Cost and model tracking.** Every AgentRun records model id, prompt version, input and output tokens, cost, latency, and outcome. Model and prompt changes require re-running the evaluation set.

---

## 6. Role-specific user journeys and information architecture

### 6.1 Journeys

**Public visitor (direct donor, D2):** Homepage → NGO or campaign → profile → evidence and compliance state → donate → confirmation → optional follow. Account creation is not required. Pilot scope: profile read-only; donation deferred.

**Individual donor (P1):** Register → follow NGOs → donation history → impact updates → preferences. Guest donation claim requires ownership verification.

**CSR professional (P0):** Register organisation → verification → invite team → create opportunity → upload RFP → correct extracted requirements → review eligibility and ranked shortlist → open Match Inbox items → proposal → approve → commitment and payment (sandbox) → project monitoring → approved impact report.

**NGO (P0):** Register → verification → profile and capabilities → initiative → Match Inbox (express interest) → proposal v1 and revisions → accepted project → milestones and field tasks → field capture (online or offline) → consent and feedback → outcome metrics → impact draft → submit for approval.

**Administrator (P0):** Verification queue → approval queue (SLA) → finance exceptions → evidence and risk queue → metric registry and impact approvals → job and agent failures → audit log → operations.

### 6.2 Information architecture

| Area | Pages (pilot) | Pages (later) |
|---|---|---|
| Public | Trust explanation (static, honest) | Homepage, NGO discovery, NGO profile, campaign page, Trust Timeline, donation checkout |
| Auth | Register, login, verification status | Guest-donation claim, account recovery |
| Donor | Overview, approved impact report view | Donation history, follows, preferences |
| CSR | Overview, team, opportunities, match inbox, shortlist, proposals, portfolio, impact | Multiple concurrent RFPs, exports |
| NGO | Overview, profile, initiatives, match inbox, proposals, projects, milestones, field, consent, outcomes, impact, approvals | Compliance center (P1), campaign management |
| Admin | Verification, approvals, finance, evidence and risk, metrics, jobs, audit, operations | Advanced risk investigation |

**Empty, loading, error, success, and permission-denied states are required on every page.**

---

## 7. Revised pilot scope, priorities and acceptance criteria

### 7.1 Timeline re-assessment

- The workbook calendar places **today (13 Oct 2026) in Week 8** (12–16 Oct). Week 9 (RC1) is 19–23 Oct, Pilot Ready is 26–30 Oct, and controlled pilot is 2–13 Nov.
- Whether Weeks 1–7 are complete is **unverified**. The Alternate-Day tracker shows "Not Started" for all 108 checkpoints, so it cannot be used as evidence.
- **Recommendation:** before any further build, run a two-day status audit (repo, CI, staging, demos) and mark each Week 1–7 deliverable as Complete / Partial / Not started, with evidence. Then re-baseline. If Weeks 1–7 are materially incomplete, the Pilot Ready date should move, and the scope cut in §7.3 applies first.

### 7.2 Pilot P0 scope with acceptance criteria

| Feature | Acceptance criteria (pilot gate) |
|---|---|
| Onboarding and admin verification (R3–R5) | NGO and CSR can register, complete profile, submit; admin approves or rejects with reason; status change visible to the organisation without developer action |
| Tenancy and RBAC (R1) | 100% negative tests pass for cross-tenant and role violations |
| Documents (R6) | Upload validated; access requires membership; signed URLs expire |
| RFP intake and extraction (R10–R11) | Uploaded RFP yields structured requirements with sources; a human correction is saved and versioned |
| Two-stage matching (R12–R13) | Ineligible NGO rejected with rule reason; eligible NGO ranked with explanation; human selects |
| Proposals and approvals (R14, R20) | v1 → change request → v2 → approval works; no path bypasses the approval gate; full history visible |
| Ledger, reconciliation, allocation (R15–R16, R38) | Duplicate payment event yields one entry; unmatched payment creates exception; allocation requires approval; project FUNDED only from ledger |
| Milestones and field evidence (R17–R19) | Capture with photo, GPS, note; works offline; reconnect syncs once |
| Evidence review (R22) | Flags visible; decision recorded; no automatic rejection |
| Consent and feedback (R23–R24) | Consent recorded per cohort; withdrawal blocks new publication |
| Outcomes and impact (R25–R27) | Metric with definition; missing data shows INSUFFICIENT_DATA; impact assertions need approval; donor sees approved content only |
| AI grounded assistant (R29) | Every claim cites a record; unsupported claims flagged in review |
| Audit and operations (R21, R30–R32) | Critical transitions produce audit events; failed jobs visible with retry; backup restore tested; runbook exists |
| Accessibility and mobile (R33) | Keyboard path works for P0 journeys; usable at 360px width |

### 7.3 Scope cut order if the timeline slips

1. Donor notifications beyond core (R28) → P1.
2. Beneficiary grievance (R24) → P1.
3. Certificate extraction workflow (R40) → P1 (already the recommendation).
4. Offline sync limited to one capture type, with the others online-only.
5. Never cut: tenancy, RBAC, approvals, ledger idempotency, consent, audit.

---

## 8. Material conflicts and decisions requiring human confirmation

| ID | Conflict or decision | Options | Recommendation | Why it matters |
|---|---|---|---|---|
| **D1** | **Pilot audience.** Workbook pilot is B2B (CSR → NGO → beneficiary). Brief makes public and individual donors first-class. | (a) Workbook scope only. (b) Workbook plus public read-only profiles and donor registration. (c) Full brief in pilot. | (b). Keep the workbook P0 unchanged. Add read-only public profile and individual registration as P1 only if confirmed. Do not add (c). | Brief says do not expand the first release automatically. |
| **D2** | **Payments.** Workbook uses sandbox and manual payment. Brief requires verified Razorpay with webhooks. | (a) Sandbox and manual only for pilot. (b) Razorpay test mode in pilot. (c) Razorpay live. | (a) for pilot, with the ledger and idempotent ingest built so the Razorpay adapter drops in. Live money requires explicit approval and a legal review. | Real money and reconciliation risk. |
| **D3** | **Surfaces.** Workbook has three portals. Brief has five audience areas and a public site. | (a) Three separate apps. (b) One app with audience areas. | (b). One deployable, separate route areas and permission boundaries. | Lower operational burden; still meets isolation through RBAC. |
| **D4** | **Compliance-certificate AI workflow in pilot?** Brief names it the first complete workflow. Workbook has upload metadata only. | (a) Pilot P1. (b) Pilot P0. | (a) Build it on the shared job runtime after RFP extraction works. It is the reference workflow for the runtime. | Schedule risk in Weeks 4–5. |
| **D5** | **Compliance score vs human verification.** Brief defines a weighted score. Workbook makes admin verification the trust gate. | (a) Score as indicator plus human gate. (b) Human gate only. | (a). Score is deterministic, shown as an indicator, and does not replace verification. | Score must not read as legitimacy. |
| **D6** | **Legal rules.** FCRA lifecycle (brief assumes a five-year validity rule to verify); 12A and 80G validity; PAN and registration verification; DPDP Act 2023 obligations for beneficiary and donor data. | Obtain legal input. | Do not encode any of these as universal rules until verified against current authoritative sources. This review did not verify them. | Incorrect legal state is a trust failure. |
| **D7** | **Stack and repository.** Brief assumes Next.js, FastAPI, Prisma (to assess). The repository could not be read. | Repo audit. | Audit before any stack decision. Keep Prisma only if version and migration compatibility holds. | Cannot choose migration path blind. |
| **D8** | **Product name and scope.** Workbook titled "Social Impact Exchange"; brief is "Imparency". | Confirm they are the same product and which name is public. | Confirm. This document assumes they are one product. | Naming affects public copy and legal entities. |
| **D9** | **Operational policies.** Retention and deletion for beneficiary data; email and notification channel; malware scanning for uploads; who may approve impact claims and their reviewer capacity. | Decide owners and policies before pilot data enters the system. | Assign owners in Week 6. Pilot uses synthetic or consented data only until policies are signed off. | Beneficiary personal data must not enter the pilot without policy. |
| **D10** | **Team capacity and reviewers.** Workbook assumes three owners, each with one coding issue at a time, and peer review of sensitive work. | Confirm who reviews auth, tenancy, finance, and consent. | Name a reviewer for each sensitive area before Week 2 work resumes. | Sensitive-work rule cannot be met without reviewers. |

### 8.1 Verification required before the next phase

- Repository audit: what exists for each P0 item, with file references.
- CI and staging: whether builds and staging deployments actually run.
- Week 1–7 demos: whether each acceptance demo can be reproduced.
- Any integration claim (Razorpay, email, AI provider) must be tested against a real sandbox before being described as working.

---

## 9. Immediate next steps

1. Resolve D1, D2, D3, D4 and D8 (these change scope and architecture).
2. Provide repository access (see the access options below) or push the repo to GitHub and attach it.
3. Run the status audit (§7.1) and produce the repo audit: Safe to reuse / Refactor / Redesign / Replace / Missing / Unverified / High risk.
4. Re-baseline the timeline, replacing the "Not Started" tracker with evidence-backed status.
5. Only after 1–4: begin the Week-current P0 issue, starting with tenancy and RBAC (R1) if it is not already verified complete.

**Access options for the repository:** (a) grant access to the folder `~/vitainspire` via the device prompt; (b) confirm the correct path for `D:\Vitainspire` (currently empty to the session); (c) add the repository through the GitHub connector.

---

*End of v1. Supersedes nothing. Later versions should be created as new files (v2, v3…). The workbook and existing project documents are unchanged.*
