---
name: epicure-pair
description: Build an Epicure pairing graph for one or more seed ingredients
---

Use Epicure MCP to explore pairings for the ingredients named in the user's
follow-up (or ask for seeds if none were given).

1. Call `find_pairings` with the seed ingredients.
2. Optionally score 2–4 promising edges with `pairing_score`.
3. Return a concise pairing brief: top partners, useful bridges, and one or two
   creative directions — without food-safety claims.
