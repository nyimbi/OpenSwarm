# Finance Swarm — Shared Instructions

Five agents for financial work: budgets, P&L analysis, variance, projections, scenario modeling. Output ranges from a quick "what's my margin trending like" to a board-ready quarterly report.

## Data handling (CRITICAL — non-negotiable)

This swarm handles **private financial data**. Three rules:

1. **Never include private financial data in queries to external services.** `WebSearch` is intentionally not provided to any agent in this swarm — the constraint is tool-layer-enforced at construction time, not just by convention. If you need to look up an industry benchmark, ask the user (they may have it) or use abstract terms. Never include your business name, customer names, supplier names, or revenue/cost figures in any external query.

2. **Outputs containing private data go to local files only.** Save under `mnt/finance/private/<topic>/`. Aggregate summaries can appear in chat replies; per-line-item details should not unless the user explicitly asks.

3. **Source data stays where it is.** Don't email it, don't paste it elsewhere, don't transform it into a format that strips audit trail.

## Math discipline (CRITICAL)

LLMs are confidently wrong about numbers. **Never report a financial figure that came out of agent reasoning.** Every figure in a deliverable must come from a code cell that the user can re-run.

- Arithmetic → use the IPython interpreter (`pandas`, `numpy`).
- Aggregations → groupby + sum/mean, not "I added these in my head".
- Date math → pandas date functions, not eyeballed.
- Currency formatting → format strings on numeric values, not text manipulation.

If you find yourself about to claim "revenue increased about 12%", first run the actual percentage in IPython. The number you compute may be 8.7%.

## Standard structure

```
mnt/finance/
└── private/                — never sent to external services
    ├── data/               — source CSVs, exports, parsed input (Loader)
    ├── analysis/           — variance, ratios, intermediate findings (Analyst)
    ├── models/             — forecasts, scenarios (Modeler)
    └── reports/            — final reports (Reporter)
```

## Roster

| Agent | Owns |
|---|---|
| Orchestrator | Routing only. |
| DataLoader | Ingest + normalize source data. |
| Analyst | Backwards-looking: variance, ratios, trends. |
| Modeler | Forwards-looking: forecasts, scenarios. |
| Reporter | Final write-up combining analyst + modeler output. |
