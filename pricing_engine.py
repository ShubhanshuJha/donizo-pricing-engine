import argparse
import json
import re
import uuid
from pathlib import Path

# Import modular logic
from pricing_logic.material_db import get_material_cost
from pricing_logic.labor_calc import estimate_hours, compute_labor_cost, hourly_rate
from pricing_logic.vat_rules import get_vat_rate


# -----------------------------
# Utility functions
# -----------------------------
def generate_quote_id():
    return f"donizo-{uuid.uuid4().hex[:8]}"


def parse_transcript(text):
    """
    Very simple rule-based parser for the Donizo test case.
    Extracts: zone, area, tasks, city, budget-conscious flag.
    """

    zone = "bathroom" if "bathroom" in text.lower() else "general"

    # Area in m2
    area_match = re.search(r"(\d+)\s?m[²2]", text.lower())
    area_m2 = float(area_match.group(1)) if area_match else None

    # City (simplified)
    city_match = re.search(r"(marseille|paris|lyon)", text.lower())
    city = city_match.group(1).capitalize() if city_match else None

    budget_flag = "budget" in text.lower()

    # Tasks (rule-based)
    tasks = []
    if "tile" in text.lower():
        tasks.append({"task_name": "Floor Tiling (ceramic)", "area_m2": area_m2})
    if "paint" in text.lower() or "repaint" in text.lower():
        tasks.append({"task_name": "Repaint Walls"})
    if "plumb" in text.lower():
        tasks.append({"task_name": "Shower Plumbing (redo)"})
    if "toilet" in text.lower():
        tasks.append({"task_name": "Replace Toilet"})
    if "vanity" in text.lower():
        tasks.append({"task_name": "Install Vanity"})
    if "remove old tile" in text.lower() or "remove the old tiles" in text.lower():
        tasks.append({"task_name": "Demolition & Disposal"})

    return {
        "zone": zone,
        "city": city,
        "budget_flag": budget_flag,
        "tasks": tasks,
        "area_m2": area_m2,
    }


def apply_margin_protection(base_price, default_margin=0.12, min_margin=0.05):
    margin_pct = max(default_margin, min_margin)
    margin_amount = base_price * margin_pct
    return margin_pct, margin_amount


def compute_confidence(task, city):
    score = 0.0
    # parsing confidence
    score += 0.4 if task.get("task_name") else 0.0
    # area presence
    score += 0.2 if task.get("area_m2") or "area_m2" not in task else 0.0
    # city confidence
    score += 0.2 if city else 0.1
    # assume db match always valid here
    score += 0.2
    return min(score, 1.0)


# -----------------------------
# Core Engine
# -----------------------------
def build_quote(transcript_text):
    parsed = parse_transcript(transcript_text)

    city = parsed["city"] or "Generic"
    zone_name = parsed["zone"]

    hourly = hourly_rate(city)

    tasks_out = []
    total_labor_cost = 0.0
    total_material_cost = 0.0
    total_vat = 0.0
    total_price = 0.0
    total_hours = 0.0
    weighted_conf_sum = 0.0
    weighted_cost_sum = 0.0

    for task in parsed["tasks"]:
        tname = task["task_name"]

        # --- Estimate labor
        hours = estimate_hours(tname, area=task.get("area_m2"))
        labor_cost = compute_labor_cost(hours, city)

        # --- Materials (very simplified demo)
        materials = []
        mat_cost = 0.0
        if "Tile" in tname:
            qty = task.get("area_m2", 4)
            cost = get_material_cost("tiles_ceramic_m2", qty, city)
            materials.append(
                {"name": "tiles_ceramic_m2", "qty": qty, "unit_cost": cost / qty, "total": cost}
            )
            mat_cost += cost
        elif "Paint" in tname:
            qty = 5
            cost = get_material_cost("paint_litre", qty, city)
            materials.append({"name": "paint_litre", "qty": qty, "unit_cost": cost / qty, "total": cost})
            mat_cost += cost
        elif "Plumbing" in tname:
            cost = get_material_cost("plumbing_parts", 1, city)
            materials.append({"name": "plumbing_parts", "qty": 1, "unit_cost": cost, "total": cost})
            mat_cost += cost
        elif "Toilet" in tname:
            cost = get_material_cost("toilet_standard", 1, city)
            materials.append({"name": "toilet_standard", "qty": 1, "unit_cost": cost, "total": cost})
            mat_cost += cost
        elif "Vanity" in tname:
            cost = get_material_cost("vanity_basic", 1, city)
            materials.append({"name": "vanity_basic", "qty": 1, "unit_cost": cost, "total": cost})
            mat_cost += cost
        elif "Demolition" in tname:
            cost = get_material_cost("disposal_fee", 1, city)
            materials.append({"name": "disposal_fee", "qty": 1, "unit_cost": cost, "total": cost})
            mat_cost += cost

        base_price = labor_cost + mat_cost

        margin_pct, margin_amount = apply_margin_protection(base_price, default_margin=0.12)
        price_ex_vat = base_price + margin_amount

        vat_rate = get_vat_rate(tname, city)
        vat_amount = price_ex_vat * vat_rate
        total_task_price = price_ex_vat + vat_amount

        confidence = compute_confidence(task, city)

        tasks_out.append(
            {
                "task_name": tname,
                "area_m2": task.get("area_m2"),
                "labor": {"hours": hours, "hourly_rate": hourly, "cost": labor_cost},
                "materials": materials,
                "estimated_duration_hours": hours,
                "vat_rate": vat_rate,
                "margin_pct": margin_pct,
                "price_ex_vat": round(price_ex_vat, 2),
                "vat_amount": round(vat_amount, 2),
                "total_price": round(total_task_price, 2),
                "confidence": round(confidence, 2),
            }
        )

        # accumulate totals
        total_labor_cost += labor_cost
        total_material_cost += mat_cost
        total_vat += vat_amount
        total_price += total_task_price
        total_hours += hours
        weighted_conf_sum += confidence * total_task_price
        weighted_cost_sum += total_task_price

    global_conf = weighted_conf_sum / weighted_cost_sum if weighted_cost_sum else 0.0

    out_json = {
        "system": "T",
        "quote_id": generate_quote_id(),
        "client": {"raw_transcript": transcript_text, "location": city},
        "currency": "EUR",
        "zones": [{"zone_name": zone_name, "tasks": tasks_out}],
        "summary": {
            "total_labor_cost": round(total_labor_cost, 2),
            "total_material_cost": round(total_material_cost, 2),
            "total_vat": round(total_vat, 2),
            "total_price": round(total_price, 2),
            "estimated_duration_hours": round(total_hours, 2),
            "confidence_score": round(global_conf, 2),
            "suspicious_input": global_conf < 0.6,
        },
    }
    return out_json


# -----------------------------
# CLI Based Input
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="Donizo Pricing Engine")
    parser.add_argument("--input", type=str, required=True, help="Path to transcript .txt")
    parser.add_argument("--output", type=str, required=True, help="Path to output JSON file")
    args = parser.parse_args()

    transcript_text = Path(args.input).read_text(encoding="utf-8")

    quote = build_quote(transcript_text)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(quote, indent=2), encoding="utf-8")

    print(f"✅ Quote generated at {out_path}")


if __name__ == "__main__":
    main()
