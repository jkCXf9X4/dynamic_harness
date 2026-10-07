from __future__ import annotations

import argparse
import functools
import tempfile
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from ..config import load_harness_config
from ..core.runtime import Runtime
from ..llm.registry import ProviderRegistry


@functools.lru_cache(maxsize=1)
def workspace_dir() -> Path:
    ts = datetime.now().strftime("%y%m%d_%H%M%S")
    tmp_id = uuid4().hex[:4]
    return Path.cwd() / ".dynamic-harness" / f"{ts}_{tmp_id}"


def build_runtime(args: argparse.Namespace) -> Runtime:
    if args.temp:
        artifact_root = Path(args.artifact_dir) if args.artifact_dir else Path(tempfile.mkdtemp())
        repo_root = Path(args.repo_dir) if args.repo_dir else Path(tempfile.mkdtemp())
        trace_root = None
        checkpoint_root = None
    else:
        base = workspace_dir()
        artifact_root = Path(args.artifact_dir) if args.artifact_dir else base / "artifacts"
        repo_root = Path(args.repo_dir) if args.repo_dir else base / "repo"
        trace_root = base / "traces"
        checkpoint_root = base / "checkpoints"
        base.mkdir(parents=True, exist_ok=True)
        artifact_root.mkdir(parents=True, exist_ok=True)
        repo_root.mkdir(parents=True, exist_ok=True)

    config = load_harness_config(getattr(args, "config", None))
    # The registry resolves the active model (``--model``/``--provider``
    # override the config) and owns provider construction + credentials, so
    # the four construction sites stop duplicating ``OpenAIProvider`` wiring.
    registry = ProviderRegistry.from_config(
        config,
        model_ref=args.model,
        provider=getattr(args, "provider", None),
        api_key=args.api_key,
        base_url=args.base_url,
    )
    rt = Runtime(
        artifact_root=artifact_root,
        repo_root=repo_root,
        trace_root=trace_root,
        checkpoint_root=checkpoint_root,
        config=config,
        provider_registry=registry,
    )

    load_dotenv()
    api_key = args.api_key or registry.api_key_for(registry.active_provider_id)
    if api_key:
        rt.set_llm(registry.select())
    return rt
