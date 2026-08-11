---
name: epicure-pairing-workflow
description: Build diversified Epicure pairing graphs and score ingredient affinities. Use when the user wants pairings, menus, bridges between seeds, or vegan/dietary-constrained flavour graphs via Epicure MCP.
---

# Epicure pairing workflow

1. Confirm seed ingredients (one or more). Prefer catalogue names Epicure knows.
2. Call `find_pairings` for a diversified cluster-and-bridge graph.
3. Optionally validate key edges with `pairing_score`.
4. For substitution ideas around a seed, use `neighbors` and optionally
   `compare_on_axis` on a relevant sensory or cuisine axis.
5. Summarise: recommended partners, bridges between clusters, and any weak or
   surprising edges worth tasting notes — not health claims.

Keep graphs actionable: highlight a small set of high-signal partners rather
than dumping the full tool payload unless the user asks for detail.
