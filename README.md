# Epicure MCP

[![MCP status](https://mcpvitals.com/badge/4997b92450.svg)](https://mcpvitals.com/status/4997b92450)

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

## Connect from Claude

In Claude, open **Settings → Connectors → Add custom connector** and enter:

```text
Name: Epicure
URL:  https://epicure-mcp.kaikaku.ai/mcp
Auth: None
```

Try one of these prompts after enabling the connector:

- “Use Epicure to build a vegan pairing graph around tomato and basil.”
- “Compare miso and soy sauce on the savoury axis.”
- “What ingredients are nearest to saffron in Epicure’s flavour space?”
- “Move rice 30 degrees toward the South Asian cuisine direction.”
- “Show where yuzu sits on Epicure’s ingredient atlas.”
- “Find a flavour trade-off from miso along a coherent factor.”

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
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for operations and
[docs/CLAUDE_SUBMISSION.md](docs/CLAUDE_SUBMISSION.md) for the directory listing.

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
| `HOST` | `0.0.0.0` | Bind address. |
| `PORT` | `8080` | Bind port. |
| `RATE_LIMIT_PER_MINUTE` | `60` | Per-client token refill rate. |
| `RATE_LIMIT_BURST` | `10` | Per-client burst capacity. |
| `MCP_SERVER_NAME` | `Epicure` | Name in the MCP initialize response. |
| `MCP_API_TOKEN` | unset | Optional bearer token for private deployments. Production leaves this unset. |
| `MCP_ALLOWED_HOSTS` | production + local hosts | Comma-separated DNS-rebinding allowlist. |
| `MCP_ALLOWED_ORIGINS` | Claude, Epicure + local origins | Comma-separated browser-origin allowlist. |

## Bundled artefacts

The repository includes the model bundle, so production does not depend on an
upstream service at runtime. It contains embeddings and ingredient metadata,
supervised directions, ICA factors, GMM modes, and 2-D/3-D UMAP projections.
Validate shape and presence with `scripts/verify_data.py` after any refresh.

## License

[MIT](LICENSE) © KAIKAKU.AI Limited.
