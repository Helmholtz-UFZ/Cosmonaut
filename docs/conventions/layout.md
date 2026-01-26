# Layout Conventions

## Reusable Components

All reusable components are in `cosmonaut_app/layout.py`.

### `loading_overlay`
Global loading modal - prevents user interaction during operations.
```python
loading_overlay = dbc.Modal(
    dbc.ModalBody([dbc.Spinner(size="lg"), html.H4("Loading...")]),
    id=LOADING_OVERLAY_SHARED_ID,
    is_open=False,
    backdrop="static",
    keyboard=False,
    centered=True,
)
```

### `create_card_input(card_body, card_footer=None, name_step=None, title=None, job_id=None)`
Creates page cards with optional progress steps and title.

### `create_reset_banner(job, job_id)`
Status banner showing job status with reset functionality.

### `create_reset_modal(job_id)`
Confirmation modal for job reset action.

### `create_map(job=None, extra_layers=None)`
Dynamic map creation with zoom/center from job data.

### `progress_footer(prev_button_url=None, next_button_url=None, ...)`
Navigation footer with Previous/Next buttons.

### `steps_tab(page_name, job)`
Progress indicator tabs showing workflow steps.

---

## Layout Functions

### `page_container_split_layout(map, input_container)`
Two-column layout: 70% map + 30% controls.

```python
dbc.Row([
    dbc.Col(map, className="col-7 p-0"),
    dbc.Col(input_container, className="col-5 p-0")
], className="flex-grow-1 d-flex")
```

### `page_container_fullscreen_layout(content)`
Full viewport layout for single content area.

---

## Flex Patterns

Main app structure:
```python
html.Div(
    className="d-flex flex-column min-vh-100 bg-light",
    children=[navbar, main_content, footer]
)
```

Common patterns:
- `d-flex flex-column flex-grow-1` - vertical flex that fills space
- `justify-content-end align-items-center` - right-aligned, centered
- `gap-2` - spacing between flex items

---

## Page File Structure

Standard organization in page files:

1. **Module docstring** - user docs + developer notes
2. **Imports** - standard, third-party, application
3. **Page registration** - `register_page()` with path, name, title
4. **Layout function** - builds UI based on job state
5. **Callbacks section** - page-specific callbacks at bottom
