"""In-process port of the Epicure ``/api/graph`` algorithm.

Builds a two-tiered pairing graph for one or more seed ingredients:

1. **Primary nodes**: top-k ingredients by cosine to the seed centroid,
   filtered for dietary compatibility, word-overlap with the seeds, and
   penalised for piling up identical categories (meat/fish, sweet, fat).
2. **Secondary nodes**: top-4 cosine neighbours of each
   ``mean(seeds, primary)`` centroid, with two follow-up batches to
   guarantee per-primary diversity and a globally capped total.
3. **Clusters**: primaries grouped by Jaccard overlap of their secondary
   sets (>=0.1).
4. **Bridges**: secondaries connected to two or more primaries.

The algorithm follows the new-epicure paper-branch implementation
verbatim (``src/api/routes/core/graph_routes.py``) except that the
upstream API's HTTP plumbing and logging are stripped out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .data_loader import Bundle, IngredientData

JACCARD_THRESHOLD = 0.1

_MEAT_CATEGORIES = frozenset({"Meat", "Fish", "Seafood"})
_SWEET_CATEGORIES = frozenset({"Sweet"})
_FAT_CATEGORIES = frozenset({"Fat", "Nuts"})


def _categories_for(ing: IngredientData, node_id: int) -> set[str]:
    """Return the set of category strings for a node, supporting either a
    single primary category or a comma-joined ``categories`` field."""
    primary = ing.primary_category.get(node_id, "")
    if not primary or primary == "Unknown":
        primary = ing.food_group.get(node_id, "Unknown")
    cats = {c.strip() for c in primary.split(",") if c.strip()}
    if not cats:
        cats = {"Unknown"}
    return cats


def _category_penalty(
    candidate_cats: set[str],
    has_meat: bool,
    has_sweet: bool,
    has_fat: bool,
) -> float:
    penalty = 0.0
    if has_meat and (candidate_cats & _MEAT_CATEGORIES):
        penalty += 0.35 if len(candidate_cats) == 1 else 0.15
    if has_sweet and (candidate_cats & _SWEET_CATEGORIES):
        penalty += 0.30 if len(candidate_cats) == 1 else 0.10
    if has_fat and (candidate_cats & _FAT_CATEGORIES):
        penalty += 0.25 if len(candidate_cats) == 1 else 0.12
    return min(penalty, 0.60)


def _has_word_overlap(candidate_name: str, seed_names: list[str]) -> bool:
    candidate_words = set(candidate_name.lower().replace("_", " ").split())
    for seed in seed_names:
        seed_words = set(seed.lower().replace("_", " ").split())
        if candidate_words & seed_words:
            return True
    return False


def _meets_dietary(
    ing: IngredientData,
    node_id: int,
    is_vegan: bool,
    is_vegetarian: bool,
    allergen_free: list[str] | None = None,
) -> bool:
    if not (is_vegan or is_vegetarian) and not allergen_free:
        return True
    if is_vegan and not ing.is_vegan.get(node_id, False):
        return False
    if is_vegetarian and not ing.is_vegetarian.get(node_id, False):
        return False
    if allergen_free:
        for name in allergen_free:
            if ing.allergen_free.get(name, {}).get(node_id, True) is False:
                return False
    return True


@dataclass
class _Primary:
    node_id: int
    row: int
    name: str
    primary_category: str
    similarity_to_center: float


@dataclass
class _SecondaryLink:
    source_node_id: int  # primary node id
    target_node_id: int
    target_name: str
    target_primary_category: str
    similarity: float


@dataclass
class PairingGraph:
    seeds: list[str]
    primaries: list[_Primary]
    secondary_links: list[_SecondaryLink]
    sec_ids_per_primary: dict[int, set[int]]


@dataclass
class _RequestFilters:
    """Per-request filters precomputed once per ``find_pairings`` call.

    Folds dietary, word-overlap, and category-penalty into a single
    per-row score multiplier + a per-row forbidden-mask. The hot
    ``_scored_candidates`` path then becomes:

        scores = (ing.normed @ q) * score_mul
        scores[forbidden | excluded] = -inf
        argsort(-scores)

    which is one matmul + one multiply + one argsort per call. The
    Python-per-row work that used to run on every primary's centroid
    runs once for the whole request.
    """

    n: int
    score_mul: np.ndarray   # (N,) float32 -- (1 - category_penalty)
    forbidden: np.ndarray   # (N,) bool   -- True == always disallow


def _build_request_filters(
    ing: IngredientData,
    seed_names: list[str],
    is_vegan: bool,
    is_vegetarian: bool,
    has_meat: bool,
    has_sweet: bool,
    has_fat: bool,
    allergen_free: list[str] | None = None,
) -> _RequestFilters:
    n = ing.normed.shape[0]
    score_mul = np.ones(n, dtype=np.float32)
    forbidden = np.zeros(n, dtype=bool)

    # Pre-tokenise seed words once.
    seed_words: set[str] = set()
    for s in seed_names:
        seed_words.update(s.lower().replace("_", " ").split())

    dietary_active = is_vegan or is_vegetarian
    flags_map = ing.is_vegan if is_vegan else ing.is_vegetarian
    penalties_active = has_meat or has_sweet or has_fat
    allergen_active = bool(allergen_free)

    for i in range(n):
        node_id = int(ing.node_ids[i])
        if dietary_active and not flags_map.get(node_id, False):
            forbidden[i] = True
            continue
        if allergen_active:
            for name in allergen_free:  # type: ignore[union-attr]
                if ing.allergen_free.get(name, {}).get(node_id, True) is False:
                    forbidden[i] = True
                    break
            if forbidden[i]:
                continue
        if seed_words:
            cand_words = set(str(ing.names[i]).lower().replace("_", " ").split())
            if cand_words & seed_words:
                forbidden[i] = True
                continue
        if penalties_active:
            cats = _categories_for(ing, node_id)
            penalty = _category_penalty(cats, has_meat, has_sweet, has_fat)
            if penalty > 0:
                score_mul[i] = 1.0 - penalty

    return _RequestFilters(n=n, score_mul=score_mul, forbidden=forbidden)


def _scored_candidates(
    ing: IngredientData,
    query_vec: np.ndarray,
    excluded_rows: set[int],
    filters: _RequestFilters,
    top_k: int = 0,
) -> list[tuple[int, float]]:
    """Vectorised candidate scoring.

    Returns ``(row, penalised_similarity)`` for at most ``top_k`` eligible
    rows in descending-score order. ``top_k=0`` returns every eligible row.
    Eligible = not in ``excluded_rows`` and not in the precomputed
    ``forbidden`` mask. Score = ``cosine(query, row) * (1 - penalty)``.
    """
    norm = float(np.linalg.norm(query_vec))
    q = (query_vec / norm if norm > 0 else query_vec).astype(np.float32)
    sims = ing.normed @ q
    scores = sims * filters.score_mul
    scores = np.where(filters.forbidden, -np.inf, scores)
    if excluded_rows:
        excluded_idx = np.fromiter(
            excluded_rows, dtype=np.int64, count=len(excluded_rows)
        )
        scores[excluded_idx] = -np.inf

    if top_k > 0:
        k = min(top_k, filters.n)
        # argpartition is O(N) for the partial top-k; argsort within the
        # k-element slice is then negligible.
        part = np.argpartition(-scores, k - 1)[:k]
        ordered = part[np.argsort(-scores[part])]
    else:
        ordered = np.argsort(-scores)

    out: list[tuple[int, float]] = []
    for idx in ordered:
        s = float(scores[idx])
        if s == float("-inf"):
            break
        out.append((int(idx), s))
    return out


def build_graph(
    bundle: Bundle,
    seed_rows: list[int],
    seed_names: list[str],
    *,
    is_vegan: bool = False,
    is_vegetarian: bool = False,
    allergen_free: list[str] | None = None,
    max_primary_nodes: int = 8,
    max_secondary_nodes: int = 8,
) -> PairingGraph:
    """Pure-numpy port of the ``/api/graph`` algorithm.

    ``seed_rows`` are row indices into ``bundle.ingredients.normed``;
    ``seed_names`` are the resolved canonical names in the same order.
    """
    ing = bundle.ingredients

    seed_categories: set[str] = set()
    for r in seed_rows:
        seed_categories |= _categories_for(ing, int(ing.node_ids[r]))
    has_meat = bool(seed_categories & _MEAT_CATEGORIES)
    has_sweet = bool(seed_categories & _SWEET_CATEGORIES)
    has_fat = bool(seed_categories & _FAT_CATEGORIES)

    # One vocabulary-wide pass; reused for every centroid below.
    filters = _build_request_filters(
        ing, seed_names, is_vegan, is_vegetarian, has_meat, has_sweet, has_fat,
        allergen_free=allergen_free,
    )

    seed_vecs = ing.normed[seed_rows]
    combined_seed = seed_vecs.mean(axis=0)

    seed_set = set(seed_rows)
    # Primary node selection: we only ever keep up to ``max_primary_nodes``,
    # so cap the candidate list there + a generous safety margin in case
    # some top scorers tie at -inf.
    primary_scored = _scored_candidates(
        ing, combined_seed, seed_set, filters, top_k=max_primary_nodes * 3,
    )

    primaries: list[_Primary] = []
    for row, sim in primary_scored:
        if len(primaries) >= max_primary_nodes:
            break
        node_id = int(ing.node_ids[row])
        name = str(ing.names[row])
        primaries.append(
            _Primary(
                node_id=node_id,
                row=row,
                name=name,
                primary_category=ing.primary_category.get(node_id, "Unknown"),
                similarity_to_center=sim,
            )
        )

    excluded_for_secondaries = seed_set | {p.row for p in primaries}

    secondary_links: list[_SecondaryLink] = []
    sec_ids_per_primary: dict[int, set[int]] = {p.node_id: set() for p in primaries}
    chosen_secondary_rows: set[int] = set()

    def _record(primary: _Primary, target_row: int, similarity: float) -> None:
        target_nid = int(ing.node_ids[target_row])
        secondary_links.append(
            _SecondaryLink(
                source_node_id=primary.node_id,
                target_node_id=target_nid,
                target_name=str(ing.names[target_row]),
                target_primary_category=ing.primary_category.get(target_nid, "Unknown"),
                similarity=similarity,
            )
        )
        sec_ids_per_primary[primary.node_id].add(target_nid)
        chosen_secondary_rows.add(target_row)

    def _scored_for_primary(
        primary: _Primary, exclude_rows: set[int], top_k: int = 16,
    ) -> list[tuple[int, float]]:
        centroid = np.vstack(
            [seed_vecs, ing.normed[primary.row : primary.row + 1]]
        ).mean(axis=0)
        return _scored_candidates(ing, centroid, exclude_rows, filters, top_k=top_k)

    # Batch 1: top-4 per primary (shared targets allowed).
    for p in primaries:
        for row, sim in _scored_for_primary(p, excluded_for_secondaries, top_k=4):
            _record(p, row, sim)

    # Batch 2: top up each primary to 4 unique connections.
    for p in primaries:
        already_connected = {
            link.target_node_id for link in secondary_links if link.source_node_id == p.node_id
        }
        # Number of unique-to-this-primary connections so far.
        shared_count = 0
        for nid in already_connected:
            sources = {
                lk.source_node_id for lk in secondary_links if lk.target_node_id == nid
            }
            if len(sources) > 1:
                shared_count += 1
        unique_needed = max(0, 4 - shared_count)
        if unique_needed == 0:
            continue
        candidates = _scored_for_primary(
            p,
            excluded_for_secondaries
            | {
                ing.nid_to_row[link.target_node_id]
                for link in secondary_links
                if link.source_node_id == p.node_id
            },
            top_k=unique_needed,
        )
        added = 0
        for row, sim in candidates:
            if added >= unique_needed:
                break
            _record(p, row, sim)
            added += 1

    # Batch 3: global fill until we hit max_secondary_nodes unique targets.
    while len(chosen_secondary_rows) < max_secondary_nodes and primaries:
        # Primary with fewest connections gets the next slot.
        primary_to_extend = min(
            primaries,
            key=lambda p: sum(
                1 for link in secondary_links if link.source_node_id == p.node_id
            ),
        )
        candidates = _scored_for_primary(
            primary_to_extend,
            excluded_for_secondaries | chosen_secondary_rows,
            top_k=1,
        )
        if not candidates:
            break
        row, sim = candidates[0]
        _record(primary_to_extend, row, sim)

    return PairingGraph(
        seeds=seed_names,
        primaries=primaries,
        secondary_links=secondary_links,
        sec_ids_per_primary=sec_ids_per_primary,
    )


def _format_name(name: str) -> str:
    return name.replace("_", " ")


def format_graph_text(graph: PairingGraph, pairing_stats: dict[str, float]) -> str:
    """Render the prototype's text layout (CLUSTERS / CONNECTIONS / BRIDGES)."""
    lines: list[str] = [
        f"Pairing graph for: {', '.join(_format_name(s) for s in graph.seeds)}",
        (
            f"(reference scores: p10={pairing_stats['p10']:.2f}, "
            f"median={pairing_stats['median']:.2f}, "
            f"p90={pairing_stats['p90']:.2f})"
        ),
        "",
    ]

    clusters: list[list[_Primary]] = []
    assigned: set[int] = set()
    for p in graph.primaries:
        if p.node_id in assigned:
            continue
        cluster = [p]
        assigned.add(p.node_id)
        for q in graph.primaries:
            if q.node_id in assigned:
                continue
            sp = graph.sec_ids_per_primary.get(p.node_id, set())
            sq = graph.sec_ids_per_primary.get(q.node_id, set())
            union = sp | sq
            jaccard = len(sp & sq) / len(union) if union else 0.0
            if jaccard >= JACCARD_THRESHOLD:
                cluster.append(q)
                assigned.add(q.node_id)
        clusters.append(cluster)

    lines.append("CLUSTERS (primaries grouped by shared secondary connections):")
    for i, cluster in enumerate(clusters):
        cats = [p.primary_category for p in cluster]
        # Stable tie-break: highest count wins, lexicographic name breaks ties.
        # (Plain ``max(set(cats), key=cats.count)`` is non-deterministic because
        # set iteration order depends on Python hash randomisation.)
        dominant = (
            max(sorted(set(cats)), key=cats.count) if cats else "Unknown"
        )
        density = "dense" if len(cluster) > 1 else "isolated"
        members = ", ".join(
            f"{_format_name(p.name)} ({p.similarity_to_center:.3f})" for p in cluster
        )
        label = chr(ord("A") + i)
        plural = "s" if len(cluster) != 1 else ""
        lines.append(
            f"  {label} [{dominant} - {len(cluster)} node{plural}, {density}]: {members}"
        )

    if len(clusters) > 1:
        all_pairs_isolated = all(
            not (
                graph.sec_ids_per_primary.get(p.node_id, set())
                & graph.sec_ids_per_primary.get(q.node_id, set())
            )
            for ci, c1 in enumerate(clusters)
            for cj, c2 in enumerate(clusters)
            if ci < cj
            for p in c1
            for q in c2
        )
        if all_pairs_isolated:
            lines.append(
                "  -> Clusters share 0 secondaries - completely different flavor directions."
            )
    lines.append("")

    sec_links_per_primary: dict[int, list[_SecondaryLink]] = {
        p.node_id: [] for p in graph.primaries
    }
    for link in graph.secondary_links:
        sec_links_per_primary.setdefault(link.source_node_id, []).append(link)
    for pid in sec_links_per_primary:
        sec_links_per_primary[pid].sort(key=lambda lk: -lk.similarity)

    lines.append("CONNECTIONS (each primary -> its secondaries):")
    for p in graph.primaries:
        secs = sec_links_per_primary.get(p.node_id, [])
        sec_strs = [f"{_format_name(lk.target_name)} {lk.similarity:.2f}" for lk in secs]
        lines.append(f"  {_format_name(p.name)}: {', '.join(sec_strs)}")
    lines.append("")

    sec_to_primaries: dict[int, list[str]] = {}
    primary_name_by_id = {p.node_id: p.name for p in graph.primaries}
    for link in graph.secondary_links:
        sec_to_primaries.setdefault(link.target_node_id, []).append(
            primary_name_by_id.get(link.source_node_id, "?")
        )
    bridges = [
        (tid, pnames)
        for tid, pnames in sec_to_primaries.items()
        if len(set(pnames)) >= 2
    ]
    bridges.sort(key=lambda x: -len(set(x[1])))

    if bridges:
        lines.append("BRIDGES (secondaries connecting multiple primaries):")
        target_name_by_id = {lk.target_node_id: lk.target_name for lk in graph.secondary_links}
        n_primaries = len(graph.primaries)
        for tid, pnames in bridges:
            uniq = list(dict.fromkeys(pnames))
            lines.append(
                f"  {_format_name(target_name_by_id[tid])} -> "
                f"{', '.join(_format_name(n) for n in uniq)} "
                f"({len(uniq)} of {n_primaries} primaries)"
            )
    return "\n".join(lines)


def find_pairings(
    bundle: Bundle,
    ingredients: list[str],
    *,
    is_vegan: bool = False,
    is_vegetarian: bool = False,
    allergen_free: list[str] | None = None,
    max_primary_nodes: int = 8,
    max_secondary_nodes: int = 8,
) -> dict[str, Any]:
    """Entry point used by the MCP tool.

    Returns a dict with either ``error`` or ``resolved`` + ``text``.
    """
    resolved_rows: list[int] = []
    resolved_names: list[str] = []
    unresolved: list[str] = []
    for raw in ingredients:
        m = bundle.matcher.resolve(raw)
        if m is None:
            unresolved.append(raw)
            continue
        resolved_rows.append(bundle.ingredients.nid_to_row[m.node_id])
        resolved_names.append(m.name)
    if not resolved_rows:
        return {"error": f"Could not resolve any ingredients: {ingredients}"}

    graph = build_graph(
        bundle,
        resolved_rows,
        resolved_names,
        is_vegan=is_vegan,
        is_vegetarian=is_vegetarian,
        allergen_free=allergen_free,
        max_primary_nodes=max_primary_nodes,
        max_secondary_nodes=max_secondary_nodes,
    )
    text = format_graph_text(graph, bundle.pairing_stats)
    return {
        "resolved": resolved_names,
        "unresolved": unresolved,
        "text": text,
    }
