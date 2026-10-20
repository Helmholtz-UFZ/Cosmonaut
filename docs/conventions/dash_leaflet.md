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

## Tile Layers: Referer and CSP

Every external tile source has to pass two gates that exist only in the deployed
app. Neither shows up locally or in a suite, and both fail as a broken map, not as
an error.

- **Send a Referer to OpenStreetMap.** The cluster ingress (UFZ IT, not in
  `values.yaml`) answers every page with `Referrer-Policy: same-origin`, which strips
  the Referer from cross-origin requests. OSM's tile usage policy requires one; in
  2026-10 both apps showed "Access blocked – App is not following the tile usage
  policy" tiles instead of a map. Set the policy on the layer; Leaflet applies it to
  each tile image, overriding the page policy there:

  ```python
  dl.TileLayer(
      url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      attribution="© OpenStreetMap contributors",
      referrerPolicy="strict-origin-when-cross-origin",
  )
  ```

  Origin only: OSM receives `https://<host>/`, never the page path, which carries
  job ids. A `dl.TileLayer()` without `url` defaults to OSM and needs it too.
  Guarded by `test/test_osm_tile_referrer.py`.

- **Allow the tile host in the CSP.** The ingress `Content-Security-Policy` in
  `deployment/ufz/prod/values.yaml` lists every image host in `img-src`. A host
  missing there fails silently: the layer stays blank, and the only trace is a
  console message. Esri (`server.arcgisonline.com`) and OpenTopoMap
  (`*.tile.opentopomap.org`) were missing until 2026-10, so the Satellite and
  Terrain base maps never loaded in production. `*.tile.openstreetmap.org` does
  not match the bare `tile.openstreetmap.org`, so a layer that drops the `{s}`
  subdomains needs that host added. A `values.yaml` change needs a new tag, see
  [deployment](deployment.md).

To check either in a browser: the network tab shows whether a tile request carries
a `Referer`, and the console reports CSP blocks. Both reproduce locally with a
minimal Dash page that sets the two headers in an `after_request` hook.
