"""Deterministic ingredient name resolver.

Ported from `eval/matcher.py` in the new-epicure paper branch. The Gemini
embedding fallback (step 6) has been intentionally removed; this resolver
returns ``None`` when steps 1-5 fail.

Resolution order:
    1. Exact match against curated names
    2. Consolidation vocabulary (variant names from the curation pipeline)
    3. Modifier-stripped retry of steps 1-2
    4. Word-boundary substring match
    5. Word-overlap match
"""

from __future__ import annotations

import ast
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MODIFIERS: frozenset[str] = frozenset(
    {
        "ground",
        "fresh",
        "dried",
        "smoked",
        "raw",
        "whole",
        "chopped",
        "minced",
        "sliced",
        "diced",
        "crushed",
        "grated",
        "shredded",
        "frozen",
        "canned",
        "roasted",
        "toasted",
        "blanched",
        "steamed",
        "fried",
        "grilled",
        "baked",
        "boiled",
        "poached",
        "braised",
        "pickled",
        "fermented",
        "unsalted",
        "salted",
        "sweetened",
        "unsweetened",
        "organic",
        "boneless",
        "skinless",
        "lean",
        "light",
        "dark",
        "baby",
        "young",
        "aged",
        "powdered",
        "flaked",
        "dehydrated",
        "concentrated",
        "hot",
        "warm",
        "cold",
        "plain",
        "natural",
        "pure",
        "cooked",
        "uncooked",
        "prepared",
    }
)


@dataclass(frozen=True)
class Match:
    node_id: int
    name: str
    score: float
    method: str


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("_", " ").replace("-", " ")).strip()


def _strip_modifiers(text: str) -> str:
    words = text.split()
    kept = [w for w in words if w not in MODIFIERS]
    return " ".join(kept) if kept else text


class Matcher:
    """Stateful resolver. Loads CSVs once on first use; thread-safe."""

    def __init__(self, ingredient_list_csv: Path, consolidated_nodes_csv: Path) -> None:
        self._ingredient_list_csv = ingredient_list_csv
        self._consolidated_nodes_csv = consolidated_nodes_csv
        self._lock = threading.Lock()
        self._loaded = False
        self._name_to_id: dict[str, int] = {}
        self._id_to_name: dict[int, str] = {}
        self._lookup: dict[str, tuple[int, str]] = {}

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._do_load()
            self._loaded = True

    def _do_load(self) -> None:
        ing_df = pd.read_csv(self._ingredient_list_csv)
        self._name_to_id = {row["name"]: int(row["node_id"]) for _, row in ing_df.iterrows()}
        self._id_to_name = {nid: name for name, nid in self._name_to_id.items()}

        lookup: dict[str, tuple[int, str]] = {}
        for name, nid in self._name_to_id.items():
            lookup[normalize(name)] = (nid, name)

        cons_df = pd.read_csv(self._consolidated_nodes_csv)
        for _, row in cons_df.iterrows():
            nid = int(row["new_node_id"])
            final = row["final_name"]
            raw_names = str(row["original_names_consolidated"])
            try:
                variants = ast.literal_eval(raw_names)
            except (ValueError, SyntaxError):
                variants = [v.strip().strip("'\"") for v in raw_names.strip("[]").split(",")]
            if isinstance(variants, str):
                variants = [variants]
            for v in variants:
                key = normalize(str(v))
                if key and key not in lookup:
                    lookup[key] = (nid, final)
        self._lookup = lookup

    def name_to_id(self) -> dict[str, int]:
        self._ensure_loaded()
        return dict(self._name_to_id)

    def id_to_name(self) -> dict[int, str]:
        self._ensure_loaded()
        return dict(self._id_to_name)

    def _try_lookup(self, query_norm: str, method: str) -> Match | None:
        hit = self._lookup.get(query_norm)
        if hit:
            return Match(node_id=hit[0], name=hit[1], score=1.0, method=method)
        return None

    def _substring(self, query_norm: str) -> Match | None:
        q_words = query_norm.split()
        candidates: list[tuple[str, int, str]] = []
        for key, (nid, name) in self._lookup.items():
            k_words = key.split()
            if len(k_words) >= len(q_words) or not all(w in q_words for w in k_words):
                continue
            leftover = [w for w in q_words if w not in k_words]
            if all(w in MODIFIERS for w in leftover):
                candidates.append((key, nid, name))
        if not candidates:
            return None
        candidates.sort(key=lambda x: -len(x[0].split()))
        _, nid, name = candidates[0]
        return Match(node_id=nid, name=name, score=0.9, method="substring")

    def _word_overlap(self, query_norm: str) -> Match | None:
        q_words = set(query_norm.split())
        best: tuple[float, int | None, str | None] = (0.0, None, None)
        for key, (nid, name) in self._lookup.items():
            k_words = set(key.split())
            common = q_words & k_words
            meaningful = common - MODIFIERS
            if not meaningful:
                continue
            if len(meaningful) < 2 and (len(q_words) > 1 or len(k_words) > 1):
                continue
            ratio = min(len(common) / len(q_words), len(common) / len(k_words))
            if ratio > best[0]:
                best = (ratio, nid, name)
        if best[1] is None or best[2] is None:
            return None
        return Match(node_id=best[1], name=best[2], score=0.75, method="word_overlap")

    def resolve(self, name: str) -> Match | None:
        self._ensure_loaded()
        if not name:
            return None

        q = normalize(name)
        r = self._try_lookup(q, "vocab")
        if r:
            return r

        stripped = _strip_modifiers(q)
        if stripped != q:
            r = self._try_lookup(stripped, "vocab_stripped")
            if r:
                return r

        r = self._substring(q)
        if r:
            return r

        if stripped != q:
            r = self._substring(stripped)
            if r:
                return Match(r.node_id, r.name, r.score, "substring_stripped")

        r = self._word_overlap(q)
        if r:
            return r

        return None
