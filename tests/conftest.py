"""Test scaffolding.

These tests target configuration and tool-routing logic that lives in
config.py, orchestrator/tools/SwitchProvider.py, and onboard.py. The
production code imports `agency_swarm` (and the wider OpenAI Agents SDK
ecosystem), but the logic under test does not actually need any of that —
SwitchProvider only needs `BaseTool` as a Pydantic-shaped base class, and
config._resolve only needs `LitellmModel` as a constructable callable.

Stubbing those two surfaces here keeps the test suite runnable from a bare
Python install (`pip install pytest python-dotenv pydantic`) without
requiring the multi-hundred-megabyte agency-swarm + openai-agents-sdk +
LiteLLM dependency chain.
"""

import sys
import types

from pydantic import BaseModel


def _install_agency_swarm_stubs() -> None:
    """Register fake `agency_swarm` and supporting modules in sys.modules.

    Production code does:
        from agency_swarm.tools import BaseTool
        from agency_swarm import LitellmModel, Agent, ModelSettings
        from openai.types.shared import Reasoning

    The orchestrator package imports Agent/ModelSettings/Reasoning at module
    load time (via `from .orchestrator import create_orchestrator` in
    orchestrator/__init__.py). Importing `orchestrator.tools.SwitchProvider`
    therefore triggers that chain. Stub all of them — none are exercised by
    the test logic; they only need to be importable.
    """
    pkg = sys.modules.get("agency_swarm")
    if pkg is not None and getattr(pkg, "_openswarm_test_stub", False):
        return  # already installed

    # If the real agency_swarm package is installed and importable, defer to
    # it. Stubs would otherwise shadow `agency_swarm.tools` so subsequent
    # `from agency_swarm.tools.<submodule> import ...` calls inside the real
    # package break with "not a package" errors.
    try:
        import agency_swarm  # noqa: F401
        return
    except Exception:
        pass

    pkg = types.ModuleType("agency_swarm")
    pkg._openswarm_test_stub = True  # type: ignore[attr-defined]

    class _Agent:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _ModelSettings:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    class _LitellmModel:
        """Records constructor kwargs as attributes for test assertions."""

        def __init__(self, model, api_key=None, base_url=None, **kwargs):
            self.model = model
            self.api_key = api_key
            self.base_url = base_url
            self.kwargs = kwargs

    pkg.Agent = _Agent  # type: ignore[attr-defined]
    pkg.ModelSettings = _ModelSettings  # type: ignore[attr-defined]
    pkg.LitellmModel = _LitellmModel  # type: ignore[attr-defined]

    class _Agency:
        """Minimal stub for tests that need to assert sub-agency dispatch."""

        def __init__(self, *agents, **kwargs):
            self.agents = agents
            self.kwargs = kwargs

        def get_response_sync(self, message, **kwargs):
            class _Result:
                final_output = f"[stub-agency] {message}"
            return _Result()

    pkg.Agency = _Agency  # type: ignore[attr-defined]

    tools = types.ModuleType("agency_swarm.tools")

    class _BaseTool(BaseModel):
        def run(self):
            raise NotImplementedError

    tools.BaseTool = _BaseTool  # type: ignore[attr-defined]

    # Tool classes used by various agents — stubbed as no-op classes since
    # tests don't actually invoke them.
    class _PassthroughTool:
        pass

    tools.PersistentShellTool = _PassthroughTool  # type: ignore[attr-defined]
    tools.WebSearchTool = _PassthroughTool  # type: ignore[attr-defined]
    tools.Handoff = _PassthroughTool  # type: ignore[attr-defined]
    tools.SendMessage = _PassthroughTool  # type: ignore[attr-defined]

    sys.modules["agency_swarm"] = pkg
    sys.modules["agency_swarm.tools"] = tools

    # openai.types.shared.Reasoning — orchestrator imports this directly.
    # Real openai package may already be installed, so only stub the path
    # if it doesn't resolve.
    try:
        from openai.types.shared import Reasoning  # noqa: F401
    except (ImportError, ModuleNotFoundError):
        openai_pkg = sys.modules.get("openai") or types.ModuleType("openai")
        openai_types = sys.modules.get("openai.types") or types.ModuleType("openai.types")
        openai_shared = types.ModuleType("openai.types.shared")

        class _Reasoning:
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)

        openai_shared.Reasoning = _Reasoning  # type: ignore[attr-defined]
        sys.modules["openai"] = openai_pkg
        sys.modules["openai.types"] = openai_types
        sys.modules["openai.types.shared"] = openai_shared


_install_agency_swarm_stubs()


# ── orchestrator.tools class-vs-submodule shadowing ─────────────────────────
#
# orchestrator/tools/__init__.py exports `SwitchProvider` and `SwitchSwarm`
# *classes* under the same dotted path as the submodules that define them:
#
#     orchestrator.tools.SwitchProvider  -> SwitchProvider class
#     orchestrator/tools/SwitchProvider.py defines class SwitchProvider
#
# Several tests pop the submodule from sys.modules and re-import it so they
# can monkeypatch module-level ENV_PATH for a tmpdir. Python's import
# machinery rebinds the package attribute to the submodule on that re-load,
# overwriting the class. The next agency factory in the suite that does
# `from orchestrator.tools import SwitchProvider` then receives the
# submodule, and agency-swarm rejects it with "Tool 'module' is not a
# supported tool".
#
# Fix: snapshot the class bindings and restore them before every test.
import pytest as _pytest


def _pin_orchestrator_tools_classes() -> None:
    """Pin orchestrator.tools.{SwitchProvider,SwitchSwarm} to the
    classes from __init__.py. Used both as setup and teardown for the
    autouse fixture below.

    Best-effort — if the orchestrator package isn't importable in this
    environment (e.g. the smoketest venv lacks dependencies), the
    affected tests skip themselves, but the fixture must not fail."""
    try:
        import orchestrator.tools as _ot
        from orchestrator.tools.SwitchProvider import SwitchProvider as _SP
        from orchestrator.tools.SwitchSwarm import SwitchSwarm as _SS
        _ot.SwitchProvider = _SP
        _ot.SwitchSwarm = _SS
    except Exception:
        pass


@_pytest.fixture(autouse=True)
def _restore_orchestrator_tools_class_bindings():
    """Restore orchestrator.tools.{SwitchProvider,SwitchSwarm} to the
    classes from __init__.py before AND after every test.

    The pre-yield pin handles the "previous test polluted this binding"
    case. The post-yield pin handles the "this test polluted the
    binding, and pytest's own machinery now wants to inspect it"
    case — keeps the binding stable for test report generation."""
    _pin_orchestrator_tools_classes()
    yield
    _pin_orchestrator_tools_classes()
