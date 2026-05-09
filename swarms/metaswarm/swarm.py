"""MetaSwarm — single-agent agency built around the MetaOrchestrator."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agency_swarm import Agency


def create_agency(load_threads_callback=None) -> "Agency":
    from agency_swarm import Agency

    from swarms.metaswarm.orchestrator import create_meta_orchestrator

    meta = create_meta_orchestrator()
    return Agency(
        meta,
        # Single-agent: no communication flows needed; the meta-orchestrator
        # uses DispatchToSwarm / SwitchSwarm tools to reach other swarms.
        communication_flows=[],
        name="MetaSwarm",
        shared_instructions="shared_instructions.md",  # repo-root shared rules
        load_threads_callback=load_threads_callback,
    )
