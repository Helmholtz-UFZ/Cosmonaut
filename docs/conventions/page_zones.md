# Page Zones — Multi-Action Editor Layout

Editor pages that mix semantically different actions (filter, per-item edit, network-level algorithm, global undo) read as cluttered when all buttons sit in one `dbc.ButtonGroup`. Split into vertically-stacked zones separated by `html.Hr`, one purpose per zone.

## Rules

- One zone per semantic purpose. Don't cluster buttons that do different *kinds* of things just because they're both buttons.
- Each zone starts with `html.H6(title, className="fw-semibold mb-1 mt-3")` + a one-line `dbc.FormText(..., className="d-block mb-2")` explaining what the zone does. No single top-of-page intro paragraph — users ignore it.
- Separate zones with `html.Hr(className="my-3")`.
- Each primary action button gets its own `html.Div([Button, FormText], className="d-flex flex-column")` so the caption sits directly under the button.
- Avoid `dbc.ButtonGroup` when grouped buttons have different semantic roles — it implies they're variants of the same action.
- Push auxiliary state indicators (selection counters, status badges) to the right of a row with `ms-auto` on the column. Never center just the button row while the rest of the page is left-aligned.
- For zones that change network/graph state, place the *state indicator* **above** the button that changes it. Natural reading flow: state → action → explanation.
- Global undo / reset-all actions belong in a footer-level section with demoted styling (`outline=True, color="secondary", size="sm"`). They are escape hatches, not primary actions.

## Examples

### Do

```python
card_body = [
    html.H6("Filter road types", className="fw-semibold mb-1 mt-2"),
    dbc.FormText("Toggles apply immediately…", className="d-block mb-2"),
    <switches>,

    html.Hr(className="my-3"),

    html.H6("Edit individual roads", className="fw-semibold mb-1"),
    dbc.FormText("Click roads on the map…", className="d-block mb-2"),
    dbc.Row(
        [
            dbc.Col(html.Div([primary_button, caption], className="d-flex flex-column"),
                    width="auto"),
            dbc.Col(badge, className="ms-auto", width="auto"),
        ],
        className="g-3 align-items-center mt-2",
    ),

    html.Hr(className="my-3"),

    html.H6("Network connectivity", className="fw-semibold mb-1 mt-3"),
    state_hint_div,
    html.Div([algorithm_button, caption], className="d-flex flex-column mt-2"),

    html.Hr(className="my-3"),

    # Footer-level global undo
    html.Div(
        [dbc.Button("Reset all edits", outline=True, color="secondary", size="sm"),
         dbc.FormText("Restores everything to the original state.", className="d-block mt-1")],
        className="d-flex flex-column",
    ),
]
```

### Don't

```python
# One ButtonGroup clustering semantically different actions
dbc.ButtonGroup([
    dbc.Button("Remove clicked roads", color="danger"),    # per-item edit
    dbc.Button("Keep largest network", color="primary"),   # network algorithm
    dbc.Button("Reset edits",          color="secondary"), # global undo
])

# Long muted intro at the top
html.P("This page lets you select roads. Click a road to mark it. "
       "Use X to do Y. Use Z for W…", className="text-muted")
```

## Notes

- Reference: `cosmonaut_app/pages/street_selection.py`.
- Compatible with disabled-state rendering: pass `disabled=not is_active` to each button individually. Section headers and microcopy render in all states.
- For the footer action, stick with `outline=True` (not `color="link"`) if the action triggers a confirm modal — it reads as a real button, just a quieter one. `color="link"` conflicts visually with nearby link-style controls (e.g. "Clear all").
