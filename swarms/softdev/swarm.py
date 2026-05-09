"""SoftDev swarm — software development team in a box.

Topology:
- Orchestrator can SendMessage to every specialist (parallel delegation).
- All-to-all Handoff edges (any agent can hand off to any other).

Mirrors the OpenSwarm dual-comms pattern. See orchestrator/instructions.md
in this swarm's folder for the routing contract.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agency_swarm import Agency


def create_agency(load_threads_callback=None) -> "Agency":
    from agency_swarm import Agency
    from agency_swarm.tools import Handoff, SendMessage

    from swarms.softdev.orchestrator import create_orchestrator
    from swarms.softdev.architect import create_architect
    from swarms.softdev.coder import create_coder
    from swarms.softdev.reviewer import create_reviewer
    from swarms.softdev.tester import create_tester
    from swarms.softdev.doc_writer import create_doc_writer
    from swarms.softdev.researcher import create_researcher
    from swarms.softdev.devops import create_devops

    orchestrator = create_orchestrator()
    agents = [
        orchestrator,
        create_architect(),
        create_coder(),
        create_reviewer(),
        create_tester(),
        create_doc_writer(),
        create_researcher(),
        create_devops(),
    ]

    send_message_flows = [
        (orchestrator, specialist, SendMessage)
        for specialist in agents
        if specialist is not orchestrator
    ]
    handoff_flows = [
        (a > b, Handoff)
        for a in agents
        for b in agents
        if a is not b
    ]

    return Agency(
        *agents,
        communication_flows=send_message_flows + handoff_flows,
        name="SoftDev",
        shared_instructions="swarms/softdev/shared_instructions.md",
        load_threads_callback=load_threads_callback,
    )
