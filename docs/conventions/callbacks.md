# Callback Conventions

## Callback Types

### Page-Specific Callbacks
Use `@callback` decorator in page files. Auto-registered via Dash pages plugin.

```python
# In pages/user_info.py
from dash import callback, Input, Output

@callback(
    Output(EMAIL_INPUT_ID, "valid"),
    Output(EMAIL_INPUT_ID, "invalid"),
    Input(EMAIL_INPUT_ID, "value"),
)
def validate_email(value):
    ...
```

### Shared Callbacks
Use `@app.callback` wrapped in registration functions. Called from `app.py`.

```python
# In layout.py
def register_navbar_callbacks(app):
    @app.callback(
        Output(SEARCH_RESULTS_ID, "children"),
        Input(SEARCH_BUTTON_ID, "n_clicks"),
        State(SEARCH_INPUT_ID, "value"),
        prevent_initial_call=True,
    )
    def search_job_id(n_clicks, job_id):
        ...

# In app.py
register_navbar_callbacks(app)
```

---

## Common Patterns

### `prevent_initial_call=True`
For user-triggered actions only:
```python
@callback(..., prevent_initial_call=True)
def handle_click(n_clicks):
    ...
```

### `allow_duplicate=True`
When multiple callbacks output to same component:
```python
@callback(
    Output(STORE_ID, "data", allow_duplicate=True),
    ...
    prevent_initial_call=True,
)
```

### `PreventUpdate`
Stop callback execution for guard conditions:
```python
from dash.exceptions import PreventUpdate

@callback(...)
def process(n_clicks, data):
    if n_clicks is None:
        raise PreventUpdate
    if not data:
        raise PreventUpdate
    # proceed
```

### `ctx.triggered_id`
Handle multiple trigger sources:
```python
from dash import ctx

@callback(
    Output(...),
    Input(BUTTON_1_ID, "n_clicks"),
    Input(BUTTON_2_ID, "n_clicks"),
)
def handle_buttons(n1, n2):
    if ctx.triggered_id == BUTTON_1_ID:
        # handle button 1
    elif ctx.triggered_id == BUTTON_2_ID:
        # handle button 2
```

---

## File Structure

Standard organization in page files:

```python
# 1. Module docstring
"""Page description."""

# 2. Imports
from dash import html, callback, Input, Output
from cosmonaut_app.constants.html_ids import ...
from cosmonaut_app.layout import ...

# 3. Page registration
register_page(__name__, path="/page", name="Page", title="Page Title")

# 4. Layout function
def layout(job_id=None):
    ...
    return page_container_split_layout(map, input_container)

# 5. Helper functions (if needed)
def validate_input(value):
    ...

# 6. Callbacks section
@callback(...)
def callback_1(...):
    ...

@callback(...)
def callback_2(...):
    ...
```
