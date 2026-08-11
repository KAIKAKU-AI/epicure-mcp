---
name: epicure-flavour-tools
description: Use Epicure MCP tools for ingredient neighbours, axis comparisons, cuisine profiles, morphs, factors, and atlas placement. Use when exploring flavour space, substitutions, or culinary structure with Epicure.
---

# Epicure flavour tools

Epicure is a public, anonymous, read-only MCP over 1,790 ingredient embeddings.
Results are deterministic statistical relationships from bundled artefacts — not
food safety, allergy, medical, or nutritional advice.

## When to use which tool

| Goal | Tool |
| --- | --- |
| Nearest substitutes / neighbours | `neighbors` |
| Compare two ingredients on an axis | `compare_on_axis` |
| Exact pair affinity | `pairing_score` |
| Cuisine association | `cultural_profile` |
| Axis relationships | `flavour_correlations` |
| Rotate toward a direction/mode/ingredient | `morph` (+ `list_targets`) |
| Named ICA factors | `list_factors`, `ingredient_on_factor` |
| Trade-off frontier | `pareto_navigate` |
| Flavour region / mode | `closest_mode` |
| 2-D atlas placement | `where_on_atlas` |
| Diversified pairing graph | `find_pairings` |

Prefer compact defaults. Only request expanded detail when the user needs it.
Use exact ingredient names from the Epicure catalogue; if a name fails, try a
common synonym or ask the user to clarify.

## Response posture

- Cite the Epicure tool results; do not invent embeddings or scores.
- Separate culinary creativity from safety: never claim allergen-free or dietary
  compliance from Epicure alone.
- Prefer a short recommendation plus the supporting numbers or neighbours.
