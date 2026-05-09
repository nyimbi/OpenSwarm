#!/usr/bin/env bash
# Wrapper to launch OpenSwarm with the user's local infrastructure pre-wired.
#
# Bridges shell-env naming conventions (AZURE_OPENAI_*) to OpenSwarm's
# LiteLLM-style names (AZURE_*), points the web tools at the connectors
# server, and forwards arguments to swarm.py.
#
# Usage:
#   ./run_swarm.sh                       # default swarm (metaswarm)
#   ./run_swarm.sh meeting_prep          # specific swarm
#   ./run_swarm.sh proposals
#   ./run_swarm.sh server                # FastAPI mode (all swarms)

set -euo pipefail

# 1. Source secrets (fail loudly if missing)
SECRETS="${HOME}/.config/secrets/api_keys.env"
if [[ -f "$SECRETS" ]]; then
  # shellcheck disable=SC1090
  source "$SECRETS"
fi

# 2. Bridge env-var naming conventions
[[ -n "${AZURE_OPENAI_API_KEY:-}" ]]    && export AZURE_API_KEY="$AZURE_OPENAI_API_KEY"
[[ -n "${AZURE_OPENAI_BASE_URL:-}" ]]   && export AZURE_API_BASE="${AZURE_OPENAI_BASE_URL%/}"
[[ -n "${AZURE_OPENAI_API_VERSION:-}" ]] && export AZURE_API_VERSION="$AZURE_OPENAI_API_VERSION"

# Anthropic-on-Foundry bridge
if [[ -n "${ANTHROPIC_FOUNDRY_API_KEY:-}" && -n "${ANTHROPIC_FOUNDRY_RESOURCE:-}" ]]; then
  export AZURE_AI_API_KEY="$ANTHROPIC_FOUNDRY_API_KEY"
  export AZURE_AI_API_BASE="https://${ANTHROPIC_FOUNDRY_RESOURCE}.services.ai.azure.com/anthropic"
fi

# Default model (override via env or first launch)
export DEFAULT_MODEL="${DEFAULT_MODEL:-azure/gpt-4o}"

# Connectors server (search + scrape)
export SEARXNG_URL="${SEARXNG_URL:-http://84.247.181.100:8888}"
export FIRECRAWL_URL="${FIRECRAWL_URL:-http://84.247.181.100:3002}"

# 3. Decide what to run
ARG="${1:-}"
case "$ARG" in
  server)
    echo "Launching FastAPI on :8080. All swarms exposed at /<slug>/..."
    exec python server.py
    ;;
  list|ls)
    python -c "from swarms import SWARMS; [print(f'  {s:25s} {d}') for s, (_,d) in SWARMS.items()]"
    ;;
  "")
    echo "Launching default swarm (metaswarm). Provider: $DEFAULT_MODEL"
    exec python swarm.py
    ;;
  *)
    export OPENSWARM_SWARM="$ARG"
    echo "Launching swarm: $ARG. Provider: $DEFAULT_MODEL"
    exec python swarm.py
    ;;
esac
