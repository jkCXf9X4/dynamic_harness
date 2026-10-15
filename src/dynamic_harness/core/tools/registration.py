from __future__ import annotations

from typing import Sequence

from . import agents as _agents
from . import artifacts as _artifacts
from . import comms as _comms
from . import context as _context
from . import filesystem as _filesystem
from . import network as _network
from . import planning as _planning
from . import process as _process
from . import result_bash as _result_bash
from . import result_read as _result_read
from . import skills as _skills
from .registry import ToolRegistry


def register_default_tools(
    registry: ToolRegistry,
    model_profiles: Sequence[tuple[str, str]] = (),
) -> None:
    """Register the default tool set.

    ``model_profiles`` is the configured (name, description) list from
    ``config.profiles``; non-empty it adds the ``model_profile`` parameter to
    the ``delegate`` tool so agents can pick a child's model tier.
    """
    registry.register(_filesystem.TOOL_READ_DEF, _filesystem.read)
    registry.register(_filesystem.TOOL_WRITE_DEF, _filesystem.write)
    registry.register(_filesystem.TOOL_GLOB_DEF, _filesystem.glob)
    registry.register(_filesystem.TOOL_GREP_DEF, _filesystem.grep)
    registry.register(_process.TOOL_BASH_DEF, _process.bash)
    registry.register(_network.TOOL_WEBFETCH_DEF, _network.webfetch)
    registry.register(_filesystem.TOOL_EDIT_DEF, _filesystem.edit)
    registry.register(_agents.make_delegate_def(model_profiles), _agents.delegate)
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
    registry.register(_agents.TOOL_RESUME_DEF, _agents.resume)
    registry.register(_agents.TOOL_READ_ARTIFACT_DEF, _agents.read_artifact)
    registry.register(_agents.TOOL_USAGE_DEF, _agents.usage)
    registry.register(_artifacts.TOOL_ARCHIVE_DEF, _artifacts.archive)
    registry.register(_result_read.TOOL_RESULT_READ_DEF, _result_read.result_read)
    registry.register(_result_bash.TOOL_RESULT_BASH_DEF, _result_bash.result_bash)
    registry.register(_skills.TOOL_SKILL_LOAD_DEF, _skills.skill_load)
    # Communication layer (all topology cells share this surface).
    registry.register(_comms.TOOL_POST_DEF, _comms.post)
    registry.register(_comms.TOOL_CHANNEL_READ_DEF, _comms.channel_read)
    registry.register(_comms.TOOL_CHANNELS_DEF, _comms.channels)
    registry.register(_comms.TOOL_CHANNEL_INFO_DEF, _comms.channel_info)
    registry.register(_comms.TOOL_SUBSCRIBE_DEF, _comms.subscribe)
    registry.register(_comms.TOOL_UNSUBSCRIBE_DEF, _comms.unsubscribe)
    registry.register(_comms.TOOL_MESSAGE_DEF, _comms.message)
