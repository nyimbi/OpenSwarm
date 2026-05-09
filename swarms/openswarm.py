"""Adapter that exposes the original OpenSwarm agency as a registered swarm.

The original create_agency lives at the repo root (swarm.py:create_agency)
to avoid breaking imports across the existing 8 agent folders. This module
re-exports it under the swarms/ namespace so the registry has a uniform
shape.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agency_swarm import Agency


def create_agency(load_threads_callback=None) -> "Agency":
    # Imported here (not at module top) so failed imports from one swarm's
    # tool chain don't poison the entire registry.
    from swarm import create_agency as _root_create_agency
    return _root_create_agency(load_threads_callback=load_threads_callback)
