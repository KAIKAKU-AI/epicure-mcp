# Epicure MCP Privacy Policy

**Effective date:** 14 July 2026<br>
**Operator:** KAIKAKU.AI Limited<br>
**Contact:** [hello@kaikaku.ai](mailto:hello@kaikaku.ai)

This policy covers the public Epicure Model Context Protocol service at
`https://epicure-mcp.kaikaku.ai/mcp` and its supporting health, atlas, and icon
endpoints.

## What the service processes

When an MCP client calls a tool, Epicure processes the supplied ingredient
names, filters, and other tool parameters in memory to produce a response from
the bundled flavour model. Epicure does not require an account and does not
receive your complete Claude conversation unless a client explicitly includes
text in a tool argument.

The application records only this operational telemetry:

- timestamp;
- tool name;
- response size and processing latency;
- success state and, on failure, the exception class; and
- a 16-character client-IP hash made with a random process-local salt that
  rotates at UTC midnight.

Tool arguments, ingredient queries, result content, prompts, chat history,
uploaded files, authentication credentials, and raw IP addresses are not
written to Epicure application logs. The raw network address exists briefly in
memory for rate limiting and generation of the rotating hash.

## Why it is processed

Tool inputs are processed to provide the result requested by the MCP client.
Minimal telemetry is used to operate the service, diagnose failures, measure
latency, and limit abuse. It is not used for advertising, user profiling, or
training an AI model.

## Storage and retention

Epicure stores no MCP account or conversation database. Operational telemetry
is written to a local rolling container log capped at two 2 MiB files for the
MCP service. Old records are overwritten on rotation and records are removed
when the container logs are removed. KAIKAKU does not forward or archive these
application logs to a long-term analytics service.

Because the hash salt rotates daily and is not retained separately, hashes
cannot be linked by KAIKAKU across salt rotations. A redeployment may rotate the
salt earlier.

## Service providers and international processing

Cloudflare provides DNS, TLS termination, DDoS protection, rate limiting, and
the outbound tunnel to KAIKAKU's local compute cluster. Cloudflare may process
network metadata such as IP addresses under its
[Privacy Policy](https://www.cloudflare.com/privacypolicy/). The Epicure MCP
application does not send tool inputs to Google, OpenRouter, Anthropic, or any
other model provider.

## Sharing and sale

KAIKAKU does not sell MCP data. It does not share tool inputs or outputs with
advertisers or data brokers. Information may be disclosed if legally required
or when necessary to protect the service and its users.

## Security

The service uses HTTPS, an outbound-only Cloudflare Tunnel, a loopback-bound
origin, request validation, rate limits, DNS-rebinding protection, and
read-only tool semantics. See [SECURITY.md](SECURITY.md) for reporting a
vulnerability.

## Your choices and rights

Epicure does not maintain a user account or a stable application identifier,
so it usually cannot associate telemetry with a named individual. You may stop
processing by disabling or removing the connector. For privacy questions or a
rights request, email [hello@kaikaku.ai](mailto:hello@kaikaku.ai). We may need
enough detail to identify information that can reasonably be located.

## Changes

Material changes will be published in this repository with a new effective
date. Continued use after a change means the updated policy applies to later
requests.
