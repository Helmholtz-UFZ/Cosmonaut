# Dash Leaflet Conventions

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
