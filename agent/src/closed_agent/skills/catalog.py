from dataclasses import dataclass
from pathlib import Path

from closed_agent.retrieve.types import RetrievalHit


@dataclass
class Skill:
    id: str
    name: str
    description: str
    approval: bool
    triggers: list[str]
    body: str


class SkillCatalog:
    def __init__(self, skills_dir: Path) -> None:
        self.skills: list[Skill] = []
        if skills_dir.exists():
            for path in sorted(skills_dir.glob("*.md")):
                self.skills.append(_parse(path.read_text(encoding="utf-8"), path.stem))

    def get(self, skill_id: str) -> Skill | None:
        return next((skill for skill in self.skills if skill.id == skill_id), None)

    def match(self, question: str) -> Skill | None:
        for skill in self.skills:
            if skill.name in question or skill.id in question:
                return skill
            if any(trigger in question for trigger in skill.triggers) and any(
                verb in question for verb in ("回して", "実行", "動かして", "スキル")
            ):
                return skill
        scored = []
        for skill in self.skills:
            hits = sum(1 for trigger in skill.triggers if trigger in question)
            if hits:
                scored.append((hits, skill))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[0][1] if scored else None

    def as_hits(self, question: str) -> list[RetrievalHit]:
        hits: list[RetrievalHit] = []
        for skill in self.skills:
            if any(trigger in question for trigger in skill.triggers) or skill.name in question:
                hits.append(
                    RetrievalHit(
                        name=skill.name,
                        kind="Skill",
                        reason=skill.description,
                        source="skills",
                        text=skill.body,
                    )
                )
        return hits


def _parse(raw: str, fallback_id: str) -> Skill:
    if not raw.startswith("---"):
        return Skill(fallback_id, fallback_id, "", False, [], raw)
    _, front, body = raw.split("---", 2)
    fields: dict[str, str] = {}
    triggers: list[str] = []
    current = ""
    for line in front.splitlines():
        if line.startswith("triggers:"):
            current = "triggers"
            continue
        if current == "triggers" and line.strip().startswith("- "):
            triggers.append(line.strip()[2:])
            continue
        if ":" in line and not line.startswith(" "):
            current = ""
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip("'\"")
    return Skill(
        id=fields.get("id", fallback_id),
        name=fields.get("name", fallback_id),
        description=fields.get("description", ""),
        approval=fields.get("approval", "false").lower() == "true",
        triggers=triggers,
        body=body.strip(),
    )
