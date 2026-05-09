"""Multi-swarm registry + SwitchSwarm + DispatchToSwarm.

These tests exercise the routing and validation layers — they do NOT
construct full sub-agencies (that would need the live LLM stack), only
the parts that decide where work goes and what gets refused.
"""

from __future__ import annotations

import importlib
import os
import sys
import types

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError


# ── Registry shape ─────────────────────────────────────────────────────────

def test_registry_has_three_swarms():
    from swarms import SWARMS

    assert set(SWARMS) == {"metaswarm", "openswarm", "softdev"}


def test_each_entry_is_factory_plus_description():
    from swarms import SWARMS

    for slug, entry in SWARMS.items():
        assert isinstance(entry, tuple) and len(entry) == 2, f"{slug} malformed"
        factory, desc = entry
        assert callable(factory), f"{slug} factory not callable"
        assert isinstance(desc, str) and desc, f"{slug} missing description"


def test_default_slug_is_metaswarm():
    from swarms import default_slug

    assert default_slug() == "metaswarm"


def test_get_factory_unknown_raises_keyerror():
    from swarms import get_factory

    with pytest.raises(KeyError, match="Unknown swarm"):
        get_factory("bedrock-of-wisdom")


def test_get_factory_returns_callable_for_each_slug():
    from swarms import SWARMS, get_factory

    for slug in SWARMS:
        assert callable(get_factory(slug))


# ── SwitchSwarm tool ──────────────────────────────────────────────────────

def _load_switch_swarm(env_path, monkeypatch):
    """Re-import SwitchSwarm with ENV_PATH redirected to a tmp .env."""
    sys.modules.pop("orchestrator.tools.SwitchSwarm", None)
    mod = importlib.import_module("orchestrator.tools.SwitchSwarm")
    monkeypatch.setattr(mod, "ENV_PATH", env_path)
    return mod.SwitchSwarm


@pytest.fixture
def env_path(tmp_path):
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    return env


@pytest.fixture
def flag_path(tmp_path, monkeypatch):
    flag = tmp_path / "switch.flag"
    monkeypatch.setenv("OPENSWARM_SWITCH_FLAG", str(flag))
    return flag


def test_switch_swarm_unknown_slug_returns_error(env_path, flag_path, monkeypatch):
    SwitchSwarm = _load_switch_swarm(env_path, monkeypatch)
    result = SwitchSwarm(swarm="nope").run()
    assert "Unknown swarm" in result
    assert dotenv_values(str(env_path)).get("OPENSWARM_SWARM") in (None, "")


def test_switch_swarm_writes_env_and_touches_flag(env_path, flag_path, monkeypatch):
    SwitchSwarm = _load_switch_swarm(env_path, monkeypatch)
    result = SwitchSwarm(swarm="softdev").run()

    assert "switched" in result.lower()
    assert dotenv_values(str(env_path)).get("OPENSWARM_SWARM") == "softdev"
    assert flag_path.exists()
    assert os.environ.get("OPENSWARM_SWARM") == "softdev"


def test_switch_swarm_recognizes_metaswarm(env_path, flag_path, monkeypatch):
    SwitchSwarm = _load_switch_swarm(env_path, monkeypatch)
    result = SwitchSwarm(swarm="metaswarm").run()
    assert "switched" in result.lower()
    assert dotenv_values(str(env_path)).get("OPENSWARM_SWARM") == "metaswarm"


def test_switch_swarm_handles_uppercase_input(env_path, flag_path, monkeypatch):
    SwitchSwarm = _load_switch_swarm(env_path, monkeypatch)
    result = SwitchSwarm(swarm="SoftDev").run()
    assert "switched" in result.lower()
    assert dotenv_values(str(env_path)).get("OPENSWARM_SWARM") == "softdev"


# ── DispatchToSwarm tool — routing validation only ────────────────────────

def _load_dispatch():
    sys.modules.pop("swarms.metaswarm.orchestrator.tools.DispatchToSwarm", None)
    return importlib.import_module(
        "swarms.metaswarm.orchestrator.tools.DispatchToSwarm"
    ).DispatchToSwarm


def test_dispatch_refuses_recursive_metaswarm():
    DispatchToSwarm = _load_dispatch()
    result = DispatchToSwarm(swarm="metaswarm", task="hi").run()
    assert "recursively" in result.lower() or "leaf swarm" in result.lower()


def test_dispatch_unknown_swarm_returns_supported_list():
    DispatchToSwarm = _load_dispatch()
    result = DispatchToSwarm(swarm="unknown_swarm", task="hi").run()
    assert "unknown" in result.lower()
    # The error suggests valid alternatives
    assert "openswarm" in result or "softdev" in result


def test_dispatch_rejects_empty_task():
    DispatchToSwarm = _load_dispatch()
    with pytest.raises(ValidationError):
        DispatchToSwarm(swarm="softdev", task="")


def test_dispatch_propagates_factory_failure_as_error_string(monkeypatch):
    """If a sub-swarm's factory raises during construction, DispatchToSwarm
    must catch it and return an error rather than crashing the meta call."""
    DispatchToSwarm = _load_dispatch()

    # Stub the factory for a real registered swarm to raise
    def _boom(*args, **kwargs):
        raise RuntimeError("simulated factory failure")

    import swarms
    monkeypatch.setitem(swarms.SWARMS, "softdev", (_boom, "stubbed"))

    result = DispatchToSwarm(swarm="softdev", task="any task").run()
    assert "Failed to construct" in result
    assert "RuntimeError" in result
