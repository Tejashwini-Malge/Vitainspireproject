from functools import lru_cache

from app.config import settings
from app.documents.storage import LocalDocumentStorage


@lru_cache
def get_storage() -> LocalDocumentStorage:
    return LocalDocumentStorage(settings.storage_dir)
