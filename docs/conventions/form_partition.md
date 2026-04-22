# Form Partition — Essential vs Advanced

Dynamically-generated Pydantic forms (via `FormFactory`) often have more fields than a user should see up-front. Hide advanced knobs behind a `dbc.Collapse`, but keep every field rendered so the existing save-to-backend callback still picks them up.

## Rules

- Declare two explicit ordered lists at module top: `ESSENTIAL_FIELDS` and `ADVANCED_FIELDS`. No iterating `Model.model_fields.keys()` directly — explicit order is the point.
- Add a module-level `assert` that the union equals `Model.model_fields.keys()`. Catches silent drift when the upstream Pydantic model gains or loses a field.
- Render **every** field as an `InputField` placeholder. Advanced fields go inside a `dbc.Collapse(is_open=False)` — never omit them, or they won't reach the backend.
- Toggle with a link-styled `dbc.Button` ("Show advanced options ▾ / Hide advanced options ▴") and a small callback that flips `is_open` and the button label in a single update.
- Add HTML ID constants for the toggle button and the Collapse in `html_ids.py` (used in callbacks → no `# nocheck`).

## Examples

### Do

```python
ESSENTIAL_FIELDS = ["segment_number", "time_limit", "max_distance", ...]
ADVANCED_FIELDS  = ["lower_benefit_limit", "max_aco_iteration", ...]

assert set(ESSENTIAL_FIELDS + ADVANCED_FIELDS) == set(
    FullPipelineConfig.model_fields.keys()
), "Field partition drifted from Pydantic model"

card_body = [
    *_build_rows(ESSENTIAL_FIELDS),
    dbc.Button("Show advanced options ▾", id=ADVANCED_TOGGLE_ID, color="link"),
    dbc.Collapse(
        _build_rows(ADVANCED_FIELDS),
        id=ADVANCED_COLLAPSE_ID,
        is_open=False,
    ),
]
```

### Don't

```python
# No drift guard, no prioritization — every field dumped on the user
for field in Model.model_fields:
    body.append(InputField(field))

# Advanced fields omitted — they won't be saved to the backend
body = [InputField(f) for f in ESSENTIAL_FIELDS]
```

## Notes

- `FormFactory.extract_field_names` recurses into component `children`, so InputFields inside a `dbc.Collapse` are discovered and wired into the validation + save callback normally. Visibility is decoupled from callback wiring.
- Known trade-off: if validation fails on an advanced field while the Collapse is closed, the Next button disables with no visible reason. Acceptable first-pass; upgrade path is auto-opening the Collapse on validation failure.
- Reference: `cosmonaut_app/pages/routing_params.py`.
