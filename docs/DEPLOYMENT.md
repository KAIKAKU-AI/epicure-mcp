# Production deployment

Epicure MCP runs on KAIKAKU's local `reef-cluster` host and is exposed through
an outbound Cloudflare Tunnel. The public hostname is
`epicure-mcp.kaikaku.ai`; no Google Cloud or Azure runtime is in the request
path.

## Request path

```text
client → Cloudflare edge → named tunnel → cloudflared container
       → mcp:8080 on the private Compose network
```

The host publishes the MCP container on `127.0.0.1:18081` for local diagnostics
only. Public clients cannot connect directly to the origin host.

## Deploy

The multi-service Compose project lives at `/srv/epicure` on the cluster. Keep
secrets in `/srv/epicure/.env`; never commit or copy them into logs.

```bash
cd /srv/epicure
docker compose build mcp
docker compose up -d --no-deps mcp
docker compose ps mcp
docker compose logs --tail=100 mcp
```

The MCP service should use a bounded local log:

```yaml
logging:
  driver: json-file
  options:
    max-size: "2m"
    max-file: "2"
```

Cloudflare owns TLS, WAF, DDoS controls, and public edge rate limits. The Python
service applies its own token bucket, input validation, DNS-rebinding checks,
optional bearer middleware (disabled publicly), and response security headers.

Default `MCP_ALLOWED_ORIGINS` includes Claude and Cursor browser origins
(`https://cursor.com`, `https://cursor.sh`, and `www` variants). Desktop MCP
clients that omit `Origin` continue to work. After changing allowlists, rebuild
and redeploy only the `mcp` service, then verify with:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST https://epicure-mcp.kaikaku.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H 'Origin: https://cursor.com' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"cursor","version":"0"}}}'
```

Expect `200` once the new image is live (was `403` before the Cursor allowlist).

## Verify

```bash
curl --fail https://epicure-mcp.kaikaku.ai/healthz
python scripts/smoke_test_remote.py https://epicure-mcp.kaikaku.ai/mcp
npx -y @modelcontextprotocol/inspector \
  --cli https://epicure-mcp.kaikaku.ai/mcp \
  --transport http --method tools/list
```

Verification is complete only when all 13 tools are discoverable, every tool
has a title and read-only annotations, the smoke suite succeeds, invalid input
returns `isError: true`, and `/healthz` remains healthy through the tunnel.

## Roll back

Keep the prior image locally until verification completes. To roll back, check
out or restore the previously deployed revision in `/srv/epicure`, rebuild only
the `mcp` service, and repeat the verification commands. Do not restart the API
or webapp when only MCP changed.
