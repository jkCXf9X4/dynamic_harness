from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ...artifact.store import Artifact, ArtifactView
from .filesystem import resolve_safe_path
from .registry import ToolDef

if TYPE_CHECKING:
    from ...core.tool_context import ToolContext


TOOL_ARCHIVE_DEF = ToolDef(
    name="archive",
    description="Persist a working file or a block of findings into the durable "
                "artifact store DURING your run — not just at report(). This gives "
                "the content a stable, unique artifact id (returned) that stays "
                "discoverable after the run via the artifact index and can be "
                "reported to your parent (put the id in report's artifact_ids). "
                "Use this instead of leaving relevant scratch/temp files scattered "
                "in the generated working dir: archive anything a future run or "
                "your parent may need, then delete the scratch copy in cleanup. "
                "Provide EITHER 'path' (an existing on-disk file, copied verbatim "
                "into storage) OR inline 'content'. Returns the new artifact id, "
                "its stable file name, AND the full on-disk path — you can keep "
                "editing the archived file with the ordinary read()/write()/edit() "
                "tools via that path.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path to an existing file to archive/copy verbatim into the artifact store. Use instead of 'content' when the data already lives on disk.",
            },
            "content": {
                "type": "string",
                "description": "Inline text to persist as a new artifact file (use instead of 'path' when the content is not yet on disk).",
            },
            "label": {
                "type": "string",
                "description": "Optional file/display name for the archived content (defaults to the source file's basename, or 'findings.txt' for inline content).",
            },
            "summary": {
                "type": "string",
                "description": "Optional short summary of what this archived artifact contains (used as its cheap headline/preview view).",
            },
        },
        "required": [],
    },
)


async def archive(
    *,
    ctx: ToolContext,
    path: str | None = None,
    content: str | None = None,
    label: str | None = None,
    summary: str | None = None,
) -> str:
    if path and content is not None:
        return ("Error: provide either 'path' (archive an existing file) or "
                "'content' (inline text), not both.")

    if path:
        try:
            safe = resolve_safe_path(path, ctx)
        except ValueError as e:
            return f"Error: {e}"
        if not safe.is_file():
            return f"Error: no such file at {path}"
        body = safe.read_text(encoding="utf-8", errors="replace")
        stored_name = safe.name
    elif content is not None:
        body = content
        stored_name = label or "findings.txt"
    else:
        return ("Error: provide 'path' or 'content' — at least one is required "
                "to archive.")

    headline = label or (stored_name if path else "Untitled artifact")
    summary_text = (summary or headline) or ""
    view = ArtifactView(
        headline=headline[:200],
        summary_200=summary_text[:200],
        summary_1000=summary_text[:1000] if len(summary_text) > 200 else "",
        full_report=body if not path and stored_name.endswith((".md", ".txt")) else "",
        raw_data=body,
    )
    art = Artifact(task_id=ctx.task_id, agent_id=ctx.agent_id, views=view)
    ctx.artifact_store.save(art)
    # Mirror the on-disk location ArtifactStore.write_text uses so ordinary
    # read()/write()/edit() on this artifact's file keep working after archive.
    store_path = ctx.artifact_store.root / art.id / stored_name
    ctx.artifact_store.write_text(art.id, stored_name, body)
    ctx.record_archived_artifact(art.id)

    return (
        f"Archived {art.id} ({stored_name}, {len(body)} chars) at "
        f"{store_path}\n"
        f"Read back with read_artifact(id='{art.id}'), re-read files with "
        f"read_artifact(id='{art.id}', file='{stored_name}'), or use the "
        f"ordinary read()/write()/edit() tools on the full path above. "
        f"Include artifact_id '{art.id}' in report()'s artifact_ids."
    )