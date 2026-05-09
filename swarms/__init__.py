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
        "Software development swarm: architect, coder, reviewer, tester, doc writer, researcher, devops.",
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
