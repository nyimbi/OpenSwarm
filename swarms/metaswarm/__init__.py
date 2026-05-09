"""MetaSwarm — front door that routes work to the right specialist swarm.

Single-agent agency: just the MetaOrchestrator, equipped with two
delegation paths — `DispatchToSwarm` (run a sub-swarm to completion and
bring the result back) and `SwitchSwarm` (migrate the user's whole
session to a different swarm).
"""
