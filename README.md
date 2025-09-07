# Donizo Pricing Engine

A modular Python engine that transforms messy renovation transcripts into clean, structured pricing quotes in JSON format.  
This repository was developed as part of the **Donizo test assignment**.

---

### Repository Structure

/donizo-pricing-engine/<br>
├── pricing_engine.py # Main orchestrator script<br>
├── pricing_logic/<br>
│ ├── material_db.py # Material lookup and costs<br>
│ ├── labor_calc.py # Labor hours and cost estimation<br>
│ └── vat_rules.py # VAT logic<br>
├── data/<br>
│ ├── materials.json # Default material prices<br>
│ ├── city_modifiers.json # Sample City-based multipliers<br>
│ └── price_templates.csv # Sample price templates<br>
├── output/<br>
│ └── sample_quote.json # Structured quote output<br>
├── tests/<br>
│ └── test_logic.py # Unit tests<br>
├── README.md<br>
└── LICENSE<br>

---

### How to Run

1. Clone the repo:
   ```bash
   git clone https://github.com/<your-username>/donizo-pricing-engine.git
   cd donizo-pricing-engine
   ```
2. Create a virtual environment and install dependencies:
    ```bash
    python -m venv venv
    source venv/bin/activate     # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```
3. Run the pricing engine on an input transcript:
    ```bash
    python pricing_engine.py --input data/example_transcript.txt --output output/sample_quote.json
    ```
4. Run tests:
    ```bash
    pytest -q
    ```

---

### Input → Output

#### Input
A free-text renovation transcript, e.g.:
```
Client wants to renovate a small 4m² bathroom. They'll remove the old tiles, redo the plumbing for the shower, replace the toilet, install a vanity, repaint the walls, and lay new ceramic floor tiles. Budget-conscious. Located in Marseille.
```

#### Output
A structured pricing quote in JSON format. Example (output/sample_quote.json):
```json
{
  "system": "T",
  "quote_id": "donizo-example-0001",
  "client": {
    "raw_transcript": "...",
    "location": "Marseille"
  },
  "currency": "EUR",
  "zones": [
    {
      "zone_name": "bathroom",
      "tasks": [
        {
          "task_name": "Floor Tiling (ceramic)",
          "area_m2": 4.0,
          "labor": {"hours": 3.5, "hourly_rate": 40.0, "cost": 140.00},
          "materials": [{"name": "tiles_ceramic_m2", "qty": 4, "unit_cost": 25.00, "total": 100.00}],
          "estimated_duration_hours": 3.5,
          "vat_rate": 0.20,
          "margin_pct": 0.15,
          "price_ex_vat": 276.00,
          "vat_amount": 55.20,
          "total_price": 331.20,
          "confidence": 0.88
        }
      ]
    }
  ],
  "summary": {
    "total_labor_cost": 780.0,
    "total_material_cost": 580.0,
    "total_vat": 310.76,
    "total_price": 1864.56,
    "estimated_duration_hours": 19.5,
    "confidence_score": 0.85,
    "suspicious_input": false
  }
}
```

---

### Core Logic

1. Parsing<br>
Extracts zones, tasks, quantities (m²), location, and budget flags from raw transcript.
Maps free-text into normalized tasks (e.g. “redo plumbing for the shower” → shower_plumbing).

2. Material Costs (material_db.py)<br>
Loads material prices from materials.json.
Supports city-based modifiers from city_modifiers.json.<br>
Example: `{ "tiles_ceramic_m2": {"unit":"m2","cost":25.0} }`

3. Labor Estimation (labor_calc.py)<br>
Uses deterministic rules:<br>
Tiling: ~0.9 hours/m²<br>
Painting: 1 hr per 10 m²<br>
Plumbing: 4–8 hrs depending on complexity<br>
Applies city-based hourly rate adjustments.<br>

4. VAT Rules (vat_rules.py)<br>
Returns VAT % by task + location.<br>
Default: 20% (configurable).

5. Margin Protection<br>
Default margin: 12–18%<br>
Never drops below a configurable minimum (e.g. 5%).<br>
Discounts only applied if margin remains above threshold.

6. Confidence Score<br>
Per-task confidence combines:<br>
Parsing success<br>
Material/labor DB matches<br>
Location detection<br>
Global confidence = weighted average by cost.<br>
If <0.6 → marks suspicious_input: true.

---

### Tests

Implemented in tests/test_logic.py:
```python
test_material_lookup()

test_estimate_hours()

test_margin_protection()

test_vat_application()

test_end_to_end_sample_transcript()
```

---

### Assumptions & Edge Cases

* System T: Treated as top-level metadata ("system": "T").
* If quantities (e.g., m²) are missing → estimate defaults + lower confidence.
* Budget-conscious → lower margins but never below threshold.
* Unknown city → applies base rates, lower confidence.

---

### Future Plans

* City-based pricing via city_modifiers.json (e.g., Paris = 1.25×).
* Feedback memory: quotes + outcomes logged in data/quote_history.json; margins adjusted incrementally.
* Vectorized memory (future): store embeddings of transcripts in pgvector/Chroma for similarity-based pricing recall.
* Suspicious flags: detect contradictions, unrealistic budgets, or parsing gaps.
* Supplier API integration: replace materials.json with live supplier feeds.
