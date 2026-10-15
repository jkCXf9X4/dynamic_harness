"""Regression tests for the ``Harness`` programmatic API wrapper."""

from __future__ import annotations

import pytest

from dynamic_harness import Harness
from dynamic_harness.llm.registry import ProviderCredentialError

LLM_CONFIG: dict = {
    "model": "prov/model",
    "providers": {
        "prov": {
            "name": "P",
            "env": ["UNSET_KEY"],
            "base_url": "https://example.invalid/v1",
            "models": {"model": {"name": "M"}},
        }
    },
}


def test_harness_llm_config_no_nameerror(tmp_path) -> None:
    """BUG #1 regression: ``Harness(llm_config=...)`` raised ``NameError``
    (missing ``HarnessConfig`` import) before config validation even ran.
    Keyless construction now fails with the credential gate instead —
    see test_harness_llm_config_constructs_with_credential."""
    with pytest.raises(ProviderCredentialError) as excinfo:
        Harness(
            artifact_root=str(tmp_path / "artifacts"),
            repo_root=str(tmp_path / "repo"),
            llm_config=LLM_CONFIG,
        )
    assert "UNSET_KEY" in str(excinfo.value)


def test_harness_llm_config_constructs_with_credential(tmp_path, monkeypatch) -> None:
    """With a credential in the environment, the documented convenience
    path validates the v2 config shape and constructs fully."""
    monkeypatch.setenv("UNSET_KEY", "test-key")
    harness = Harness(
        artifact_root=str(tmp_path / "artifacts"),
        repo_root=str(tmp_path / "repo"),
        llm_config=LLM_CONFIG,
    )
    assert harness.runtime.provider_registry is not None
