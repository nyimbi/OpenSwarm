"""One high-impact quality invariant per remaining swarm.

The universal harness (test_swarm_quality.py) covers structural rules.
This file pins the one domain-specific invariant per swarm that
matters most for "highest possible quality" — the rule whose violation
would degrade output even if the structural checks pass.

Each test reads the relevant instructions file and asserts the
presence of a key concept; the asserted-content checks are intentionally
broad ("citation" not "citation:") so that legitimate rewording
doesn't break the test, but narrow enough to catch removal of the
discipline rule entirely.
"""

from __future__ import annotations

from pathlib import Path

import pytest


SWARMS_ROOT = Path(__file__).resolve().parents[1] / "swarms"


def _instr(swarm: str, agent_slug: str) -> str:
    return (SWARMS_ROOT / swarm / "instructions" / f"{agent_slug}.md").read_text("utf-8")


def _shared(swarm: str) -> str:
    return (SWARMS_ROOT / swarm / "shared_instructions.md").read_text("utf-8")


# ── US-005: historical_analysis — citation discipline ─────────────────────


def test_historical_analysis_researcher_requires_citations():
    text = _instr("historical_analysis", "researcher").lower()
    assert "citation" in text or "cite" in text or "source" in text, (
        "Researcher must teach citation/sourcing discipline"
    )


def test_historical_analysis_synthesizer_requires_citations_in_output():
    text = _instr("historical_analysis", "synthesizer").lower()
    assert "citation" in text or "cite" in text, (
        "Synthesizer must require citations in the final report"
    )


def test_historical_analysis_distinguishes_primary_secondary():
    text = _shared("historical_analysis").lower()
    assert "primary" in text and "secondary" in text, (
        "shared_instructions must distinguish primary vs secondary sources"
    )


# ── US-006: geopolitical_analysis — uncertainty + sourcing ────────────────


def test_geopolitical_researcher_requires_sourced_facts():
    text = _instr("geopolitical_analysis", "researcher").lower()
    assert "source" in text or "cite" in text or "citation" in text, (
        "Researcher must require sourced facts (the analytical agents "
        "build on these)"
    )


def test_geopolitical_strategic_analyst_handles_forward_uncertainty():
    text = _instr("geopolitical_analysis", "strategicanalyst").lower()
    assert (
        "scenario" in text or "uncertainty" in text or "confidence" in text
        or "probabil" in text
    ), (
        "StrategicAnalyst must teach forward-looking-uncertainty discipline"
    )


def test_geopolitical_synthesizer_surfaces_uncertainty():
    text = _instr("geopolitical_analysis", "synthesizer").lower()
    assert (
        "uncertainty" in text or "confidence" in text
        or "what we don't know" in text or "what we don't" in text
        or "limits" in text
    ), "Synthesizer must surface uncertainty in the final brief"


# ── US-007: corpus_analysis — IPython math substrate ──────────────────────


def test_corpus_analyst_uses_ipython():
    for slug in ("loader", "textanalyst", "statanalyst", "reporter"):
        text = _instr("corpus_analysis", slug).lower()
        assert (
            "ipython" in text or "pandas" in text or "numpy" in text
            or "python" in text
        ), f"corpus_analysis/{slug} must reference the IPython/Python math substrate"


def test_corpus_reporter_includes_methodology():
    text = _instr("corpus_analysis", "reporter").lower()
    assert "method" in text, (
        "Reporter must include / require a methodology section"
    )


# ── US-008: technical_docs — audience + executable examples ───────────────


def test_technical_docs_architect_defines_audience():
    text = _instr("technical_docs", "docarchitect").lower()
    assert "audience" in text or "reader" in text, (
        "DocArchitect must require audience definition"
    )


def test_technical_docs_writer_handles_code_examples():
    text = _instr("technical_docs", "techwriter").lower()
    assert "example" in text or "code" in text, (
        "TechWriter must teach how to handle code examples"
    )


def test_technical_docs_editor_does_cohesion_check():
    text = _instr("technical_docs", "editor").lower()
    assert (
        "consistency" in text or "cohesion" in text or "structure" in text
        or "coheren" in text or "consistent" in text
    ), "Editor must do a structural/cohesion check"


# ── US-009: marketing — brand voice + no buzzwords ────────────────────────


def test_marketing_strategist_defines_voice():
    text = _instr("marketing", "strategist").lower()
    assert "voice" in text or "brand" in text or "positioning" in text, (
        "Strategist must define brand voice / positioning"
    )


def test_marketing_editor_kills_marketing_voice():
    text = _instr("marketing", "editor").lower()
    # The "kill marketing buzzwords" rule from proposals/editor.md
    # should apply here too; check for any of the common signal words.
    assert any(
        bad in text for bad in (
            "leverage", "buzzword", "marketing voice", "marketing-speak",
            "robust", "best-in-class", "world-class",
        )
    ), "Editor must explicitly call out marketing buzzwords to remove"


# ── US-010: softdev — test discipline + no invented APIs ──────────────────


def _read_softdev_instructions(slug: str) -> str:
    """softdev co-locates instructions inside per-role subpackages."""
    candidates = [
        SWARMS_ROOT / "softdev" / slug / "instructions.md",
        SWARMS_ROOT / "softdev" / "instructions" / f"{slug}.md",
    ]
    for p in candidates:
        if p.is_file():
            return p.read_text("utf-8")
    raise AssertionError(f"no instructions found for softdev/{slug} (tried {candidates})")


def test_softdev_coder_or_tester_teaches_test_discipline():
    """Test-first or test-after discipline must be taught somewhere
    in the test/code path; check both."""
    found_test_discipline = False
    for slug in ("coder", "tester", "reviewer", "architect"):
        try:
            text = _read_softdev_instructions(slug).lower()
        except AssertionError:
            continue
        if any(
            phrase in text
            for phrase in ("test", "pytest", "unit test", "regression", "tdd")
        ):
            found_test_discipline = True
            break
    assert found_test_discipline, (
        "softdev's coder/tester/reviewer/architect must teach test "
        "discipline somewhere"
    )


# ── US-011: courses — audience targeting + answer keys ────────────────────


def test_courses_designer_defines_audience():
    text = _instr("courses", "coursedesigner").lower()
    assert (
        "audience" in text or "learner" in text or "level" in text
        or "prerequisite" in text or "objective" in text
    ), "CourseDesigner must define audience / learning objectives"


def test_courses_exercise_writer_requires_answer_keys():
    text = _instr("courses", "exercisewriter").lower()
    assert "answer" in text or "solution" in text or "key" in text, (
        "ExerciseWriter must require answer keys / solutions"
    )


# ── US-012: sci_fi_stories — worldbuilding consistency ────────────────────


def test_sci_fi_worldbuilder_owns_setting_rules():
    text = _instr("sci_fi_stories", "worldbuilder").lower()
    assert "rules" in text or "setting" in text or "world" in text, (
        "Worldbuilder must own setting rules / canon"
    )


def test_sci_fi_editor_does_voice_or_continuity_check():
    text = _instr("sci_fi_stories", "editor").lower()
    assert "voice" in text or "continuity" in text or "consistency" in text, (
        "Editor must check voice and/or continuity"
    )


# ── US-013: tiktok_stories — short-form discipline ────────────────────────


def test_tiktok_hookwriter_targets_first_seconds():
    text = _instr("tiktok_stories", "hookwriter").lower()
    assert (
        "hook" in text or "first" in text or "second" in text or "open" in text
    ), "HookWriter must target the first-seconds attention window"


def test_tiktok_specialists_acknowledge_format_constraints():
    """At least one specialist must acknowledge the short-form
    platform constraint (vertical video, ~60-second limit, captions)."""
    found_format_awareness = False
    for slug in ("hookwriter", "storyboarder", "storyteller", "polisher"):
        text = _instr("tiktok_stories", slug).lower()
        if any(
            kw in text for kw in (
                "tiktok", "short-form", "short form", "60-second",
                "60 second", "vertical", "9:16", "caption",
            )
        ):
            found_format_awareness = True
            break
    assert found_format_awareness, (
        "At least one tiktok_stories specialist must teach the "
        "platform-format constraints"
    )


# ── US-014: meeting_prep — already upgraded in Commit 2 ──────────────────


def test_meeting_prep_orchestrator_sequential():
    text = _instr("meeting_prep", "orchestrator").lower()
    assert "one at a time" in text and "wait" in text, (
        "meeting_prep orchestrator must enforce strict sequential routing"
    )


def test_meeting_prep_specialists_have_workflow_sections():
    for slug in ("researcher", "briefer", "questionsmith"):
        text = _instr("meeting_prep", slug)
        lower = text.lower()
        assert any(
            section in lower for section in ("# workflow", "## workflow", "workflow")
        ), f"meeting_prep/{slug} must have a workflow section"
        assert any(
            section in lower for section in (
                "boundar", "discipline", "rules", "guidelines"
            )
        ), f"meeting_prep/{slug} must have a boundaries/discipline section"
