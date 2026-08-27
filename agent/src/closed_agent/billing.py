from typing import Any

import httpx

from closed_agent.settings import settings


class QuotaExceededError(RuntimeError):
    pass


class BillingClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(timeout=10.0)

    async def access(self, user_id: int) -> dict[str, Any]:
        response = await self._client.get(
            f"{settings.internal_api_base_url}/api/internal/agent-access",
            params={"user_id": user_id},
            headers={"X-Internal-Token": settings.internal_token},
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("allowed"):
            raise QuotaExceededError("monthly token quota exceeded")
        return payload

    async def record(
        self,
        *,
        user_id: int,
        organization_id: int,
        request_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> dict[str, Any]:
        response = await self._client.post(
            f"{settings.internal_api_base_url}/api/internal/usage",
            headers={"X-Internal-Token": settings.internal_token},
            json={
                "user_id": user_id,
                "organization_id": organization_id,
                "request_id": request_id,
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            },
        )
        if response.status_code == 402:
            raise QuotaExceededError("monthly token quota exceeded")
        response.raise_for_status()
        return response.json()
