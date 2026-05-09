# FastAPI entry point — run with: python server.py
#
# Provider switching at runtime: the SwitchProvider tool on the orchestrator
# rewrites .env and reloads os.environ in this process. Agency-swarm rebuilds
# the agency on every chat/run request, so subsequent requests pick up the
# new DEFAULT_MODEL automatically — no server restart required. In-flight
# requests keep their existing agency until they finish.
#
# Multi-swarm: every swarm in the registry is exposed at its own URL path.
# Hit `/<slug>/...` to talk to a specific swarm — the FastAPI surface
# doesn't need a SwitchSwarm tool because URL routing already separates them.

import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

from agency_swarm.integrations.fastapi import run_fastapi

# Importing `swarm` triggers the runtime patches at the root of the repo
# (dual_comms, utf8_file_reads, file_attachment_refs, ipython_composio).
# Required before any swarm constructs an Agency — the dual-comms patch
# in particular is what makes the orchestrator-to-many + all-to-all
# topology work.
import swarm  # noqa: F401

from swarms import SWARMS


if __name__ == "__main__":
    # Register every registered swarm as its own FastAPI agency. URL paths
    # follow the slug ('/openswarm/...', '/softdev/...', '/metaswarm/...').
    agencies = {slug: factory for slug, (factory, _desc) in SWARMS.items()}

    run_fastapi(
        agencies=agencies,
        port=8080,
        enable_logging=True,
        allowed_local_file_dirs=[
            "./uploads",
        ],
    )
