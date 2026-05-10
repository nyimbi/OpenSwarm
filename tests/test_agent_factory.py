"""Eager-validation tests for make_agent (H7).

If `make_agent` is called with a name whose derived `<slug>.md` doesn't
exist under the agent's instructions directory, the helper must raise
FileNotFoundError at construction time — not silently accept an
empty-instructions agent that fails at first chat call.
"""

from __future__ import annotations

import pytest

from swarms._common.agent_factory import make_agent


def test_make_agent_rejects_missing_instructions(tmp_path):
    """The guarded path. tmp_path has no <slug>.md, so make_agent should
    raise FileNotFoundError mentioning both the agent name and expected slug."""
    with pytest.raises(FileNotFoundError) as exc:
        make_agent(
            name="NonexistentAgent",
            description="should not construct",
            instructions_dir=tmp_path,
        )
    msg = str(exc.value)
    assert "NonexistentAgent" in msg
    assert "nonexistentagent.md" in msg


def test_make_agent_accepts_present_instructions(tmp_path):
    """The happy path. With the file present, construction succeeds."""
    (tmp_path / "happyagent.md").write_text("# Happy", encoding="utf-8")
    agent = make_agent(
        name="HappyAgent",
        description="should construct",
        instructions_dir=tmp_path,
    )
    assert agent is not None
    # Name preserved through the helper
    assert getattr(agent, "name", None) == "HappyAgent"


def test_make_agent_slug_strips_non_alphanumeric(tmp_path):
    """Slug derivation: 'CopyWriter' -> 'copywriter'; 'SEO-Specialist' -> 'seospecialist'."""
    (tmp_path / "seospecialist.md").write_text("# stub", encoding="utf-8")
    agent = make_agent(
        name="SEO-Specialist",
        description="hyphenated name",
        instructions_dir=tmp_path,
    )
    assert agent is not None
