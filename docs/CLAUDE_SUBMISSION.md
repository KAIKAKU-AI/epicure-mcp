# Claude Connector Directory submission

This is the copy-ready listing and release checklist for the Epicure connector.

## Listing

| Field | Value |
| --- | --- |
| Name | Epicure |
| Tagline | Computational flavour intelligence for culinary agents |
| Company | KAIKAKU.AI Limited |
| MCP URL | `https://epicure-mcp.kaikaku.ai/mcp` |
| Authentication | None |
| Documentation | `https://epicure.kaikaku.ai/agents` |
| Privacy policy | `https://epicure.kaikaku.ai/privacy` |
| Support | `https://epicure.kaikaku.ai/support` |
| Contact | `hello@kaikaku.ai` |

### Description

Epicure gives Claude read-only access to a computational flavour model spanning
1,790 ingredients. It can explore pairings, compare ingredients on sensory and
cultural axes, find substitutions and neighbours, locate ingredients on a
flavour atlas, and navigate interpretable flavour transformations. Results are
deterministic and computed from bundled model artefacts; no external model is
called.

### Example prompts

1. Use Epicure to build a vegan pairing graph around tomato and basil.
2. Compare miso and soy sauce on the savoury axis.
3. What are the five nearest ingredients to saffron?
4. Move rice 30 degrees toward the South Asian cuisine direction.
5. Where does yuzu sit on the ingredient atlas, and what is nearby?
6. Which cuisine directions are most associated with tahini?
7. Find a coherent flavour factor for miso and show its Pareto frontier.
8. What named flavour-space axes are strongly opposed?

### Tool catalogue

| Title | Name |
| --- | --- |
| Compare ingredients on an axis | `compare_on_axis` |
| Score an ingredient pairing | `pairing_score` |
| Explore ingredient pairings | `find_pairings` |
| Inspect flavour correlations | `flavour_correlations` |
| Profile an ingredient by cuisine | `cultural_profile` |
| Find similar ingredients | `neighbors` |
| Transform an ingredient in flavour space | `morph` |
| List transformation targets | `list_targets` |
| List flavour factors | `list_factors` |
| Project an ingredient onto a factor | `ingredient_on_factor` |
| Navigate a flavour trade-off | `pareto_navigate` |
| Find an ingredient's flavour region | `closest_mode` |
| Locate an ingredient on the atlas | `where_on_atlas` |

Every tool is annotated read-only, non-destructive, idempotent, and
closed-world. Descriptions are neutral, tool-specific, and contain no
instructions that override Claude or compel tool use.

## Data handling answers

- No account or test credentials are required.
- Tool inputs and outputs are not persisted or logged.
- The service logs only rotating pseudonymous operational telemetry described
  in `PRIVACY.md`.
- The service does not sell data or use requests to train a model.
- Cloudflare provides the network edge and tunnel; the application runs on
  KAIKAKU's local compute cluster.
- The tools do not expose external links, interactive UI, write operations, or
  third-party API side effects.

## Release checklist

- [x] CI passes on the exact submitted revision.
- [x] `scripts/verify_data.py` succeeds.
- [x] Official MCP Inspector connects to the public URL.
- [x] All 13 live tool calls return successful MCP results.
- [x] Invalid enums and unknown ingredients return `isError: true`.
- [x] Tool titles and all four behaviour hints appear in live `tools/list`.
- [x] Default catalogue results remain compact.
- [x] `/healthz`, documentation, privacy, support, and security links are public.
- [ ] The connector is added to a regular Claude account and at least three
      example prompts complete successfully.
- [ ] The exact production URL is entered in the Claude submission form.

The final Claude-account test is intentionally manual because it verifies the
same user-facing connector flow the directory reviewer will use.
