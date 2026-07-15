"""Regression + performance tests for the vectorised pairings algorithm.

The find_pairings algorithm is the only tool with O(N) inner loops, so
we keep:
  - a structural equivalence test (top primaries + bridges are stable
    against accidental algorithmic drift), and
  - a latency budget (a 200 ms ceiling on the 1,790-ingredient bundle
    is well above the current ~5 ms steady-state and will catch any
    accidental re-introduction of per-row Python loops).
"""

from __future__ import annotations

import time
from collections import Counter

import pytest

from epicure_mcp.data_loader import get_bundle
from epicure_mcp.pairings import build_graph
from epicure_mcp.tools import find_pairings

pytestmark = pytest.mark.usefixtures("use_real_bundle")


def _resolve_rows(bundle, names: list[str]) -> tuple[list[int], list[str]]:
    rows: list[int] = []
    resolved: list[str] = []
    for n in names:
        m = bundle.matcher.resolve(n)
        assert m is not None, f"unresolved seed in test fixture: {n}"
        rows.append(bundle.ingredients.nid_to_row[m.node_id])
        resolved.append(m.name)
    return rows, resolved


def test_miso_primaries_stable() -> None:
    """The top primaries for miso are determined entirely by cosine to the
    seed centroid + dietary + category penalty. None of those change unless
    the data bundle changes. The exact eight primaries below were captured
    from the original (pre-vectorisation) implementation."""
    bundle = get_bundle()
    seed_rows, seed_names = _resolve_rows(bundle, ["miso"])
    graph = build_graph(bundle, seed_rows, seed_names)

    primary_names = [p.name for p in graph.primaries]
    expected = {
        "mirin",
        "bonito_flakes",
        "rice_vinegar",
        "udon_noodle",
        "tempura_flour",
        "soybean_oil",
        "vegetarian_oyster_sauce",
        "wakame",
    }
    assert set(primary_names) == expected, f"primaries drifted: {primary_names}"
    # Highest-similarity primary should be mirin (~0.41).
    assert graph.primaries[0].name == "mirin"
    assert graph.primaries[0].similarity_to_center > 0.39


def test_miso_top_bridge_is_garland_chrysanthemum() -> None:
    """The dominant bridge ingredient under miso is garland chrysanthemum
    (appears under most primaries). Acts as a sanity check on the 3-batch
    secondary-node algorithm + the bridge detection rule."""
    bundle = get_bundle()
    seed_rows, seed_names = _resolve_rows(bundle, ["miso"])
    graph = build_graph(bundle, seed_rows, seed_names)

    # Count how many distinct primaries each secondary connects to.
    sec_to_primaries: dict[int, set[int]] = {}
    for link in graph.secondary_links:
        sec_to_primaries.setdefault(link.target_node_id, set()).add(link.source_node_id)
    bridge_counts = Counter({tid: len(srcs) for tid, srcs in sec_to_primaries.items()})
    top_bridge_tid, top_bridge_count = bridge_counts.most_common(1)[0]
    top_bridge_name = next(
        lk.target_name for lk in graph.secondary_links if lk.target_node_id == top_bridge_tid
    )
    assert top_bridge_name == "garland_chrysanthemum"
    assert top_bridge_count >= 4  # appears across at least half of primaries


def test_vegan_filter_excludes_animal_products() -> None:
    """Dietary filter is checked once at the request-filters precompute step
    and should remove all non-vegan ingredients from the graph entirely."""
    bundle = get_bundle()
    seed_rows, seed_names = _resolve_rows(bundle, ["tomato", "basil"])
    graph = build_graph(bundle, seed_rows, seed_names, is_vegan=True)

    all_names = [p.name for p in graph.primaries] + [lk.target_name for lk in graph.secondary_links]
    forbidden = {"beef", "chicken", "pork", "cheese", "butter", "milk", "yogurt"}
    leaked = forbidden & set(all_names)
    assert not leaked, f"vegan filter leaked: {leaked}"


def test_find_pairings_under_200ms_after_warmup() -> None:
    """Regression guard against re-introducing per-row Python loops.

    The current implementation runs in ~5 ms on the 1,790-ingredient
    bundle. We assert a generous 200 ms ceiling so the test is robust to
    CI noise but still catches a 200x regression.
    """
    # Warm up loader + matcher
    find_pairings.run("miso")

    seeds = [
        "miso",
        ["tomato", "basil"],
        "beef",
        ["chicken", "lemon", "thyme"],
    ]
    timings: list[float] = []
    for s in seeds:
        t0 = time.perf_counter()
        out = find_pairings.run(s)
        dt_ms = (time.perf_counter() - t0) * 1000
        assert isinstance(out, str) and out.startswith("Pairing graph for")
        timings.append(dt_ms)

    max_dt = max(timings)
    assert max_dt < 200, (
        f"find_pairings exceeded 200 ms budget; observed timings: "
        f"{[round(t, 1) for t in timings]} ms"
    )
