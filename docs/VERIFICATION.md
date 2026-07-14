# Production verification record

**Endpoint:** `https://epicure-mcp.kaikaku.ai/mcp`<br>
**Verified:** 14 July 2026<br>
**Origin:** KAIKAKU `reef-cluster`, reached through Cloudflare Tunnel

## Automated checks

- Ruff lint and format checks passed.
- Bundled-data verification passed for 1,790 × 300 embeddings, 38 supervised
  directions, 20 ICA factors, 150 mode poles, and both UMAP projections.
- Pytest passed: **53 tests**.
- The production Docker image built successfully as `epicure-mcp` version
  1.0.0.

## Public endpoint checks

- The official MCP Inspector connected over Streamable HTTP.
- `tools/list` exposed exactly 13 tools.
- Every tool exposed a top-level title, matching annotation title, validated
  input schema, `readOnlyHint: true`, `destructiveHint: false`,
  `idempotentHint: true`, `openWorldHint: false`, and `noauth` metadata.
- One real production call to each of the 13 tools completed with
  `isError: false`.
- An unknown ingredient and an invalid catalogue enum both returned
  `isError: true`.
- Default result sizes, measured as compact JSON before MCP text framing, were
  2,391 bytes for `flavour_correlations`, 3,627 bytes for `list_targets`, and
  5,798 bytes for `list_factors`.
- `/mcp` returned `Cache-Control: no-store`, HSTS, no-sniff, no-referrer, and a
  restricted permissions policy.

## Privacy check

A unique unknown ingredient string was sent through the live MCP endpoint and
then searched across the MCP container logs. It was not present. The emitted
telemetry contained only the timestamp, rotating IP hash, tool name, result
size, latency, success state, and exception class described in `PRIVACY.md`.

## Website and service integration

- `https://epicure.kaikaku.ai/agents` returned HTTP 200.
- `https://epicure.kaikaku.ai/privacy` returned HTTP 200.
- `https://epicure.kaikaku.ai/support` returned HTTP 200.
- The website MCP status route reported 13 live, read-only, anonymous tools.
- The website MCP demo completed a real `pairing_score` call for tomato and
  basil.
- The same-origin website API and the direct authenticated API health checks
  both passed after deployment.

The remaining directory-specific check is to add the public endpoint to a
regular Claude account and exercise at least three prompts through Claude's
user interface before submitting the listing.
