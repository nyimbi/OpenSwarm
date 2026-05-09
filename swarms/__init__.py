"""Swarm registry — the single source of truth for which swarms exist.

Each entry maps a slug (used in OPENSWARM_SWARM env var, the TUI picker,
and FastAPI URL paths) to a no-arg factory that returns an Agency.
Adding a new swarm means importing its factory here and registering it.

Factories receive `load_threads_callback` as a kwarg when called from
agency-swarm's FastAPI integration; they should accept it transparently.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agency_swarm import Agency

# Lazy imports inside the factory wrappers — keeps `from swarms import SWARMS`
# fast and avoids loading the entire OpenSwarm + SoftDev tool chains at
# module import time when only one swarm will actually run.

def _openswarm_factory(load_threads_callback=None) -> "Agency":
    from swarms.openswarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _softdev_factory(load_threads_callback=None) -> "Agency":
    from swarms.softdev.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _metaswarm_factory(load_threads_callback=None) -> "Agency":
    from swarms.metaswarm.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _technical_docs_factory(load_threads_callback=None) -> "Agency":
    from swarms.technical_docs.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _courses_factory(load_threads_callback=None) -> "Agency":
    from swarms.courses.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _corpus_analysis_factory(load_threads_callback=None) -> "Agency":
    from swarms.corpus_analysis.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _historical_analysis_factory(load_threads_callback=None) -> "Agency":
    from swarms.historical_analysis.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _geopolitical_analysis_factory(load_threads_callback=None) -> "Agency":
    from swarms.geopolitical_analysis.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _sci_fi_stories_factory(load_threads_callback=None) -> "Agency":
    from swarms.sci_fi_stories.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _tiktok_stories_factory(load_threads_callback=None) -> "Agency":
    from swarms.tiktok_stories.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _meeting_prep_factory(load_threads_callback=None) -> "Agency":
    from swarms.meeting_prep.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _proposals_factory(load_threads_callback=None) -> "Agency":
    from swarms.proposals.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _marketing_factory(load_threads_callback=None) -> "Agency":
    from swarms.marketing.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _people_ops_factory(load_threads_callback=None) -> "Agency":
    from swarms.people_ops.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


def _finance_factory(load_threads_callback=None) -> "Agency":
    from swarms.finance.swarm import create_agency
    return create_agency(load_threads_callback=load_threads_callback)


# Slug -> (factory, one-line description).
# Slugs must match `[a-z0-9_-]+` since they appear in URL paths.
SWARMS: dict[str, tuple[Callable, str]] = {
    "metaswarm": (
        _metaswarm_factory,
        "Front-door router. Decides which swarm fits a request and dispatches or migrates.",
    ),
    "openswarm": (
        _openswarm_factory,
        "General-purpose multi-modal swarm: research, slides, docs, images, video, data analysis, virtual assistant.",
    ),
    "softdev": (
        _softdev_factory,
        "Software development: architect, coder, reviewer, tester, doc writer, researcher, devops.",
    ),
    "technical_docs": (
        _technical_docs_factory,
        "Technical documentation: API references, architecture guides, ADRs, READMEs, runbooks.",
    ),
    "courses": (
        _courses_factory,
        "Educational course material: lessons, exercises, quizzes, assessments.",
    ),
    "corpus_analysis": (
        _corpus_analysis_factory,
        "Text and statistical analysis over document collections.",
    ),
    "historical_analysis": (
        _historical_analysis_factory,
        "Evidence-based historical research and synthesis with citations.",
    ),
    "geopolitical_analysis": (
        _geopolitical_analysis_factory,
        "International-affairs briefs: situation, actors, drivers, scenarios.",
    ),
    "sci_fi_stories": (
        _sci_fi_stories_factory,
        "Science-fiction narrative writing: worldbuilding, plot, prose, editing.",
    ),
    "tiktok_stories": (
        _tiktok_stories_factory,
        "Short-form vertical-video story scripts with hooks, storyboards, captions.",
    ),
    "meeting_prep": (
        _meeting_prep_factory,
        "Pre-meeting research, one-page brief, and question list.",
    ),
    "proposals": (
        _proposals_factory,
        "Business proposals: RFP responses, SOWs, pitches with pricing and compliance audit.",
    ),
    "marketing": (
        _marketing_factory,
        "Marketing content: positioning, voice, web copy, ads, email, SEO.",
    ),
    "people_ops": (
        _people_ops_factory,
        "Small-team HR: handbooks, scheduling, training plans, performance reviews. Sensitive data — local files only.",
    ),
    "finance": (
        _finance_factory,
        "Budgets, P&L, variance, projections. Math via IPython, not LLM. Sensitive data — local files only.",
    ),
}


def get_factory(slug: str) -> Callable:
    """Look up a factory by slug, with a clear error if not registered."""
    if slug not in SWARMS:
        raise KeyError(
            f"Unknown swarm '{slug}'. Available: {', '.join(SWARMS)}."
        )
    return SWARMS[slug][0]


def default_slug() -> str:
    """The slug used when OPENSWARM_SWARM isn't set and no picker runs.

    Defaults to 'metaswarm' — the front-door router, which can route to any
    other swarm. Lets fresh sessions start with "what should I do?" instead
    of forcing the user to commit to a swarm before they know what they want.
    """
    return "metaswarm"
