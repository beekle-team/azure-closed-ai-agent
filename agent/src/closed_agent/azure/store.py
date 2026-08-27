from __future__ import annotations

from pathlib import Path
from typing import Protocol

from closed_agent.settings import settings


class DocumentStore(Protocol):
    kind: str

    def put(self, path: str, body: str) -> str: ...

    def get(self, path: str) -> str: ...


class FilesystemStore:
    kind = "filesystem"

    def __init__(self, root: Path) -> None:
        self.root = root

    def put(self, path: str, body: str) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / Path(path).name
        target.write_text(body, encoding="utf-8")
        return str(target)

    def get(self, path: str) -> str:
        target = self.root / Path(path).name
        return target.read_text(encoding="utf-8")


class AzureBlobStore:
    kind = "blob"

    def __init__(self, connection_string: str, container: str) -> None:
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:
            raise RuntimeError("azure-storage-blob を入れてください") from exc
        self._client = BlobServiceClient.from_connection_string(connection_string)
        self._container_name = container
        self._container = self._client.get_container_client(container)
        try:
            self._container.create_container()
        except Exception as exc:
            if type(exc).__name__ != "ResourceExistsError":
                raise

    def put(self, path: str, body: str) -> str:
        name = Path(path).name
        self._container.upload_blob(name, body.encode("utf-8"), overwrite=True)
        return f"{self._container_name}/{name}"

    def get(self, path: str) -> str:
        name = Path(path).name
        data = self._container.download_blob(name).readall()
        return data.decode("utf-8")


class MemoryStore:
    kind = "memory"

    def __init__(self) -> None:
        self._items: dict[str, str] = {}

    def put(self, path: str, body: str) -> str:
        name = Path(path).name
        self._items[name] = body
        return name

    def get(self, path: str) -> str:
        return self._items[Path(path).name]


def build_store(corpus_dir: Path) -> DocumentStore:
    connection = settings.azure_storage_connection_string.strip()
    if connection:
        return AzureBlobStore(connection, settings.azure_blob_container)
    return FilesystemStore(corpus_dir)
