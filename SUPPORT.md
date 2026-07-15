# Support

Epicure MCP is a public beta service operated by KAIKAKU.AI Limited.

- **Service status:** [epicure-mcp.kaikaku.ai/healthz](https://epicure-mcp.kaikaku.ai/healthz)
- **Usage guide:** [epicure.kaikaku.ai/agents](https://epicure.kaikaku.ai/agents)
- **Bug reports:** [GitHub Issues](https://github.com/KAIKAKU-AI/epicure-mcp/issues)
- **Private support:** [hello@kaikaku.ai](mailto:hello@kaikaku.ai)
- **Security reports:** follow [SECURITY.md](SECURITY.md)

For a useful bug report, include the MCP client and version, tool name,
sanitised arguments, approximate timestamp and timezone, and the error text.
Never post API tokens, private conversations, or personal data in an issue.

## Common checks

1. Confirm the health endpoint returns `{"status":"ok"}`.
2. Confirm the connector URL ends in `/mcp`.
3. Select **None** when the client asks for authentication.
4. Remove and re-add the connector if the client cached an older tool list.
5. Retry after a minute if the client reports HTTP 429.

Support is best effort. Availability and response times are not guaranteed.
