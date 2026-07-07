# Dash Leaflet Conventions

## `hideout` Is Stale Inside Event Handlers

`hideout` exists to push state into the clientside **style functions**
(`style`, `hoverStyle`) without rebuilding the layer — those read the current
value on every restyle. **Event handlers (`eventHandlers`) do not**: they keep
a snapshot of `hideout` from binding time and never see hideout updates
written by server-side callbacks.

Verified symptom (2026-07-07): a dim-toggle callback wrote
`hideout.dimmed = False`, the *styling* followed correctly, but a click
handler guarding on `ctx.hideout.dimmed` still saw `True` forever — street
marking was completely dead.

Consequences:

- **Never** gate event-handler behavior on server-written hideout fields.
  For page-dependent behavior, read the URL instead:

  ```js
  if (!window.location.pathname.endsWith('/street-selection')) { return; }
  ```

- Reading hideout fields that the handler itself writes via
  `ctx.setProps({hideout: ...})` (e.g. the accumulated `selected` list) works,
  because the clientside setProps re-renders the component and rebinds the
  handler with a fresh snapshot.

Regression test: `test/test_street_selection_marking.py` (clicks a street on
the canvas after a hard page load and asserts the marking badge updates).

## Map Repositioning

Use `viewport` to reposition the map from callbacks. **Never** use `center` or `zoom`
as callback outputs — they are creation-time props and silently fail when updated after
mount.

```python
# WRONG — silently drops the entire callback result
Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "center"),
Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "zoom"),

# CORRECT — use viewport with allow_duplicate
Output(MAIN_MAP_COMPONENT_MAP_SHARED_ID, "viewport", allow_duplicate=True),
```

The viewport value is a dict:

```python
{"center": [lat, lon], "zoom": 12, "transition": "flyTo"}
```

Use `no_update` when you don't want to reposition.
