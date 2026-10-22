"""Upload validation. The declared type is checked against the file's own signature."""

import re
from pathlib import PurePosixPath, PureWindowsPath

ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}

_SIGNATURES: list[tuple[bytes, str]] = [
    (b"%PDF-", "application/pdf"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


class UploadError(ValueError):
    pass


def sniff_type(content: bytes) -> str | None:
    for magic, mime in _SIGNATURES:
        if content.startswith(magic):
            return mime
    return None


def validate_upload(content: bytes, declared_type: str, max_bytes: int) -> str:
    """Return the verified content type, or raise UploadError with a reason the uploader can act on."""
    if not content:
        raise UploadError("The file is empty")
    if len(content) > max_bytes:
        raise UploadError(f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit")
    if declared_type not in ALLOWED_TYPES:
        raise UploadError("Only PDF, JPEG and PNG files are accepted")
    actual = sniff_type(content)
    if actual is None:
        raise UploadError("The file content is not a PDF, JPEG or PNG")
    if actual != declared_type:
        raise UploadError("The file content does not match its file type")
    return actual


def safe_filename(name: str | None) -> str:
    """Keep a readable name for downloads. Never used as a storage path."""
    base = PureWindowsPath(PurePosixPath(name or "").name).name  # strip any directory parts from either OS style
    cleaned = re.sub(r"[\x00-\x1f\x7f\\/:*?\"<>|]", "_", base).strip(" .")
    return (cleaned or "document")[:255]
