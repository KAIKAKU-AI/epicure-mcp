"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent
_DEFAULT_DATA_DIR = _PACKAGE_ROOT.parent.parent / "data"


@dataclass(frozen=True)
class Config:
    data_dir: Path
    host: str
    port: int
    rate_limit_per_minute: int
    rate_limit_burst: int
    server_name: str
    api_token: str | None = None
    allowed_hosts: tuple[str, ...] = ()
    allowed_origins: tuple[str, ...] = ()

    @property
    def embeddings_csv(self) -> Path:
        return self.data_dir / "embeddings.csv"

    @property
    def ingredient_list_csv(self) -> Path:
        return self.data_dir / "ingredient_list.csv"

    @property
    def ingredient_tags_csv(self) -> Path:
        return self.data_dir / "ingredient_tags.csv"

    @property
    def consolidated_nodes_csv(self) -> Path:
        return self.data_dir / "consolidated_nodes.csv"

    @property
    def supervised_directions_npz(self) -> Path:
        return self.data_dir / "supervised_directions.npz"

    @property
    def factor_dirs_npy(self) -> Path:
        return self.data_dir / "factor_dirs_ica_n20.npy"

    @property
    def factor_labels_json(self) -> Path:
        return self.data_dir / "factor_labels_ica_cooc.json"

    @property
    def mode_explorer_json(self) -> Path:
        return self.data_dir / "mode_explorer_cooc.json"

    @property
    def mode_poles_npy(self) -> Path:
        return self.data_dir / "mode_poles_cooc.npy"

    @property
    def umap_coords_csv(self) -> Path:
        return self.data_dir / "umap_coords.csv"

    @property
    def umap_coords_3d_csv(self) -> Path:
        return self.data_dir / "umap_coords_3d.csv"


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    return int(raw) if raw else default


def _env_csv(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(key)
    if not raw:
        return default
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def load_config() -> Config:
    return Config(
        data_dir=Path(os.environ.get("EPICURE_DATA_DIR", str(_DEFAULT_DATA_DIR))),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=_env_int("PORT", 8080),
        rate_limit_per_minute=_env_int("RATE_LIMIT_PER_MINUTE", 60),
        rate_limit_burst=_env_int("RATE_LIMIT_BURST", 10),
        server_name=os.environ.get("MCP_SERVER_NAME", "Epicure"),
        api_token=os.environ.get("MCP_API_TOKEN") or None,
        allowed_hosts=_env_csv(
            "MCP_ALLOWED_HOSTS",
            (
                "epicure-mcp.kaikaku.ai",
                "epicure-mcp.kaikaku.ai:*",
                "localhost",
                "localhost:*",
                "127.0.0.1",
                "127.0.0.1:*",
                "mcp",
                "mcp:*",
            ),
        ),
        allowed_origins=_env_csv(
            "MCP_ALLOWED_ORIGINS",
            (
                "https://claude.ai",
                "https://www.claude.ai",
                "https://claude.com",
                "https://www.claude.com",
                # Cursor IDE / Marketplace HTTP MCP clients (browser webviews).
                "https://cursor.com",
                "https://www.cursor.com",
                "https://cursor.sh",
                "https://www.cursor.sh",
                "https://epicure.kaikaku.ai",
                "http://localhost:*",
                "http://127.0.0.1:*",
            ),
        ),
    )
