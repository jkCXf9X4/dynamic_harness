from __future__ import annotations

from . import agents as _agents
from . import context as _context
from . import filesystem as _filesystem
from . import network as _network
from . import planning as _planning
from . import process as _process
from .registry import ToolRegistry


def register_default_tools(registry: ToolRegistry) -> None:
    registry.register(_filesystem.TOOL_READ_DEF, _filesystem.read)
    registry.register(_filesystem.TOOL_WRITE_DEF, _filesystem.write)
    registry.register(_filesystem.TOOL_GLOB_DEF, _filesystem.glob)
    registry.register(_filesystem.TOOL_GREP_DEF, _filesystem.grep)
    registry.register(_process.TOOL_BASH_DEF, _process.bash)
    registry.register(_network.TOOL_WEBFETCH_DEF, _network.webfetch)
    registry.register(_filesystem.TOOL_EDIT_DEF, _filesystem.edit)
    registry.register(_agents.TOOL_DELEGATE_DEF, _agents.delegate)
    registry.register(_agents.TOOL_REPORT_DEF, _agents.report)
    registry.register(_agents.TOOL_ESCALATE_DEF, _agents.escalate)
    registry.register(_agents.TOOL_FAIL_DEF, _agents.fail)
    registry.register(_agents.TOOL_ASK_DEF, _agents.ask)
    registry.register(_context.TOOL_COMPRESS_DEF, _context.compress)
    registry.register(_context.TOOL_PRUNE_DEF, _context.prune)
    registry.register(_context.TOOL_RESTORE_DEF, _context.restore)
    registry.register(_planning.TOOL_PLAN_DEF, _planning.plan)
    registry.register(_planning.TOOL_CHECKPOINT_DEF, _planning.checkpoint)
    registry.register(_agents.TOOL_CONVERSE_DEF, _agents.converse)
    registry.register(_agents.TOOL_KILL_DEF, _agents.kill)
    registry.register(_agents.TOOL_STATUS_DEF, _agents.status)
    registry.register(_agents.TOOL_READ_ARTIFACT_DEF, _agents.read_artifact)
    registry.register(_agents.TOOL_USAGE_DEF, _agents.usage)
