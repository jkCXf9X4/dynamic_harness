from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv

from ..core.runtime import Runtime
from ..llm.openai_provider import OpenAIProvider


def build_runtime(
    args: argparse.Namespace,
    *,
    register_handlers: bool = True,
    on_report=None,
    on_failure=None,
) -> Runtime:
    if args.temp:
        artifact_root = Path(args.artifact_dir) if args.artifact_dir else Path(tempfile.mkdtemp())
        repo_root = Path(args.repo_dir) if args.repo_dir else Path(tempfile.mkdtemp())
    else:
        base = Path.home() / ".dynamic-harness"
        artifact_root = Path(args.artifact_dir) if args.artifact_dir else base / "artifacts"
        repo_root = Path(args.repo_dir) if args.repo_dir else base / "repo"
        artifact_root.mkdir(parents=True, exist_ok=True)
        repo_root.mkdir(parents=True, exist_ok=True)
    rt = Runtime(artifact_root=artifact_root, repo_root=repo_root)

    if register_handlers:
        if on_report:
            rt.on_report(on_report)
        if on_failure:
            rt.on_failure(on_failure)

    if not args.no_llm:
        load_dotenv()
        api_key = args.api_key or os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if api_key:
            model = args.model or os.environ.get("LLM_MODEL", "deepseek/deepseek-v4-flash")
            base_url = args.base_url or os.environ.get("LLM_BASE_URL", "https://openrouter.ai/api/v1")
            llm = OpenAIProvider(model=model, base_url=base_url, api_key=api_key, verify_ssl=False)
            rt.set_llm(llm)
    return rt