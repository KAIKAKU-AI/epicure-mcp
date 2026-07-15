# Security Policy

## Report a vulnerability privately

Please use [GitHub private vulnerability reporting](https://github.com/KAIKAKU-AI/epicure-mcp/security/advisories/new)
or email [hello@kaikaku.ai](mailto:hello@kaikaku.ai) with the subject
`[SECURITY] Epicure MCP`. Do not include secrets or exploit details in a public
issue.

Include the affected endpoint or revision, impact, reproduction steps, and any
suggested mitigation. We will acknowledge a good-faith report within five
business days, investigate it, and coordinate remediation and disclosure.

## Scope

In scope:

- `https://epicure-mcp.kaikaku.ai`;
- the `epicure-mcp` source and container image; and
- authentication, request-validation, data-exposure, or availability defects
  directly affecting the connector.

Out of scope:

- social engineering, physical attacks, or denial-of-service load testing;
- automated scanning that materially degrades the public service;
- issues in third-party services without an Epicure-specific impact; and
- learned-model quality disagreements without a security consequence.

Please avoid accessing other people's data, disrupting the service, or
retaining data beyond what is needed to demonstrate the issue.

## Supported version

The production revision and the latest `main` branch receive security fixes.
Older revisions are not supported.
