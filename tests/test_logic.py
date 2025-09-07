"""
tests/test_logic.py

Unit tests for Donizo Pricing Engine.
Covers:
- material_db lookups
- labor_calc estimations
- vat_rules
- full pipeline via pricing_engine.build_quote
"""

import pytest
import json

from pricing_logic import material_db, labor_calc, vat_rules
import pricing_engine


# -----------------------
# Material DB tests
# -----------------------
def test_material_lookup_default():
    cost = material_db.get_material_cost("tiles_ceramic_m2", quantity=4, city="Marseille")
    # 4 m2 * €25 base * 1.0 city multiplier
    assert cost == 100.0

def test_city_modifier_paris():
    cost_generic = material_db.get_material_cost("toilet_standard", 1, city="Marseille")
    cost_paris = material_db.get_material_cost("toilet_standard", 1, city="Paris")
    # Paris has 1.25 multiplier
    assert pytest.approx(cost_paris, rel=1e-2) == cost_generic * 1.25


# -----------------------
# Labor Calc tests
# -----------------------
def test_hourly_rate_city():
    rate_marseille = labor_calc.hourly_rate("Marseille")
    rate_paris = labor_calc.hourly_rate("Paris")
    assert rate_paris > rate_marseille
    assert rate_marseille == 40.0  # base rate

def test_estimate_hours_tiling_area():
    hours = labor_calc.estimate_hours("Floor Tiling", area=4)
    # 0.9 hr per m² → 3.6 → rounded to 3.75
    assert hours == 3.75

def test_compute_labor_cost():
    cost = labor_calc.compute_labor_cost(2, "Marseille")
    assert cost == 80.0


# -----------------------
# VAT Rules tests
# -----------------------
def test_vat_rate_default_and_match():
    rate_default = vat_rules.get_vat_rate("random_task", "Marseille")
    rate_tiling = vat_rules.get_vat_rate("Floor Tiling", "Marseille")
    assert rate_default == 0.20
    assert rate_tiling == 0.20


# -----------------------
# End-to-End pipeline test
# -----------------------
def test_build_quote_sample_transcript(tmp_path):
    transcript = (
        "Client wants to renovate a small 4m² bathroom. "
        "They'll remove the old tiles, redo the plumbing for the shower, "
        "replace the toilet, install a vanity, repaint the walls, "
        "and lay new ceramic floor tiles. Budget-conscious. Located in Marseille."
    )

    quote = pricing_engine.build_quote(transcript)

    # Ensure top-level keys exist
    assert "system" in quote
    assert "zones" in quote
    assert "summary" in quote

    # Check zone & tasks
    assert quote["zones"][0]["zone_name"] == "bathroom"
    tasks = quote["zones"][0]["tasks"]
    assert any(t["task_name"].startswith("Floor Tiling") for t in tasks)
    assert any("Toilet" in t["task_name"] for t in tasks)

    # Check totals consistency
    summary = quote["summary"]
    total_price_sum = sum(t["total_price"] for t in tasks)
    assert pytest.approx(summary["total_price"], rel=1e-2) == total_price_sum

    # Check confidence score
    assert 0.0 <= summary["confidence_score"] <= 1.0

    # Write to file (simulate CLI)
    out_file = tmp_path / "sample_quote.json"
    out_file.write_text(json.dumps(quote, indent=2), encoding="utf-8")
    assert out_file.exists()
