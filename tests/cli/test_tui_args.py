from __future__ import annotations

from pathlib import Path

import pytest

from dynamic_harness.cli.terminal import _parse_args


@pytest.mark.asyncio
async def test_m_flag_parses_prompt_file() -> None:
    args = _parse_args(["-m", "prompts/file_inventory.txt"])
    assert args.m == "prompts/file_inventory.txt"


@pytest.mark.asyncio
async def test_m_flag_file_missing() -> None:
    args = _parse_args(["-m", "prompts/nonexistent.txt"])
    assert args.m == "prompts/nonexistent.txt"
    assert not Path(args.m).exists()


@pytest.mark.asyncio
async def test_m_flag_no_llm() -> None:
    args = _parse_args(["-m", "prompts/file_inventory.txt", "--no-llm"])
    assert args.m == "prompts/file_inventory.txt"
    assert args.no_llm is True


@pytest.mark.asyncio
async def test_inline_prompt() -> None:
    args = _parse_args(["list", "all", "files"])
    assert args.prompt == ["list", "all", "files"]


@pytest.mark.asyncio
async def test_tui_flag() -> None:
    args = _parse_args(["--tui"])
    assert args.tui is True


@pytest.mark.asyncio
async def test_interactive_flag() -> None:
    args = _parse_args(["-i"])
    assert args.interactive is True