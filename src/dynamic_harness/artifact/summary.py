from __future__ import annotations

from ..artifact.store import Artifact
from ..core.policies.disclosure import DisclosurePolicy


def summarize_artifact(artifact: Artifact, target_tokens: int = 200) -> str:
    return DisclosurePolicy.pick_for_token_budget(artifact, target_tokens)


def hierarchical_summary(
    artifacts: list[Artifact],
    level_name: str = "executive",
    max_items: int = 10,
) -> str:
    lines: list[str] = []
    lines.append(f"# {level_name.replace('_', ' ').title()} Summary")
    lines.append("")

    for art in artifacts[:max_items]:
        lines.append(f"## Artifact {art.id}")
        lines.append(f"  {summarize_artifact(art, 200)}")
        if art.views.technical:
            lines.append(f"  Technical: {art.views.technical[:200]}")
        lines.append("")

    return "\n".join(lines)