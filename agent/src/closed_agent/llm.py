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
        return Completion(text=_mock_from_context(user), input_tokens=16, output_tokens=48)

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


def _mock_from_context(user: str) -> str:
    lines = [line[2:].strip() for line in user.splitlines() if line.startswith("- ")]
    if not lines:
        return "手元の規程・口伝・スキルに、この質問の根拠は見つかりませんでした。"
    parts = ["根拠になった関係と原本は次です。"]
    parts.extend(f"・{line}" for line in lines[:6])
    if any("口伝" in line or "Tacit" in line or "保険" in line or "一声" in line for line in lines):
        parts.append("マニュアルに無い確認は口伝として残っています。スキル化できるものは提案できます。")
    return "\n".join(parts)
