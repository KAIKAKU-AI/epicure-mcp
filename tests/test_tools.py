"""Tool happy-path + error-case smoke tests against the real bundle."""

from __future__ import annotations

import json

import pytest

from epicure_mcp.tools import (
    closest_mode,
    compare_on_axis,
    cultural_profile,
    find_pairings,
    flavour_correlations,
    ingredient_on_factor,
    list_factors,
    list_targets,
    morph,
    neighbors,
    pairing_score,
    pareto_navigate,
    where_on_atlas,
)

pytestmark = pytest.mark.usefixtures("use_real_bundle")


# -------- compare_on_axis -------------------------------------------------


def test_compare_on_axis_ok() -> None:
    out = compare_on_axis.run("miso", "soy_sauce", "cf_savory")
    assert "error" not in out
    assert out["resolved_a"] == "miso"
    assert out["resolved_b"] == "soy_sauce"
    assert isinstance(out["delta"], float)


def test_compare_on_axis_bad_axis() -> None:
    out = compare_on_axis.run("miso", "soy_sauce", "not_real_axis")
    assert "error" in out


def test_compare_on_axis_bad_ingredient() -> None:
    out = compare_on_axis.run("zzz_unknown", "soy_sauce", "cf_savory")
    assert "error" in out


# -------- pairing_score ---------------------------------------------------


def test_pairing_score_ok() -> None:
    out = pairing_score.run("miso", "soy_sauce")
    assert "error" not in out
    assert -1.0 <= out["pairing_score"] <= 1.0


def test_pairing_score_bad() -> None:
    out = pairing_score.run("zzz_unknown", "soy_sauce")
    assert "error" in out


# -------- neighbors -------------------------------------------------------


def test_neighbors_ok() -> None:
    out = neighbors.run("miso", top_k=3)
    assert "error" not in out
    assert len(out["neighbors"]) == 3
    assert out["neighbors"][0]["rank"] == 1


def test_neighbors_bad() -> None:
    out = neighbors.run("zzz_unknown", top_k=3)
    assert "error" in out


# -------- flavour_correlations --------------------------------------------


def test_flavour_correlations() -> None:
    out = flavour_correlations.run()
    assert "notable_correlations" in out
    assert out["n_axes"] > 0
    assert out["returned"] <= 30
    assert out["truncated"] == (out["total_matches"] > out["returned"])


# -------- cultural_profile ------------------------------------------------


def test_cultural_profile_ok() -> None:
    out = cultural_profile.run("miso")
    assert "error" not in out
    assert "cuisines" in out
    assert "Japanese" in out["cuisines"]


def test_cultural_profile_bad() -> None:
    out = cultural_profile.run("zzz_unknown")
    assert "error" in out


# -------- morph -----------------------------------------------------------


def test_morph_direction() -> None:
    out = morph.run(
        seed="rice",
        target={"kind": "direction", "name": "South_Asian"},
        angle_deg=30,
        top_k=3,
    )
    assert "error" not in out
    assert out["resolved_target"] == "direction:South_Asian"
    assert len(out["neighbors"]) == 3


def test_morph_mode() -> None:
    out = morph.run(
        seed="miso",
        target={"kind": "mode", "property": "cf_savory", "mode_id": 0},
        angle_deg=30,
        top_k=3,
    )
    assert "error" not in out
    assert out["resolved_target"].startswith("mode:cf_savory/")


def test_morph_ingredient() -> None:
    out = morph.run(
        seed="rice",
        target={"kind": "ingredient", "name": "saffron"},
        angle_deg=30,
        top_k=3,
    )
    assert "error" not in out
    assert out["resolved_target"].startswith("ingredient:")


def test_morph_bad_target_kind() -> None:
    out = morph.run(seed="rice", target={"kind": "garbage"}, angle_deg=30, top_k=3)
    assert "error" in out


# -------- list_targets ----------------------------------------------------


def test_list_targets_default_page() -> None:
    out = list_targets.run()
    assert out["summary"]["n_directions"] > 0
    assert out["summary"]["n_modes"] == 0
    assert out["summary"]["limit"] == 25
    assert len(out["directions"]) <= 25
    assert "angle_deg_primer" in out


def test_list_targets_filtered() -> None:
    out = list_targets.run(kind="mode", limit=10)
    assert out["summary"]["n_directions"] == 0
    assert out["summary"]["n_modes"] > 0
    assert len(out["modes"]) == 10


# -------- list_factors / ingredient_on_factor -----------------------------


def test_list_factors() -> None:
    out = list_factors.run(min_coherence="low")
    assert out["n"] == 20
    assert len(out["factors"]) > 0
    assert "top_ingredients" not in out["factors"][0]["pole_a"]
    assert "notes" not in out["factors"][0]["axis"]


def test_list_factors_examples_are_opt_in() -> None:
    out = list_factors.run(min_coherence="high", include_examples=True)
    assert out["factors"]
    assert "top_ingredients" in out["factors"][0]["pole_a"]
    assert "description" in out["factors"][0]["axis"]


def test_default_catalogues_are_compact() -> None:
    payloads = (
        flavour_correlations.run(),
        list_targets.run(),
        list_factors.run(),
    )
    assert all(len(json.dumps(payload).encode("utf-8")) < 20_000 for payload in payloads)


def test_ingredient_on_factor_ok() -> None:
    out = ingredient_on_factor.run("miso", 0)
    assert "error" not in out
    assert -1.0 <= out["projection"] <= 1.0


def test_ingredient_on_factor_bad_index() -> None:
    out = ingredient_on_factor.run("miso", 999)
    assert "error" in out


# -------- pareto_navigate -------------------------------------------------


def test_pareto_navigate_auto() -> None:
    out = pareto_navigate.run(seed="miso", top_k_poles=3, max_frontier=10)
    assert "error" not in out
    assert len(out["poles"]) <= 3


def test_pareto_navigate_explicit_pole() -> None:
    out = pareto_navigate.run(seed="miso", pole={"factor": 0, "side": "a"}, max_frontier=5)
    assert "error" not in out
    assert len(out["poles"]) == 1


def test_pareto_navigate_bad_seed() -> None:
    out = pareto_navigate.run(seed="zzz_unknown")
    assert "error" in out


# -------- closest_mode ----------------------------------------------------


def test_closest_mode_ok() -> None:
    out = closest_mode.run("miso", top_k=3)
    assert "error" not in out
    assert len(out["modes"]) == 3


def test_closest_mode_filtered() -> None:
    out = closest_mode.run("miso", property="cf_savory", top_k=2)
    assert "error" not in out
    for m in out["modes"]:
        assert m["property"] == "cf_savory"


# -------- where_on_atlas --------------------------------------------------


def test_where_on_atlas_ok() -> None:
    out = where_on_atlas.run("miso")
    assert "error" not in out
    assert len(out["atlas_xy"]) == 2
    assert len(out["neighbors_in_2d"]) == 5


def test_where_on_atlas_bad() -> None:
    out = where_on_atlas.run("zzz_unknown")
    assert "error" in out


# -------- find_pairings ---------------------------------------------------


def test_find_pairings_single_seed() -> None:
    out = find_pairings.run("miso")
    assert isinstance(out, str)
    assert out.lower().startswith("pairing graph for")
    assert "CLUSTERS" in out
    assert "CONNECTIONS" in out


def test_find_pairings_multi_seed_vegan() -> None:
    out = find_pairings.run(["tomato", "basil"], is_vegan=True)
    assert isinstance(out, str)
    assert "Pairing graph for: tomato, basil" in out
    # Vegan filter should keep meat/dairy out of the secondary text.
    lowered = out.lower()
    assert "beef" not in lowered
    assert "cheese" not in lowered


def test_find_pairings_unresolvable() -> None:
    out = find_pairings.run(["zzz_unknown_xyz"])
    assert isinstance(out, str)
    assert out.lower().startswith("error")
