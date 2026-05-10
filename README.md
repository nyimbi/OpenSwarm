# OpenSwarm — personal multi-swarm fork

A fork of [VRSEN/OpenSwarm](https://github.com/VRSEN/openswarm) built around three changes that mattered for a small business owning its own infrastructure:

- **15 specialized swarms** (78 agents total) — from software engineering to meeting prep to finance — instead of one general-purpose team.
- **7 LLM providers** with runtime switching (Azure OpenAI, Azure AI Foundry/Claude, Anthropic, Google, OpenAI, Ollama local, OpenAI-compatible).
- **Self-hosted search and scraping** wired in (SearXNG + Firecrawl) — works on every provider, not just OpenAI's hosted Responses API.

```bash
oswarm                    # default swarm (metaswarm router)
oswarm meeting_prep       # specific swarm
oswarm proposals
oswarm list               # see all 15
oswarm server             # FastAPI on :8080 — every swarm at its own URL
```

---

## Quick start

```bash
git clone https://github.com/nyimbi/OpenSwarm.git
cd OpenSwarm

# One-time install: bootstrap deps + symlink launcher
python swarm.py            # first run pulls deps via uv
ln -sf "$(pwd)/bin/oswarm" ~/.local/bin/oswarm

# Configure provider + (optional) connectors infra
cp .env.example .env       # fill in keys
# OR rely on ~/.config/secrets/api_keys.env — oswarm sources it automatically
```

Then `oswarm` is available system-wide.

---

## The fleet

15 swarms, picked at startup via env var or by talking to the MetaSwarm router. Sensitive-data swarms (`people_ops`, `finance`) have hard data-policy rules in their instructions — outputs land in local files only, no private data ever reaches external services.

| Slug | Agents | What it does |
|---|---|---|
| `metaswarm` | 1 | Front-door router. Pick this when starting fresh. Dispatches to specialists or migrates the session. |
| `openswarm` | 8 | Original general-purpose team: research, slides, docs, images, video, data analysis, virtual assistant. |
| `softdev` | 8 | Software engineering: architect, coder, reviewer, tester, docs, researcher, devops. |
| `technical_docs` | 4 | API references, architecture guides, ADRs, READMEs, runbooks. |
| `courses` | 5 | Lessons, exercises, quizzes — full educational content. |
| `corpus_analysis` | 5 | Text + statistical analysis over document collections. IPython for the math. |
| `historical_analysis` | 4 | Evidence-based historical research with citations. |
| `geopolitical_analysis` | 5 | International-affairs briefs: situation, actors, drivers, scenarios. |
| `sci_fi_stories` | 4 | Long-form science-fiction narrative writing. |
| `tiktok_stories` | 5 | Short-form vertical-video story scripts with hooks, storyboards, captions. |
| `meeting_prep` | 4 | Pre-meeting research, one-page brief, question list. |
| `proposals` | 6 | RFP responses, SOWs, pitches with pricing and compliance audit. |
| `marketing` | 5 | Web copy, ads, email, SEO. Carries brand voice across pieces. |
| `people_ops` | 5 | Small-team HR: handbooks, scheduling, training, performance. **Sensitive data — local files only.** |
| `finance` | 5 | Budgets, P&L, variance, projections. Math via IPython, not LLM. **Sensitive data — local files only.** |

Run `oswarm list` to see the live registry.

---

## Providers

Every swarm runs on any provider. Switch at runtime by talking to the orchestrator:

> "switch to ollama llama3.1"
> "switch to azure_ai claude-opus-4-1"
> "use Claude"

| Provider | `DEFAULT_MODEL` | Required env |
|---|---|---|
| OpenAI | `gpt-5.2` (or any OpenAI model id) | `OPENAI_API_KEY` |
| Anthropic | `litellm/claude-sonnet-4-6` | `ANTHROPIC_API_KEY` |
| Google Gemini | `litellm/gemini/gemini-3-flash` | `GOOGLE_API_KEY` |
| Azure OpenAI Service | `azure/<deployment>` | `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION` |
| Azure AI Foundry (Claude on Azure, Llama, Mistral) | `azure_ai/<model>` | `AZURE_AI_API_KEY`, `AZURE_AI_API_BASE` (note: Anthropic models need `/anthropic` URL suffix) |
| Ollama (local) | `ollama_chat/<model>` | `OLLAMA_API_BASE` (defaults to `http://localhost:11434`) |
| OpenAI-compatible (Ollama Cloud, Groq, Together, Mistral, OpenRouter, vLLM) | `openai_compat/<model>` | `OPENAI_COMPAT_API_KEY`, `OPENAI_COMPAT_API_BASE` |

The orchestrator's `SwitchProvider` tool writes to `.env` and reloads in-process — works on both the TUI and the FastAPI surface (per-request agency rebuild picks up the change automatically).

---

## How to use it

### Interactive (TUI)

```bash
oswarm meeting_prep
> I have a 45-min call tomorrow with the procurement officer at WFP Nairobi.
  Prep me — research, brief, questions.
```

The orchestrator routes work to the right specialists. Output files land in `mnt/<swarm>/...` per the agent instructions.

Switch swarms mid-session by saying so:

> "switch to softdev"

The orchestrator calls `SwitchSwarm`, you `/quit`, and the TUI restarts on the new swarm.

### API (FastAPI)

```bash
oswarm server   # all 15 swarms at http://localhost:8080/<slug>/
```

Each swarm has its own URL path. Provider switching from the API surface is a tool call inside a request — agency-swarm rebuilds the agency on every request, so the next call picks up the new provider with no server restart.

### Programmatic

```python
from swarms import get_factory
agency = get_factory("proposals")()
result = agency.get_response_sync("Write me an RFP response for ...")
print(result.final_output)
```

---

## Personal infrastructure

The fork integrates with self-hosted services on a connectors server (your own infra — see `~/src/pjs/infra/docs/search_crawl/infra-search.md` for the topology):

- **SearXNG** at `:8888` — privacy-respecting metasearch over Google/Bing/DuckDuckGo/Brave/Wikipedia. Wraps as the `WebSearch` tool.
- **Firecrawl** at `:3002` — JS-rendered scraping with stealth anti-detection. Wraps as the `WebFetch` tool.

Configure with:

```bash
SEARXNG_URL=http://your-host:8888
FIRECRAWL_URL=http://your-host:3002
```

Both default to `localhost` ports if you self-host on the same machine. The `oswarm` launcher pre-fills the connectors-server URLs from the user's `~/.config/secrets/api_keys.env`.

---

## Sensitive data discipline

The `people_ops` and `finance` swarms handle private business data — employee records, performance, compensation, P&L figures. Their `shared_instructions.md` enforces three rules:

1. **Never include private data in queries to external services** (WebSearch, WebFetch, etc.).
2. **Outputs containing private data go to local files only** under `mnt/<swarm>/private/`.
3. **When uncertain whether something is sensitive, treat it as sensitive.**

The `finance` swarm goes further — its agents don't have web tools at all, closing off the data-leak vector at construction time rather than relying on instructions alone.

---

## Architecture

- **`swarms/__init__.py`** is the single source of truth. Each entry maps a slug → factory + description.
- **Each swarm is a folder** under `swarms/<slug>/` with a `swarm.py` factory, `shared_instructions.md` for cross-agent rules, and `instructions/<agent>.md` for per-agent system prompts.
- **The MetaSwarm orchestrator** (in `swarms/metaswarm/`) has two delegation tools:
  - `DispatchToSwarm(swarm, task)` — runs a sub-swarm to completion and returns the result (subroutine-style).
  - `SwitchSwarm(swarm)` — migrates the user's whole session to a different swarm.
- **The orchestrator's "router only" contract** is preserved across all swarms, with two documented carve-outs: `SwitchProvider` (provider switching) and `SwitchSwarm` (swarm switching). All other work is delegated to specialists.
- **Patches at `patches/`** monkey-patch agency-swarm to support the dual `SendMessage` + `Handoff` topology, UTF-8 instruction reads, FastAPI file-attachment paths, and IPython kernel context bootstrapping. Loaded automatically by `swarm.py` and the launcher.

Adding a new swarm is one entry in the registry plus a folder. See `swarms/meeting_prep/` for the smallest reference example (4 agents, ~9 files).

---

## Repo structure

```
openswarm/
├── bin/
│   ├── oswarm                      ← personal launcher (this fork)
│   └── openswarm                   ← original npm CLI (upstream binary)
├── swarms/
│   ├── __init__.py                  ← registry
│   ├── _common/                     ← shared tools across swarms
│   │   ├── agent_factory.py
│   │   ├── file_ops.py
│   │   └── web_tools/               ← WebSearch + WebFetch
│   ├── metaswarm/
│   ├── openswarm.py                 ← wraps the original create_agency
│   ├── softdev/
│   └── ... (12 more)
├── orchestrator/                    ← original OpenSwarm orchestrator (root-level)
├── shared_instructions.md
├── tests/                            ← 61 unit + 12 web + 4 live tests
├── patches/                          ← agency-swarm runtime patches
├── swarm.py                         ← TUI entry point
└── server.py                        ← FastAPI entry point
```

Original 8-agent OpenSwarm lives at the repo root unchanged. New swarms live under `swarms/`. The registry in `swarms/__init__.py` knows about both.

---

## Tests

```bash
pytest                  # 61 unit + auto-skip live tests when keys absent
pytest -m live          # only live tests (need real provider keys)
pytest -m "not live"    # only unit tests (CI-friendly)
```

Live tests live in `tests/test_live_providers.py` (Ollama + Azure round-trips) and `tests/test_web_tools.py` (real SearXNG + Firecrawl). They opt-in via env vars and skip cleanly when the relevant infra isn't reachable.

---

## Credit

Built on [VRSEN/OpenSwarm](https://github.com/VRSEN/openswarm), itself built on [Agency Swarm](https://github.com/VRSEN/agency-swarm) and the [OpenAI Agents SDK](https://github.com/openai/openai-agents-python). The original OpenSwarm provided the eight specialist agents, the agency-swarm framework integrations, and the runtime patches that make the dual-comms topology work.

---

## License

MIT — same as upstream. See [LICENSE](LICENSE).
