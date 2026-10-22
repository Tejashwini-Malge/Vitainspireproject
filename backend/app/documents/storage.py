"""Private file storage. Keys are random; user-supplied names never reach the filesystem path."""

import os
import re
import uuid
from pathlib import Path

_KEY = re.compile(r"^[0-9a-f]{32}$")


class LocalDocumentStorage:
    """Development and test backend. Production must use object storage with encryption at rest (see README)."""

    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise ValueError("Invalid storage key")
        return self.root / key[:2] / key

    def put(self, content: bytes) -> str:
        key = uuid.uuid4().hex
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # O_EXCL: never overwrite an existing object. Owner-only permissions.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return key

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()
