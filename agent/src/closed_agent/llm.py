from dataclasses import dataclass

from openai import AsyncAzureOpenAI

from closed_agent.settings import settings


@dataclass
class Completion:
    text: str
    input_tokens: int
    output_tokens: int


async def complete(*, system: str, user: str) -> Completion:
    if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
        return Completion(
            text="(モック) グラフ上の関係だけを根拠に回答します。Azure OpenAI の接続後に実応答へ切り替わります。",
            input_tokens=12,
            output_tokens=24,
        )

    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )
    response = await client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    usage = response.usage
    return Completion(
        text=response.choices[0].message.content or "",
        input_tokens=usage.prompt_tokens if usage else 0,
        output_tokens=usage.completion_tokens if usage else 0,
    )
