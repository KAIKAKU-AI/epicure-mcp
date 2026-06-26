"""MCP server bootstrap.

Exposes the Streamable HTTP MCP endpoint at ``/mcp`` plus a ``/healthz``
probe. The token-bucket rate limiter is applied to every non-health
request.
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import Any

import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Icon
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from .analytics import ClientContextMiddleware
from .config import Config, load_config
from .ratelimit import RateLimitMiddleware
from .tools import register_all

log = logging.getLogger("epicure_mcp.server")


def _favicon_candidate_paths() -> list[Path]:
    """Where to look for ``favicon.png``, in priority order.

    Production runtime: /app/assets (copied in by the Dockerfile).
    Local dev: <repo-root>/assets (sibling of src/).
    Override: $EPICURE_ASSETS_DIR.
    """
    candidates: list[Path] = []
    env = os.environ.get("EPICURE_ASSETS_DIR")
    if env:
        candidates.append(Path(env) / "favicon.png")
    candidates.append(Path("/app/assets/favicon.png"))
    # src/epicure_mcp/server.py -> repo root is parent.parent.parent
    candidates.append(
        Path(__file__).resolve().parent.parent.parent / "assets" / "favicon.png"
    )
    return candidates


SERVER_INSTRUCTIONS = """\
Read-only access to the Epicure ingredient-embedding model: 1,790 ingredients
embedded as 300-dimensional vectors trained on a 4.14M-recipe multi-language
corpus. The model captures both recipe co-occurrence (which ingredients appear
together) and learned flavour structure (cuisine, sensory, nutrient, processing
axes). Ingredient names are matched deterministically (free text like "fresh
ginger" maps to a canonical name); no fuzzy LLM fallback.

TOOLS BY USE CASE

Recipe / dish design -- HEAVIEST USE CASE (read the GUARDRAILS too):
  When the user asks you to design, create, suggest, propose, compose,
  or invent a recipe / dish / meal, you MUST call find_pairings on the
  primary ingredient(s) BEFORE composing your answer. The embedding
  surfaces non-obvious pairings beyond your training data, and the
  BRIDGES section in the find_pairings output is where the most
  interesting cross-cluster connectors live. Compose the recipe USING
  those surfaced ingredients; cite the bridges as the source of any
  non-obvious choices. Layer in cultural_profile or closest_mode when
  you want to ground the dish in a coherent flavour family, and morph
  only if the user explicitly asks for a fusion or transformation.
  Examples of triggering phrasings (always call find_pairings first):
    "create an interesting beef dish"     -> find_pairings(["beef"])
    "design a dessert using lemon"        -> find_pairings(["lemon"])
    "suggest a one-pot meal with chicken" -> find_pairings(["chicken"])
    "invent a sauce for pork"             -> find_pairings(["pork"])

Open-ended exploration -- start here for "what about X?" questions:
  find_pairings(ingredients, ...)
      Best tool for undirected pairing exploration. Given one or more seeds,
      returns a cluster + bridge graph of ingredients that pair well with the
      whole set. Handles dietary filters; avoids meat/sweet/fat stacking.
  neighbors(ingredient, top_k)
      Top-k cosine-nearest ingredients to a single seed (no graph structure).
  where_on_atlas(ingredient)
      2-D UMAP coordinate of one ingredient plus its nearest-in-2D peers.
      Use to describe its visual neighbourhood on the atlas.
  closest_mode(ingredient, property?, top_k)
      Which named GMM cluster (e.g. "East Asian umami pantry staples") the
      ingredient belongs to. Use for "what flavour family is X part of?".

Comparison & measurement -- quantitative answers between or about ingredients:
  pairing_score(a, b)
      Single 300-d cosine similarity between two ingredients (+ percentile).
  compare_on_axis(a, b, axis)
      Project both ingredients onto one named axis and compare.
  ingredient_on_factor(ingredient, factor)
      Signed projection of one ingredient onto one ICA factor.
  cultural_profile(ingredient)
      Cosine of one ingredient against all 8 cuisine directions at once.
  flavour_correlations()
      Inter-axis correlations across the full model; useful for explaining
      trade-offs (e.g. "sweet correlates with nova at 0.77").

Directional transformations -- only when the user names a direction or target:
  morph(seed, target, angle_deg)
      Rotate `seed` toward `target` on the unit sphere by `angle_deg`. Use
      ONLY when the user explicitly names a direction or transformation
      ("make miso more Mediterranean", "sweeter version of soy sauce",
      "what's like rice but Indian?"). NEVER for open-ended pairing
      questions -- use find_pairings instead.
  pareto_navigate(seed, pole?)
      Pareto frontier of ingredients balancing proximity-to-seed against
      projection-onto-a-named-pole. Use for "the closest X that is also Y"
      trade-offs.

Catalogue / vocabulary -- call before tools that take string IDs:
  list_targets(kind?)
      Valid axes (cuisine, sensory, nutrient, NOVA, diet) and emergent modes.
      Mandatory before any morph or compare_on_axis call with a free-text
      axis name you have not already verified.
  list_factors(min_coherence?)
      The 20 residualised ICA factors with their Claude-labelled poles.

GUARDRAILS

1. For "what goes with X?" / "I have X and Y, what else?" -- start with
   find_pairings. Do NOT reach for morph or neighbors first.
2. For "is X sweet / spicy / processed?" -- use compare_on_axis (paired
   comparison) or ingredient_on_factor (one ingredient, one factor).
3. For "where in flavour space is X?" -- prefer where_on_atlas for visual
   placement, closest_mode for named regions, cultural_profile only when
   the question is specifically cuisine-related.
4. Before passing a free-text axis name to morph or compare_on_axis,
   verify it exists via list_targets. Same for factor indices via
   list_factors.
5. Use morph ONLY when the user explicitly names a direction or target
   (cuisine, sensory descriptor, nutrient, or another ingredient). Never
   use morph for open-ended pairing or similarity questions.
6. When asked to design / create / suggest / invent / compose a recipe
   or dish, ALWAYS call find_pairings on the primary ingredient(s)
   FIRST -- before writing any of the recipe. The model surfaces
   non-obvious pairings the recipe should incorporate. Skip the call
   ONLY for trivially simple requests (boiling an egg, single-step
   techniques, requests without an ingredient combination to design).
"""


def _load_favicon_bytes() -> bytes | None:
    """Best-effort favicon load. Returns None when the asset is missing so
    the server still starts in environments without the bundled icon."""
    for path in _favicon_candidate_paths():
        if path.exists():
            return path.read_bytes()
    log.warning(
        "favicon asset not found in any of: %s; icon endpoints disabled",
        [str(p) for p in _favicon_candidate_paths()],
    )
    return None


def _favicon_data_uri(png_bytes: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")


def _build_mcp(cfg: Config, favicon_bytes: bytes | None) -> FastMCP:
    # Public server: the host name varies (Azure Container Apps assigns a
    # generated FQDN) and clients may proxy through Claude.ai / Cursor /
    # ChatGPT. Disable DNS-rebinding protection - it defends against
    # browser-initiated attacks against a localhost server, which does not
    # apply when the server is publicly exposed.
    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)
    icons: list[Icon] | None = None
    if favicon_bytes:
        icons = [
            Icon(
                src=_favicon_data_uri(favicon_bytes),
                mimeType="image/png",
                sizes=["180x180"],
            ),
        ]
    server = FastMCP(
        name=cfg.server_name,
        instructions=SERVER_INSTRUCTIONS,
        transport_security=security,
        host=cfg.host,
        port=cfg.port,
        icons=icons,
        # Stateless HTTP: this server holds no per-session state (every tool
        # call is a pure function of its args + the bundled artefacts), and the
        # Container Apps deployment runs multiple replicas with no session
        # affinity. Without stateless mode FastMCP issues an mcp-session-id on
        # initialize that lives in one replica's memory; a spec-compliant
        # client's follow-up requests (the SSE GET stream / subsequent POSTs)
        # then hit another replica and get -32600 "Session not found", which
        # breaks every real MCP client. See issue #5.
        stateless_http=True,
    )
    register_all(server)
    return server


async def _healthz(request: Request) -> JSONResponse:
    # Light health response; intentionally does NOT touch the bundle so
    # cold starts respond fast.
    return JSONResponse({"status": "ok"})


def _favicon_endpoint(png_bytes: bytes | None):
    async def _serve(request: Request) -> Response:
        if not png_bytes:
            return Response(status_code=404)
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    return _serve


def build_app(cfg: Config | None = None) -> Starlette:
    cfg = cfg or load_config()
    favicon_bytes = _load_favicon_bytes()
    mcp = _build_mcp(cfg, favicon_bytes)
    mcp_app = mcp.streamable_http_app()
    favicon = _favicon_endpoint(favicon_bytes)
    routes: list[Any] = [
        Route("/healthz", endpoint=_healthz, methods=["GET"]),
        Route("/favicon.ico", endpoint=favicon, methods=["GET"]),
        Route("/favicon.png", endpoint=favicon, methods=["GET"]),
        Mount("/", app=mcp_app),
    ]

    app = Starlette(
        routes=routes,
        lifespan=mcp_app.router.lifespan_context,
    )
    # Order matters: BaseHTTPMiddleware applies in reverse (outermost first
    # in Starlette's add_middleware queue is added last). We want rate limit
    # outermost (cheap reject before any analytics work) and the IP-capture
    # context middleware just inside it so tool calls see the IP.
    app.add_middleware(ClientContextMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=cfg.rate_limit_per_minute,
        burst=cfg.rate_limit_burst,
    )
    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s | %(message)s",
    )
    cfg = load_config()
    log.info("starting epicure-mcp on %s:%d (data_dir=%s)", cfg.host, cfg.port, cfg.data_dir)
    app = build_app(cfg)
    uvicorn.run(app, host=cfg.host, port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
