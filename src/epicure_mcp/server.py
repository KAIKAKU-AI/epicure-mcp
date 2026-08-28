"""MCP server bootstrap.

Exposes the Streamable HTTP MCP endpoint at ``/mcp``, a read-only ``/atlas``
projection, and a ``/healthz`` probe. Optional bearer authentication and the
token-bucket rate limiter are applied to every non-health request.
"""

from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import uvicorn
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import Icon
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from .analytics import ClientContextMiddleware
from .auth import BearerAuthMiddleware
from .config import Config, load_config
from .ratelimit import RateLimitMiddleware
from .security import SecurityHeadersMiddleware
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
        candidates.append(Path(env) / "favicon-v2.png")
        candidates.append(Path(env) / "favicon.png")
    candidates.append(Path("/app/assets/favicon-v2.png"))
    candidates.append(Path("/app/assets/favicon.png"))
    # src/epicure_mcp/server.py -> repo root is parent.parent.parent
    candidates.append(Path(__file__).resolve().parent.parent.parent / "assets" / "favicon-v2.png")
    candidates.append(Path(__file__).resolve().parent.parent.parent / "assets" / "favicon.png")
    return candidates


SERVER_INSTRUCTIONS = """\
Read-only access to the Epicure ingredient-embedding model: 1,790 ingredients
embedded as 300-dimensional vectors trained on a 4.14M-recipe multi-language
corpus. The model captures both recipe co-occurrence (which ingredients appear
together) and learned flavour structure (cuisine, sensory, nutrient, processing
axes). Ingredient names are matched deterministically (free text like "fresh
ginger" maps to a canonical name); no fuzzy LLM fallback.

Tool families:
- Pairing exploration: find_pairings, pairing_score, neighbors.
- Measurement: compare_on_axis, ingredient_on_factor, cultural_profile,
  flavour_correlations.
- Spatial context: where_on_atlas, closest_mode.
- Directed transformation: morph and pareto_navigate.
- Valid target catalogues: list_targets and list_factors.

find_pairings returns a diversified cluster-and-bridge graph for open-ended
pairing and recipe-design questions. pairing_score measures one exact pair,
while neighbors returns direct single-seed similarity. morph represents an
explicit directional transformation rather than undirected exploration.

The server is deterministic, anonymous, read-only, and does not call an AI
model or external data source. Tool outputs describe learned statistical
relationships, not food-safety, allergy, medical, or nutritional advice.
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
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=list(cfg.allowed_hosts),
        allowed_origins=list(cfg.allowed_origins),
    )
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
        website_url="https://epicure.kaikaku.ai/agents",
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


@lru_cache(maxsize=4)
def _load_atlas_payload(data_dir: str) -> dict[str, Any]:
    """Load and cache the 3-D projection without warming the full model."""
    root = Path(data_dir)
    coords = pd.read_csv(root / "umap_coords_3d.csv")
    tags = pd.read_csv(root / "ingredient_tags.csv", usecols=["name", "food_group"])
    groups = dict(zip(tags["name"].astype(str), tags["food_group"].astype(str), strict=False))
    points = [
        {
            "name": str(row.name),
            "x": round(float(row.x), 5),
            "y": round(float(row.y), 5),
            "z": round(float(row.z), 5),
            "group": groups.get(str(row.name), "Other"),
        }
        for row in coords.itertuples(index=False)
    ]
    return {
        "version": "umap-3d-v1",
        "dimensions": 3,
        "total": len(points),
        "source": "Epicure 300-dimensional ingredient embedding",
        "points": points,
    }


def _atlas_endpoint(cfg: Config):
    async def _serve(request: Request) -> JSONResponse:
        try:
            payload = _load_atlas_payload(str(cfg.data_dir.resolve()))
        except (FileNotFoundError, KeyError, ValueError) as exc:
            log.exception("atlas projection unavailable: %s", exc)
            return JSONResponse(
                {"error": "atlas_unavailable"},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        return JSONResponse(
            payload,
            headers={
                "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
            },
        )

    return _serve


def build_app(cfg: Config | None = None) -> Starlette:
    cfg = cfg or load_config()
    favicon_bytes = _load_favicon_bytes()
    mcp = _build_mcp(cfg, favicon_bytes)
    mcp_app = mcp.streamable_http_app()
    favicon = _favicon_endpoint(favicon_bytes)
    atlas = _atlas_endpoint(cfg)
    routes: list[Any] = [
        Route("/healthz", endpoint=_healthz, methods=["GET"]),
        Route("/favicon.ico", endpoint=favicon, methods=["GET"]),
        Route("/favicon.png", endpoint=favicon, methods=["GET"]),
        Route("/atlas", endpoint=atlas, methods=["GET"]),
        Mount("/", app=mcp_app),
    ]

    app = Starlette(
        routes=routes,
        lifespan=mcp_app.router.lifespan_context,
    )
    # Starlette applies middleware in reverse addition order. Client context
    # remains inside the rate limiter but around the MCP application so tool
    # calls can create their rotating client hash.
    app.add_middleware(ClientContextMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        per_minute=cfg.rate_limit_per_minute,
        burst=cfg.rate_limit_burst,
    )
    # Authentication runs before rate-limited application work when enabled.
    app.add_middleware(BearerAuthMiddleware, token=cfg.api_token)
    # Security headers are outermost and therefore cover success/error paths.
    app.add_middleware(SecurityHeadersMiddleware)
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
