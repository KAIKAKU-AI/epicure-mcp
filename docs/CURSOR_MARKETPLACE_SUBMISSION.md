# Cursor Marketplace plugin submission

Copy-ready listing and release checklist for publishing Epicure as a Cursor
Plugin (MCP + skills/rules/commands). Official flow:
[cursor.com/marketplace/publish](https://cursor.com/marketplace/publish).

Prepared: 2026-08-11. Live portal inspected the same day while signed in as
Josef Ultra (`josef@kaikaku.ai`).

## Listing (repo / manifest)

| Field | Value |
| --- | --- |
| Plugin name | `epicure` |
| Display name | Epicure |
| Tagline | Computational flavour intelligence for culinary agents |
| Company | KAIKAKU.AI Limited |
| Repository | `https://github.com/KAIKAKU-AI/epicure-mcp` |
| MCP URL | `https://epicure-mcp.kaikaku.ai/mcp` |
| Authentication | None |
| Documentation | `https://epicure.kaikaku.ai/agents` |
| Privacy policy | Repository `PRIVACY.md` / `https://epicure.kaikaku.ai/privacy` |
| Support | `SUPPORT.md` / `https://epicure.kaikaku.ai/support` |
| License | MIT (permissive; required for Marketplace) |
| Contact | `hello@kaikaku.ai` |
| Logo | `assets/logo.svg` (1:1, background plate) |

### Description (marketplace / publisher form)

Epicure is a public, anonymous, read-only MCP server for computational flavour
exploration over 1,790 ingredient embeddings from a 4.14M-recipe corpus.
Pairings, cuisine axes, morph, and atlas tools for food AI agents.

Longer listing copy (README / site):

Epicure gives Cursor agents read-only access to a computational flavour model
spanning 1,790 ingredients. Explore pairings, compare ingredients on sensory and
cultural axes, find substitutions and neighbours, locate ingredients on a
flavour atlas, and navigate interpretable flavour transformations. Results are
deterministic and computed from bundled model artefacts; no external model is
called at serve time.

### Keywords

`mcp`, `flavour`, `flavor`, `culinary`, `ingredients`, `pairings`, `food`,
`embeddings`, `epicure`, `kaikaku`

### Example prompts

1. Use Epicure to build a vegan pairing graph around tomato and basil.
2. Compare miso and soy sauce on the savoury axis.
3. What are the five nearest ingredients to saffron?
4. Move rice 30 degrees toward the South Asian cuisine direction.
5. Where does yuzu sit on the ingredient atlas, and what is nearby?

## Live publish form fields

Portal URL: [cursor.com/marketplace/publish](https://cursor.com/marketplace/publish)
(“Become a plugin publisher”). This is a **publisher application + first plugin
repo** form — not a multi-step wizard with separate MCP/privacy/screenshot
fields. Plugin identity mostly comes from the public GitHub packaging.

| Field | Recommended value | Notes |
| --- | --- | --- |
| Organization name | `KAIKAKU.AI` | Draft filled |
| Organization handle | `kaikaku` | Unique kebab-case namespace; uniqueness checked at submit |
| Contact email | `hello@kaikaku.ai` | Draft filled |
| Logotype URL | `https://raw.githubusercontent.com/KAIKAKU-AI/epicure-mcp/main/assets/logo.svg` | After `logo.svg` is on `main`. Interim live URL already on GitHub: `.../assets/favicon-v2.svg`. Form requires **1:1 SVG or PNG with background plate**. |
| Description | Short description above | Draft filled |
| GitHub repository | `https://github.com/KAIKAKU-AI/epicure-mcp` | Must be **public** and contain the plugin package |
| Owner | `Individual · josef@kaikaku.ai` | Locked on this account |
| Website URL | `https://epicure.kaikaku.ai/agents` | Draft filled |

**Not on the form** (comes from repo / manifest): plugin `name` / `displayName`,
MCP URL (`mcp.json`), privacy URL, screenshots, pricing, auth, category/tags.

**Irreversible gate:** button **Submit Application** — clicking acknowledges the
[Publisher Terms](https://cursor.com/marketplace-publisher-terms). No separate
payment step. Do not click until packaging is on public `main` and the human
publisher accepts the terms.

Contact for questions: `marketplace-publishing@cursor.com`.

### Marketplace rules that affect Epicure

- Listing is free; plugins must remain free via Marketplace.
- Open source + permissive license required (MIT OK; no GPL/AGPL/LGPL).
- Manual review (typically ~1–2 weeks); updates are also manually reviewed.
- Epicure is **not** currently listed (marketplace search returns no results).

## Plugin package contents

| Path | Role |
| --- | --- |
| `.cursor-plugin/plugin.json` | Cursor Plugin manifest |
| `mcp.json` | HTTP MCP server entry (production URL, `"type": "http"`) |
| `skills/` | Agent skills for tool selection and pairing workflows |
| `rules/` | Optional guidance when culinary questions arise |
| `commands/` | Slash commands for pairings and neighbours |
| `agents/` | Specialized culinary analyst subagent |
| `assets/logo.svg` | Marketplace logo (1:1 plate) |

This is a **single-plugin** repository (no `.cursor-plugin/marketplace.json`).

## Submission checklist

### Manifest and package (local)

- [x] `.cursor-plugin/plugin.json` with kebab-case `name`, description, version, author, license, logo
- [x] `mcp.json` points at the public Streamable HTTP endpoint (no secrets / no `${VAR}`)
- [x] Logo committed locally and referenced by relative path (`assets/logo.svg`)
- [x] Skills / rules / agents / commands have required frontmatter
- [x] `README.md` documents Cursor install and configuration
- [x] `LICENSE`, `PRIVACY.md`, `SECURITY.md`, `SUPPORT.md`, `TERMS.md` present
- [x] `python scripts/validate_plugin.py` passes
- [x] Local install symlink: `~/.cursor/plugins/local/epicure` → this checkout

### Runtime readiness (production)

- [x] `/healthz` returns OK on `https://epicure-mcp.kaikaku.ai/healthz`
- [x] Desktop-style MCP `initialize` without `Origin` succeeds
- [ ] **Deploy** the Cursor origin allowlist update (`MCP_ALLOWED_ORIGINS` defaults
      now include `cursor.com` / `cursor.sh`) to production before relying on
      browser/webview clients that send an `Origin` header (OPTIONS with
      `Origin: https://cursor.com` still returns `403` as of 2026-08-11)
- [ ] Local plugin smoke in Cursor UI: Customize → Plugins → enable Epicure,
      then run an example prompt
- [ ] Screenshots optional — not requested by the current publish form

### Portal steps (human)

1. **Commit and push** plugin scaffolding to public `main` on
   `KAIKAKU-AI/epicure-mcp` (packaging is local-only until then).
2. Redeploy production MCP so Cursor origins are allowed (see
   [DEPLOYMENT.md](DEPLOYMENT.md)).
3. Open [cursor.com/marketplace/publish](https://cursor.com/marketplace/publish)
   while signed into the publisher Cursor account (draft already prepared for
   Josef Ultra; refresh Logotype URL to `assets/logo.svg` raw URL after push).
4. Confirm Organization handle (`kaikaku`) is acceptable; if taken, try
   `kaikaku-ai` / `epicure`.
5. Decide whether **Individual** ownership is OK, or ask Cursor for a company
   publisher before submitting.
6. Click **Submit Application** only when ready to accept Publisher Terms.
7. Wait for Cursor’s manual review (~1–2 weeks); escalate via
   `marketplace-publishing@cursor.com` if stuck.

There is no local CLI that completes marketplace publication; the publish portal
is required.

## Local validation commands

```bash
python scripts/validate_plugin.py
python scripts/verify_data.py --data-dir data
pytest -q
python scripts/smoke_test_remote.py https://epicure-mcp.kaikaku.ai/mcp
```

Optional: install for local Cursor testing without publishing:

```bash
mkdir -p ~/.cursor/plugins/local
ln -sfn "$(pwd)" ~/.cursor/plugins/local/epicure
```

Then reload Cursor Customize / Plugins and enable Epicure.

## Data handling answers (reviewers)

- No account or API keys required for the public MCP.
- Tool inputs/outputs are not persisted in application logs (see `PRIVACY.md`).
- Operational telemetry is rotating pseudonymous client hashes + tool metrics.
- No advertising, no training on user prompts, no write tools.
- Cloudflare provides the edge tunnel; origin runs on KAIKAKU local compute.
