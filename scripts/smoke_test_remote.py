"""End-to-end smoke test against a running MCP server.

Initialises an MCP session over Streamable HTTP, lists every tool, and
calls one happy-path invocation per tool. Prints a one-line PASS/FAIL
per tool.

Usage:
    python scripts/smoke_test_remote.py https://<aca-fqdn>/mcp
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

SAMPLE_CALLS: list[tuple[str, dict]] = [
    ("list_targets", {}),
    ("flavour_correlations", {}),
    ("neighbors", {"ingredient": "miso", "top_k": 3}),
    ("pairing_score", {"ingredient_a": "miso", "ingredient_b": "soy_sauce"}),
    ("compare_on_axis", {"ingredient_a": "miso", "ingredient_b": "soy_sauce", "axis": "cf_savory"}),
    ("cultural_profile", {"ingredient": "miso"}),
    ("find_pairings", {"ingredients": ["tomato", "basil"], "is_vegan": True}),
    (
        "morph",
        {
            "seed": "rice",
            "target": {"kind": "direction", "name": "South_Asian"},
            "angle_deg": 30,
            "top_k": 3,
        },
    ),
    ("list_factors", {"min_coherence": "high"}),
    ("ingredient_on_factor", {"ingredient": "miso", "factor": 0}),
    ("pareto_navigate", {"seed": "miso", "top_k_poles": 3, "max_frontier": 5}),
    ("closest_mode", {"ingredient": "miso", "top_k": 2}),
    ("where_on_atlas", {"ingredient": "miso"}),
]


async def run(url: str) -> int:
    auth_mode = os.environ.get("MCP_AUTH_MODE", "none").strip().lower() or "none"
    if auth_mode == "none":
        headers = None
    elif auth_mode == "bearer":
        token = os.environ.get("MCP_API_TOKEN", "").strip()
        if not token:
            raise RuntimeError("MCP_API_TOKEN is required when MCP_AUTH_MODE=bearer")
        headers = {"Authorization": f"Bearer {token}"}
    else:
        raise RuntimeError("MCP_AUTH_MODE must be either 'none' or 'bearer'")
    async with streamablehttp_client(url, headers=headers) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            tool_names = {t.name for t in tools}
            print(f"discovered {len(tool_names)} tools: {sorted(tool_names)}")

            # Throttle to stay under a 60 req/min / burst-10 limiter.
            # The MCP handshake already consumed a few tokens; pace ourselves.
            failures: list[str] = []
            for name, args in SAMPLE_CALLS:
                if name not in tool_names:
                    print(f"  MISSING: {name}")
                    failures.append(name)
                    continue
                time.sleep(1.1)  # one call/sec keeps us safe at the default limit
                try:
                    result = await session.call_tool(name, args)
                    if result.isError:
                        text = next(
                            (c.text for c in result.content if hasattr(c, "text")), str(result)
                        )
                        print(f"  ERROR  {name}: {text[:140]}")
                        failures.append(name)
                    else:
                        text = next((c.text for c in result.content if hasattr(c, "text")), "")
                        print(f"  PASS   {name}: {text[:120]}")
                except Exception as e:
                    print(f"  CRASH  {name}: {e}")
                    failures.append(name)

            print()
            if failures:
                print(f"FAIL: {len(failures)} tool(s) failed: {failures}")
                return 1
            print(f"OK: {len(SAMPLE_CALLS)} tool calls succeeded.")
            return 0


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    return asyncio.run(run(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())
