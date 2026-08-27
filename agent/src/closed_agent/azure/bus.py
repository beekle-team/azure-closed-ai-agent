from __future__ import annotations

import json
from typing import Protocol

from closed_agent.settings import settings


class IngestBus(Protocol):
    kind: str

    def send(self, payload: dict[str, str]) -> None: ...

    def receive(self, limit: int = 8) -> list[dict[str, str]]: ...


class MemoryBus:
    kind = "memory"

    def __init__(self) -> None:
        self._items: list[dict[str, str]] = []

    def send(self, payload: dict[str, str]) -> None:
        self._items.append(payload)

    def receive(self, limit: int = 8) -> list[dict[str, str]]:
        items = self._items[:limit]
        self._items = self._items[limit:]
        return items


class AzureQueueBus:
    kind = "queue"

    def __init__(self, connection_string: str, queue_name: str) -> None:
        try:
            from azure.storage.queue import QueueClient
        except ImportError as exc:
            raise RuntimeError("azure-storage-queue を入れてください") from exc
        self._queue = QueueClient.from_connection_string(connection_string, queue_name)
        try:
            self._queue.create_queue()
        except Exception as exc:
            if type(exc).__name__ != "ResourceExistsError":
                raise

    def send(self, payload: dict[str, str]) -> None:
        self._queue.send_message(json.dumps(payload, ensure_ascii=False))

    def receive(self, limit: int = 8) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for message in self._queue.receive_messages(max_messages=limit):
            items.append(json.loads(message.content))
            self._queue.delete_message(message)
        return items


class ServiceBusIngest:
    kind = "servicebus"

    def __init__(self, connection_string: str, queue_name: str) -> None:
        try:
            from azure.servicebus import ServiceBusClient
        except ImportError as exc:
            raise RuntimeError("azure-servicebus を入れてください") from exc
        self._client = ServiceBusClient.from_connection_string(connection_string)
        self._queue_name = queue_name

    def send(self, payload: dict[str, str]) -> None:
        from azure.servicebus import ServiceBusMessage

        with self._client.get_queue_sender(self._queue_name) as sender:
            sender.send_messages(ServiceBusMessage(json.dumps(payload, ensure_ascii=False)))

    def receive(self, limit: int = 8) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        with self._client.get_queue_receiver(self._queue_name) as receiver:
            for message in receiver.receive_messages(max_message_count=limit, max_wait_time=1):
                items.append(json.loads(_message_text(message)))
                receiver.complete_message(message)
        return items


def _message_text(message: object) -> str:
    body = getattr(message, "body", message)
    if isinstance(body, str):
        return body
    if isinstance(body, bytes):
        return body.decode("utf-8")
    chunks = list(body)
    if chunks and isinstance(chunks[0], bytes):
        return b"".join(chunks).decode("utf-8")
    return str(message)


def build_bus() -> IngestBus:
    servicebus = settings.azure_servicebus_connection_string.strip()
    if servicebus:
        return ServiceBusIngest(servicebus, settings.azure_servicebus_queue)
    storage = settings.azure_storage_connection_string.strip()
    if storage:
        return AzureQueueBus(storage, settings.azure_ingest_queue)
    return MemoryBus()
