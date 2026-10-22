"""Pure rules. No database: these run fast and pin the deterministic gates."""

import pytest

from app.documents.validation import UploadError, safe_filename, validate_upload
from app.domain.review import ReviewError, decide
from app.domain.profile import publish_blockers
from app.documents.storage import LocalDocumentStorage
from app.models import NgoProfile, OrgType, ReviewStatus, VerificationStatus

PDF = b"%PDF-1.7\n" + b"x" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"x" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 64
MB = 1024 * 1024


def test_decide_allows_first_decision_with_reason():
    assert decide(ReviewStatus.PENDING_REVIEW, ReviewStatus.APPROVED, "Matches the registry") is ReviewStatus.APPROVED
    assert decide(ReviewStatus.PENDING_REVIEW, ReviewStatus.REJECTED, "Name differs") is ReviewStatus.REJECTED


@pytest.mark.parametrize("current", [ReviewStatus.APPROVED, ReviewStatus.REJECTED])
def test_decided_documents_are_final(current):
    with pytest.raises(ReviewError, match="already"):
        decide(current, ReviewStatus.APPROVED, "changed my mind")


def test_decision_requires_non_blank_reason():
    with pytest.raises(ReviewError, match="reason"):
        decide(ReviewStatus.PENDING_REVIEW, ReviewStatus.APPROVED, "   ")


def test_pending_is_not_a_decision():
    with pytest.raises(ReviewError, match="APPROVED or REJECTED"):
        decide(ReviewStatus.PENDING_REVIEW, ReviewStatus.PENDING_REVIEW, "reason")


def _profile(**overrides):
    base = dict(mission="Clean water in rural Odisha", sectors=["Water"], geographies=["Odisha"])
    base.update(overrides)
    return NgoProfile(**base)


def test_publish_blockers_lists_every_reason_at_once():
    blockers = publish_blockers(OrgType.CSR, VerificationStatus.PENDING, None)
    assert len(blockers) == 5  # org type, verification, mission, sectors, geographies
    assert any("NGO organizations" in b for b in blockers)
    assert any("verified" in b for b in blockers)
    assert any("mission" in b for b in blockers)


def test_publish_blockers_empty_when_complete_and_verified():
    assert publish_blockers(OrgType.NGO, VerificationStatus.APPROVED, _profile()) == []


def test_publish_blocked_when_not_verified_even_if_profile_complete():
    blockers = publish_blockers(OrgType.NGO, VerificationStatus.REJECTED, _profile())
    assert blockers == ["The organization must be verified by Imparency before its profile can be published"]


def test_upload_accepts_matching_signature():
    assert validate_upload(PDF, "application/pdf", 10 * MB) == "application/pdf"
    assert validate_upload(JPEG, "image/jpeg", 10 * MB) == "image/jpeg"
    assert validate_upload(PNG, "image/png", 10 * MB) == "image/png"


def test_upload_rejects_declared_type_that_does_not_match_content():
    with pytest.raises(UploadError, match="does not match"):
        validate_upload(PNG, "application/pdf", 10 * MB)


def test_upload_rejects_disallowed_declared_type_even_with_valid_pdf_bytes():
    with pytest.raises(UploadError, match="Only PDF, JPEG and PNG"):
        validate_upload(PDF, "text/html", 10 * MB)


def test_upload_rejects_unrecognised_content():
    with pytest.raises(UploadError, match="not a PDF, JPEG or PNG"):
        validate_upload(b"<html>not a pdf</html>", "application/pdf", 10 * MB)


def test_upload_rejects_empty_and_oversized():
    with pytest.raises(UploadError, match="empty"):
        validate_upload(b"", "application/pdf", 10 * MB)
    with pytest.raises(UploadError, match="larger than"):
        validate_upload(PDF, "application/pdf", 10)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("../../etc/passwd", "passwd"),
        ("C:\\Users\\x\\evil.pdf", "evil.pdf"),
        ("reg\x00istration:2024.pdf", "reg_istration_2024.pdf"),
        ("", "document"),
        (None, "document"),
        ("...", "document"),
    ],
)
def test_safe_filename(raw, expected):
    assert safe_filename(raw) == expected


def test_storage_roundtrip_and_rejects_traversal_keys(tmp_path):
    store = LocalDocumentStorage(str(tmp_path))
    key = store.put(b"hello")
    assert store.read(key) == b"hello"
    with pytest.raises(ValueError, match="Invalid storage key"):
        store.read("../secret")
    with pytest.raises(ValueError, match="Invalid storage key"):
        store.read("/etc/passwd")
