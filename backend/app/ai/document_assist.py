"""Reviewer assist for a single uploaded compliance document.

Mirrors app.ai.assist: this produces a *proposal* for a human reviewer, with a citation
for every claim, and decides nothing. app.routers.admin owns the review decision, and
nothing here writes to the database or changes document state.

Two code paths:
  - Deterministic (default): page text is read from the PDF and matched against explicit
    patterns. No network call, no model, same input gives the same output every time.
  - LLM-assisted (only when VITA_LLM_API_KEY is set): asks a model to phrase the same
    extracted facts more usefully. Any failure falls back to the deterministic draft --
    a reviewer must never be blocked by an optional convenience.

Every finding carries the page it came from, so a reviewer can check it in seconds
instead of reading the whole file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

import httpx

from app.config import settings
from app.models import Document, DocumentType

# A PAN is five letters, four digits, one letter.
_PAN = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
# Indian registration/80G/12A references vary; this catches the common labelled forms.
_REGISTRATION = re.compile(
    r"(?:registration|regn\.?|reg\.?|certificate)\s*(?:no\.?|number|#)?\s*[:\-]?\s*([A-Z0-9][A-Z0-9/\-]{4,25})",
    re.IGNORECASE,
)
_SECTION_REF = re.compile(r"\b(80\s*-?\s*G|12\s*-?\s*A{1,2}B?)\b", re.IGNORECASE)
_DATE = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})\b")
_VALIDITY_HINT = re.compile(r"valid\s+(?:up\s*to|until|till|through)", re.IGNORECASE)


@dataclass
class Finding:
    """One extracted fact and where it was found."""

    label: str
    value: str
    page: int  # 1-indexed, as a human counts pages


@dataclass
class DocumentAssistDraft:
    summary: str
    findings: list[Finding] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    page_count: int = 0
    text_extractable: bool = True
    generated_by: str = "rules"


def extract_pdf_pages(content: bytes) -> list[str]:
    """Per-page text. Returns [] when the bytes are not a readable PDF.

    A scanned document yields pages that are empty strings: real pages, no text layer.
    That distinction matters to the caller, so it is preserved rather than filtered out.
    """
    try:
        from io import BytesIO

        from pypdf import PdfReader

        reader = PdfReader(BytesIO(content))
        pages = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception:
                pages.append("")
        return pages
    except Exception:
        return []


def _parse_date(match: re.Match[str]) -> date | None:
    day, month, year = (int(g) for g in match.groups())
    # Day and month are ambiguous across formats; swap when the first value cannot be a day.
    if day > 31 or month > 12:
        day, month = month, day
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _deterministic_draft(doc: Document, pages: list[str]) -> DocumentAssistDraft:
    sources: list[str] = [f"document:{doc.id}"]
    findings: list[Finding] = []
    flags: list[str] = []

    if not pages:
        return DocumentAssistDraft(
            summary=(
                f"{doc.title} could not be read as a PDF, so nothing was extracted. "
                "Open the file and review it manually."
            ),
            flags=["File could not be parsed as a PDF"],
            sources=sources,
            page_count=0,
            text_extractable=False,
        )

    non_empty = [i for i, text in enumerate(pages) if text.strip()]
    if not non_empty:
        return DocumentAssistDraft(
            summary=(
                f"{doc.title} has {len(pages)} page(s) but no text layer, which usually means "
                "a scan or photograph. Nothing could be extracted; this one needs human eyes."
            ),
            flags=["Scanned document: no text to extract", "Needs manual reading"],
            sources=sources,
            page_count=len(pages),
            text_extractable=False,
        )

    seen: set[tuple[str, str]] = set()

    def add(label: str, value: str, page_index: int) -> None:
        key = (label, value.upper())
        if key in seen:
            return
        seen.add(key)
        findings.append(Finding(label=label, value=value, page=page_index + 1))
        sources.append(f"document:{doc.id}:page:{page_index + 1}")

    today = date.today()
    for i, text in enumerate(pages):
        if not text.strip():
            continue
        upper = text.upper()

        for m in _PAN.finditer(upper):
            add("PAN", m.group(1), i)
        for m in _REGISTRATION.finditer(text):
            candidate = m.group(1).strip()
            # A bare year is a false positive, not a registration number.
            if not candidate.isdigit() or len(candidate) > 4:
                add("Registration reference", candidate, i)
        for m in _SECTION_REF.finditer(text):
            add("Section reference", re.sub(r"\s|-", "", m.group(1)).upper(), i)

        has_validity_language = bool(_VALIDITY_HINT.search(text))
        for m in _DATE.finditer(text):
            parsed = _parse_date(m)
            if parsed is None:
                continue
            label = "Validity date" if has_validity_language else "Date"
            add(label, parsed.isoformat(), i)
            if has_validity_language and parsed < today:
                flags.append(f"States a validity date in the past ({parsed.isoformat()}, page {i + 1})")

    # Cross-check what was found against what the document claims to be.
    labels = {f.label for f in findings}
    if doc.doc_type is DocumentType.PAN and "PAN" not in labels:
        flags.append("Filed as a PAN document, but no PAN-formatted number was found")
    if doc.doc_type in (DocumentType.SECTION_80G, DocumentType.SECTION_12A):
        expected = "80G" if doc.doc_type is DocumentType.SECTION_80G else "12A"
        refs = {f.value for f in findings if f.label == "Section reference"}
        if not any(r.startswith(expected[:3]) for r in refs):
            flags.append(f"Filed as {doc.doc_type.value}, but no {expected} reference was found in the text")

    if doc.valid_until_stated and doc.valid_until_stated < today:
        flags.append(f"The uploader stated this expired on {doc.valid_until_stated.isoformat()}")

    if not findings:
        flags.append("No identifiers were recognised; read the document directly")

    summary = (
        f"{doc.title} ({doc.doc_type.value}), {len(pages)} page(s). "
        + (
            f"Found {len(findings)} identifier(s): "
            + "; ".join(f"{f.label} {f.value} on page {f.page}" for f in findings[:6])
            + ("; …" if len(findings) > 6 else "")
            + "."
            if findings
            else "No recognisable identifiers were extracted."
        )
    )

    return DocumentAssistDraft(
        summary=summary,
        findings=findings,
        flags=flags,
        sources=sources,
        page_count=len(pages),
        text_extractable=True,
    )


def _llm_draft(doc: Document, base: DocumentAssistDraft) -> DocumentAssistDraft | None:
    """Ask a model to phrase `base` more usefully. Returns None on any failure."""
    if not settings.llm_api_key:
        return None
    facts = "; ".join(f"{f.label}: {f.value} (page {f.page})" for f in base.findings) or "none extracted"
    prompt = (
        "You are drafting a note for a human reviewer checking a nonprofit's compliance "
        "document. Rewrite the following extracted facts as a short, neutral summary. "
        "Do not add any fact that is not listed. Keep every page number. Do not say whether "
        "the document should be accepted or rejected.\n\n"
        f"Document type: {doc.doc_type.value}\n"
        f"Title: {doc.title}\n"
        f"Pages: {base.page_count}\n"
        f"Extracted: {facts}\n"
        f"Concerns already identified: {'; '.join(base.flags) if base.flags else 'none'}\n"
    )
    try:
        response = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": settings.llm_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.llm_model,
                "max_tokens": 400,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=10.0,
        )
        response.raise_for_status()
        text = response.json()["content"][0]["text"].strip()
        if not text:
            return None
        return DocumentAssistDraft(
            summary=text,
            findings=base.findings,
            flags=base.flags,
            sources=base.sources,
            page_count=base.page_count,
            text_extractable=base.text_extractable,
            generated_by=f"llm:{settings.llm_model}",
        )
    except Exception:
        # Network, auth, schema or timeout failure: the reviewer gets the deterministic
        # draft instead. This is a convenience layer, not a dependency.
        return None


def draft_document_assist(doc: Document, content: bytes) -> DocumentAssistDraft:
    base = _deterministic_draft(doc, extract_pdf_pages(content))
    return _llm_draft(doc, base) or base
