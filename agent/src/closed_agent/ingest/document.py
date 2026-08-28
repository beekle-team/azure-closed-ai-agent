from pathlib import Path


def parse_stored(text: str, fallback_name: str) -> tuple[str, str, dict[str, str]]:
    lines = text.splitlines()
    title = Path(fallback_name).stem
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        lines = lines[1:]
    meta: dict[str, str] = {}
    while lines:
        raw = lines[0].strip()
        if raw == "":
            lines = lines[1:]
            continue
        if ":" in raw and raw.split(":", 1)[0] in {
            "source_system",
            "source_url",
            "kind",
            "department",
            "classification",
        }:
            key, value = raw.split(":", 1)
            meta[key.strip()] = value.strip()
            lines = lines[1:]
            continue
        break
    return title, "\n".join(lines).strip(), meta


def render_stored(
    *,
    title: str,
    body: str,
    kind: str,
    source_system: str,
    source_url: str = "",
    department: str = "",
    classification: str = "",
) -> str:
    header = [f"# {title}", "", f"source_system: {source_system}", f"kind: {kind}"]
    if source_url:
        header.append(f"source_url: {source_url}")
    if department:
        header.append(f"department: {department}")
    if classification:
        header.append(f"classification: {classification}")
    header.append("")
    header.append(body.strip())
    return "\n".join(header) + "\n"
