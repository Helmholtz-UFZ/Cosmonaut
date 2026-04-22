# Plan: Routing Parameters — Essential / Advanced Reorg

**Created:** 2026-04-22
**Context:** The Parameters step currently renders all 16 fields of `FullPipelineConfig` flat. Louis wants a minimal essential set up top and everything else tucked behind a "Show advanced options" toggle.

---

## Background

`cosmonaut_app/pages/routing_params.py` builds `card_body_with_placeholder` by iterating `FullPipelineConfig.model_fields.keys()` two-per-row. This dumps every field on the user — most of which are tuning knobs they shouldn't touch.

The sensor-routing backend (`Can's code`) will also be reworked, but **earliest in May**. Until then, every parameter must still flow through the existing save path: `update_routing_params` callback → `setattr(job.model, key, value)` → `job.save()`. That means **every field must still be rendered as an `InputField`** so `FormFactory` picks it up via `extract_field_names` and wires it into `produce_callback_inputs()`/`produce_callback_outputs()`. We only change *visibility*, not the component tree's membership.

## Design decisions

- **UI pattern:** `dbc.Collapse` toggled by a link-styled `dbc.Button` ("Show advanced options ▾" / "Hide advanced options ▴"). Cleaner than `dbc.Accordion` — one lightweight toggle, no box-in-box chrome. Lives below the essential fields, above the footer.
- **Objective handling:** Time Limit, Max distance, and Objective all stay in essentials. Objective remains the existing free-text field (d/t/i). We add a static helper caption under it explaining that objective decides which of the two limits the backend actually uses. No dynamic highlight/dimming — Can's May update will handle that properly.
- **`working_directory`:** goes in advanced (it's a filesystem path — not user-facing, but the backend still needs it saved). Do **not** remove or hide entirely; keep wired.
- **`num_points`:** stays in essentials (user-facing "how many stops?"; other HPE knobs go advanced).
- **No FormFactory changes.** All logic lives in `routing_params.py` plus HTML ID constants and one small toggle callback.

## Field partition

**Essential (visible by default, in this order):**
1. `segment_number` — "Segments per class"
2. `time_limit` — "Time limit [h]"
3. `max_distance` — "Max distance"
4. `optimization_objective` — "Objective" + static helper caption
5. `num_points` — "Number of points"

**Advanced (inside `dbc.Collapse`, collapsed by default):**
- `lower_benefit_limit`
- `max_aco_iteration`
- `ant_no`
- `is_reversed`
- `working_directory`
- `benefit_type`
- `route_type`
- `goal_ratio`
- `use_fixed_seeds`
- `debug_seed`
- `allow_fewer_points`

Partition is declared as two explicit lists at module top (no dict iteration) so the order is obvious and review-friendly.

## Work items

### HTML IDs
- [ ] Add to [cosmonaut_app/constants/html_ids.py](cosmonaut_app/constants/html_ids.py) under the `# ROUTING_PARAMS` section:
  - `ADVANCED_TOGGLE_ROUTING_PARAMS_ID = "advanced-toggle-routing-params-id"`
  - `ADVANCED_COLLAPSE_ROUTING_PARAMS_ID = "advanced-collapse-routing-params-id"`
- Both are used in a callback (toggle → collapse), so they satisfy the restricted-usage rule. No `# nocheck` needed.

### Page module
- [ ] In [cosmonaut_app/pages/routing_params.py](cosmonaut_app/pages/routing_params.py), replace the current `fields = list(FullPipelineConfig.model_fields.keys())` loop with two explicit ordered lists: `ESSENTIAL_FIELDS` and `ADVANCED_FIELDS`.
- [ ] Build `card_body_with_placeholder` as:
  1. Rows of `InputField` placeholders for `ESSENTIAL_FIELDS` (2-per-row, same grid pattern as today).
  2. A static `dbc.FormText` caption under the `optimization_objective` input explaining the d/t/i meaning and how it picks between Time Limit / Max distance. (Simplest: put it in its own row right after the row containing the objective field, or insert it as a sibling under the InputField via a nested layout. Choose whichever keeps the row flow clean.)
  3. A `dbc.Button` ("Show advanced options") with `ADVANCED_TOGGLE_ROUTING_PARAMS_ID`, styled via Bootstrap utility classes (`btn btn-link`, no inline CSS).
  4. A `dbc.Collapse` with `ADVANCED_COLLAPSE_ROUTING_PARAMS_ID`, `is_open=False`, containing rows of `InputField` placeholders for `ADVANCED_FIELDS` (same 2-per-row grid).
- [ ] Safeguard: assert at module load time that `set(ESSENTIAL_FIELDS + ADVANCED_FIELDS) == set(FullPipelineConfig.model_fields.keys())`. Prevents silent drift when the backend model gains a new field that nobody added to either list. Use a module-level `assert` with a descriptive message.
- [ ] Verify `FormFactory.extract_field_names` discovers InputFields inside `dbc.Collapse` — it recurses into `children`, so this should work, but confirm by logging or checking that `fields_website` after layout construction contains all 16 fields.

### Collapse toggle callback
- [ ] Add a small callback in `routing_params.py`:
  - Input: `Input(ADVANCED_TOGGLE_ROUTING_PARAMS_ID, "n_clicks")`
  - State: `State(ADVANCED_COLLAPSE_ROUTING_PARAMS_ID, "is_open")`
  - Output: `Output(ADVANCED_COLLAPSE_ROUTING_PARAMS_ID, "is_open")` and `Output(ADVANCED_TOGGLE_ROUTING_PARAMS_ID, "children")` (to flip the label/arrow)
  - Logic: toggle `is_open`, update button text accordingly. Prevent initial call.
  - No defensive programming, no bare excepts — the button either exists or it doesn't.

### Styling
- [ ] Bootstrap classes only (`btn btn-link`, `mt-2`, `g-2`, etc.). No `style={}` on anything new. The existing `card_body_with_placeholder` uses `className="g-2 mt-1"` — match that grid gap.
- [ ] The arrow (▾/▴) is a plain unicode char in the button text — no icon lib needed.

## Non-goals (explicit)

- **Do not** turn Objective into a radio/dropdown. Louis confirmed: keep as free text until Can reworks the backend.
- **Do not** add active/inactive dimming on Time Limit / Max distance. Static caption is enough for now.
- **Do not** remove `working_directory` from the form — the backend still consumes it.
- **Do not** modify `dash_form_factory` — all work is in the page module.
- **Do not** add any new dependencies.

## Risks / things to watch

- **Invalid advanced field while Collapse is closed:** the existing validation flow sets the field's `invalid=True` and disables the Next button. If the user can't see the error (it's hidden), they'll see a disabled Next with no visible reason. **Accepted for now** (first-iteration simplicity). Follow-up: auto-open the Collapse on validation failure — add to a follow-up issue if Louis finds it annoying in practice.
- **Validators that span multiple fields** (model validators targeting fields not present as placeholders) already get routed via `validate_callback`'s "remaining exceptions" path — unaffected by this change.
- **Job in non-PENDING status** (`is_active=False`): all fields render disabled. Collapse still works because `active` only affects `create_component`, not layout structure.

## Execution checklist

- [ ] Add the two new HTML ID constants in the `# ROUTING_PARAMS` block.
- [ ] Refactor `routing_params.py` module-level layout construction into `ESSENTIAL_FIELDS` + `ADVANCED_FIELDS` with an integrity assert.
- [ ] Build `card_body_with_placeholder` with: essential rows → objective helper caption → toggle button → Collapse(advanced rows).
- [ ] Add the toggle callback (open/close + button label flip).
- [ ] Manually verify in the dev server that:
  - Essential fields show in the requested order.
  - Objective caption is visible and correctly worded.
  - Clicking "Show advanced options" expands the Collapse and flips the label.
  - All 11 advanced fields render inside the Collapse.
  - Changing any advanced value persists to the job (check via reload: re-open the page and confirm the Collapse value is retained).
  - Next button still behaves correctly (enabled when form valid, disabled on validation error).
  - Status-banner mode (non-PENDING job) still renders correctly with the Collapse present.
- [ ] Run the project test suite (`docs/conventions/testing.md`) — at minimum, anything that touches the routing_params page.
- [ ] Flag to Louis: any Playwright locators that referenced advanced-field inputs by position/order will break if the advanced fields moved. Grep Playwright tests for the advanced field names before shipping.
