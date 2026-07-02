from __future__ import annotations

from ..artifact.store import Artifact, ArtifactView


def summarize_artifact(artifact: Artifact, target_tokens: int = 200) -> str:
    if target_tokens <= 200:
        return artifact.views.headline or artifact.views.summary_200
    elif target_tokens <= 1000:
        return artifact.views.summary_1000 or artifact.views.summary_200
    else:
        return artifact.views.technical or artifact.views.summary_1000


def hierarchical_summary(
    artifacts: list[Artifact],
    level_name: str = "executive",
    max_items: int = 10,
) -> str:
    lines: list[str] = []
    lines.append(f"# {level_name.title()} Summary")
    lines.append("")

    for art in artifacts[:max_items]:
        lines.append(f"## Artifact {art.id}")
        lines.append(f"  {summarize_artifact(art, 200)}")
        if art.views.technical:
            lines.append(f"  Technical: {art.views.technical[:200]}")
        lines.append("")

    return "\n".join(lines)