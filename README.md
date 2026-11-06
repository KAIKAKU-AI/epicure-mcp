# Epicure MCP

[Epicure](https://epicure.kaikaku.ai/agents) is a public, anonymous,
read-only Model Context Protocol server for computational flavour exploration.
It exposes deterministic tools over 1,790 ingredient embeddings learned from a
4.14 million-recipe, multilingual corpus.

- **MCP endpoint:** `https://epicure-mcp.kaikaku.ai/mcp`
- **Health check:** `https://epicure-mcp.kaikaku.ai/healthz`
- **Interactive guide:** [epicure.kaikaku.ai/agents](https://epicure.kaikaku.ai/agents)
- **Authentication:** none
- **Transport:** Streamable HTTP

The production origin runs on KAIKAKU's local compute cluster and is published
through a Cloudflare Tunnel. It is not hosted on Google Cloud or Azure. Every
tool reads the bundled model artefacts; the MCP server makes no external AI or
data-provider calls.

## Connect from Cursor

### Marketplace plugin (recommended)

This repository is packaged as a Cursor Plugin (`.cursor-plugin/plugin.json` +
`mcp.json`). After it is listed, install **Epicure** from
[Cursor Marketplace](https://cursor.com/marketplace) or **Customize → Plugins**.

Until the listing is live, install from this checkout for local testing:

```bash
mkdir -p ~/.cursor/plugins/local
ln -sfn "$(pwd)" ~/.cursor/plugins/local/epicure
```

Reload Cursor, enable the plugin, then try:

- “Use Epicure to build a vegan pairing graph around tomato and basil.”
- “Compare miso and soy sauce on the savoury axis.”
- “What ingredients are nearest to saffron in Epicure’s flavour space?”
- “Move rice 30 degrees toward the South Asian cuisine direction.”
- “Show where yuzu sits on Epicure’s ingredient atlas.”
- “Find a flavour trade-off from miso along a coherent factor.”

Submission checklist: [docs/CURSOR_MARKETPLACE_SUBMISSION.md](docs/CURSOR_MARKETPLACE_SUBMISSION.md).
Validate scaffolding with `python scripts/validate_plugin.py`.

### Manual MCP entry

In Cursor MCP settings, add:

```json
{
  "mcpServers": {
    "epicure": {
      "type": "http",
      "url": "https://epicure-mcp.kaikaku.ai/mcp"
    }
  }
}
```

No API key is required for the public endpoint.

## Connect from Claude

In Claude, open **Settings → Connectors → Add custom connector** and enter:

```text
Name: Epicure
URL:  https://epicure-mcp.kaikaku.ai/mcp
Auth: None
```

Tool outputs describe learned statistical relationships. They are not food
safety, allergy, medical, or nutritional advice.

## Tools

All tools advertise read-only, non-destructive, idempotent, closed-world MCP
annotations and validated JSON schemas.

| Tool title | MCP name | Purpose |
| --- | --- | --- |
| Compare ingredients on an axis | `compare_on_axis` | Compare two ingredients along a named flavour, cuisine, nutrient, diet, or processing axis. |
| Score an ingredient pairing | `pairing_score` | Measure cosine affinity for one exact ingredient pair. |
| Explore ingredient pairings | `find_pairings` | Build a diversified cluster-and-bridge pairing graph for one or more seeds. |
| Inspect flavour correlations | `flavour_correlations` | Return the strongest relationships between named flavour-space axes. |
| Profile an ingredient by cuisine | `cultural_profile` | Measure an ingredient against the bundled cuisine directions. |
| Find similar ingredients | `neighbors` | Return nearest ingredients in the 300-dimensional embedding. |
| Transform an ingredient in flavour space | `morph` | Rotate a seed toward a direction, mode, or ingredient using spherical interpolation. |
| List transformation targets | `list_targets` | Page through valid directions and emergent modes for `morph`. |
| List flavour factors | `list_factors` | Inspect the 20 named ICA factor summaries, with examples available on request. |
| Project an ingredient onto a factor | `ingredient_on_factor` | Measure signed position on an ICA factor. |
| Navigate a flavour trade-off | `pareto_navigate` | Find ingredients on a proximity-versus-factor Pareto frontier. |
| Find an ingredient’s flavour region | `closest_mode` | Find the closest named GMM modes. |
| Locate an ingredient on the atlas | `where_on_atlas` | Return the precomputed atlas coordinate and nearby 2-D peers. |

Large catalogues are filtered and paginated. Default responses are deliberately
compact; callers can request more detail through each tool's documented inputs.

## Data and privacy

Epicure has no accounts, cookies, user profiles, or advertising. Tool arguments
and result content are processed in memory and are never written to application
logs. Minimal operational telemetry contains a rotating pseudonymous client
hash, tool name, response size, latency, success state, and exception class.

Read the complete [Privacy Policy](PRIVACY.md), [Security Policy](SECURITY.md),
[Support Policy](SUPPORT.md), and [Terms](TERMS.md).

## Architecture

```text
MCP client
    │  HTTPS / Streamable HTTP
    ▼
Cloudflare edge (TLS, DDoS controls, WAF/rate limits)
    │  outbound-only Cloudflare Tunnel
    ▼
reef-cluster on local KAIKAKU compute
    └── epicure-mcp container
          └── bundled read-only model artefacts
```

The origin binds to loopback on the cluster host. No inbound router port is
opened; `cloudflared` initiates the tunnel from the private Docker network.
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for operations,
[docs/CLAUDE_SUBMISSION.md](docs/CLAUDE_SUBMISSION.md) for the Claude directory
listing, and [docs/CURSOR_MARKETPLACE_SUBMISSION.md](docs/CURSOR_MARKETPLACE_SUBMISSION.md)
for the Cursor Marketplace package.

## Local development

Python 3.11 or newer is supported (production uses Python 3.12).

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/verify_data.py --data-dir data
ruff check src tests scripts
pytest -q
python -m epicure_mcp.server
```

The local endpoints are:

| Path | Method | Purpose |
| --- | --- | --- |
| `/healthz` | GET | Lightweight liveness probe. |
| `/mcp` | POST/GET/DELETE | Streamable HTTP MCP transport. |
| `/provenance` | GET | Content-addressed runtime bundle and application identity. |
| `/atlas` | GET | Read-only 3-D UMAP projection used by the Epicure site. |
| `/favicon.ico`, `/favicon.png` | GET | Connector icon. |

Inspect the local server with the official MCP Inspector:

```bash
npx -y @modelcontextprotocol/inspector \
  --cli http://127.0.0.1:8080/mcp --transport http --method tools/list
```

Run the complete remote smoke suite against production:

```bash
python scripts/smoke_test_remote.py https://epicure-mcp.kaikaku.ai/mcp
```

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `EPICURE_DATA_DIR` | `<repo>/data` | Bundled artefact directory. |
| `EPICURE_ASSETS_DIR` | bundled assets | Optional favicon directory. |
| `EPICURE_RELEASE_ID` | `exploratory-unmatched-1790-runtime` | Runtime release label. The default deliberately does not claim identity with a public Cooc, Core, or Chem release. |
| `EPICURE_APPLICATION_SHA256` | unset | Optional 64-character digest for an immutable application or image build. Without it, `/provenance` returns a deterministic installed-source hash labelled `development_source_manifest`. |
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8080` | Bind port. |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-client token refill rate. |
| `RATE_LIMIT_BURST` | `10` | Per-client burst capacity. |
| `MCP_SERVER_NAME` | `Epicure` | Name in the MCP initialize response. |
| `MCP_AUTH_MODE` | `none` | Authentication mode: anonymous `none`, or explicit `bearer` for a private deployment. |
| `MCP_API_TOKEN` | unset | Bearer credential required when `MCP_AUTH_MODE=bearer`. For backward compatibility, a token with no mode retains legacy bearer auth; public deployments must pin `MCP_AUTH_MODE=none`. |
| `MCP_ALLOWED_HOSTS` | production + local hosts | Comma-separated DNS-rebinding allowlist. |
| `MCP_ALLOWED_ORIGINS` | ChatGPT, Claude, Cursor, Epicure + local origins | Comma-separated browser-origin allowlist. |

## Bundled artefacts

The repository includes the model bundle, so production does not depend on an
upstream service at runtime. It contains embeddings and ingredient metadata,
supervised directions, ICA factors, GMM modes, and 2-D/3-D UMAP projections.
Validate shape and presence with `scripts/verify_data.py` after any refresh.

### Runtime provenance

`GET /provenance` returns the exact runtime identity used by benchmark clients:
the configured release label, ingredient count and embedding dimensions, a
canonical manifest of every bundled data file, the manifest-derived bundle
SHA-256, and the application SHA-256. The data manifest is sorted by relative
POSIX path and records each file's byte count and SHA-256; the bundle digest is
the SHA-256 of its canonical JSON representation.

When bearer authentication is enabled, `/provenance` requires the same bearer
token as `/mcp` and `/atlas`. Responses are always `Cache-Control: no-store`. The
endpoint is GET-only and does not load or mutate the embedding model.

Release deployments should set `EPICURE_APPLICATION_SHA256` from an immutable
image or application build. If it is absent, Epicure hashes the installed
Python files deterministically and marks the result as a development identity.
That fallback is useful for local and exploratory runs, but is not evidence of
a published application release. Likewise, the default
`exploratory-unmatched-1790-runtime` label intentionally does not identify the
bundled vectors as any public Cooc, Core, or Chem sibling.

## License

[MIT](LICENSE) © KAIKAKU.AI Limited.
