# ADR-0003 — NGO profiles, private compliance documents, and the review gate

Status: Accepted for the NGO profile and document slice. Storage backend and retention are provisional (see Consequences).
Date: 2026-10-13

## Context
Public trust depends on two things kept apart: what an organization says about itself, and what Imparency has checked. This slice adds both paths, plus the controls that keep them separate.

## Decisions
1. **Public visibility requires two independent conditions.** A profile is public only when the organization is verified (`APPROVED`) *and* the organization has published its profile. Either alone is not enough. Non-public and non-existent profiles return the same 404, so the public cannot probe for them.
2. **Profile text is labelled as self-described.** The public page states that the organization wrote it and Imparency did not check it. Verification is shown separately, with the date.
3. **Documents are never public.** Only the document *type* and the *date of approval* appear on a public profile, and only for approved documents. Filenames, hashes, storage details and PAN numbers never leave the private area. PAN documents are only ever approved or rejected, never displayed.
4. **Publication is a deterministic gate.** `publish_blockers` returns every unmet condition at once (org type, verification, mission, sectors, geographies), so an organization fixes everything in one pass.
5. **Review decisions are final and immutable.** A document awaiting review can be decided once. The decision row is written with the reason, the previous status and the reviewer. A database trigger rejects `UPDATE` and `DELETE` on `document_review_decisions`. A correction is a new upload.
6. **Reviewers cannot review their own organization.** This applies to verification and to documents. The reviewer queue excludes such documents, and direct calls return 403.
7. **Upload validation checks file content, not the declared type.** PDF, JPEG and PNG are accepted only when their signature matches the declared type. Size is capped. Duplicates are refused within an organization by SHA-256. The stored filename is random; the uploader's name is kept only for display after sanitising.
8. **Downloads are attachments, never inline.** Responses set `Content-Disposition: attachment`, `X-Content-Type-Options: nosniff` and `Cache-Control: private, no-store`. Every download is audited, including reviewer downloads, which carry the reviewer's identity.
9. **Expiry dates are stated, not verified.** The field is labelled as the organization's statement everywhere it appears.
10. **Audit is append-only at the database level.** Triggers block `UPDATE`, `DELETE` and `TRUNCATE` on `audit_events`.

## Agentic architecture
No AI component was added in this slice. The review gate, publication gate, and upload validation are deterministic code. A future certificate-extraction workflow (P1) must place its output in a pending state for a human reviewer, and it must not reach `decide()` or the publication gate directly.

## Consequences
- **Storage is local filesystem for development and test only.** Production requires private object storage with encryption at rest and malware scanning. Neither exists yet.
- **Compliance score is not implemented.** When it is, it is an indicator computed in code and shown beside verification, never a substitute for it.
- **TRUNCATE is blocked on the audit table only by a statement trigger.** Table owners can still drop tables. Production must restrict DDL and TRUNCATE privileges to a migration role.
- **Document retention and deletion are undefined.** Documents are kept. A retention rule is required before real personal data enters the system (spec decision D9).
- **Reviewer capacity and SLA are not modelled.** The queue is first-in-first-out with no escalation.
