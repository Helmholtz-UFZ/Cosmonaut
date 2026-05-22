# Handoff to Claude Design — Round 2

> Paste this into a new Claude Design conversation alongside the regenerated
> screenshots from `assets/screenshots/` (see [README §Sources](README.md)).
> Original review produced six recommendations; this document grades each
> against what shipped on the `Claude-Design` branch.

## What to send

1. The fresh screenshots in [assets/screenshots/](assets/screenshots/) — regenerated against the changed pages via:
   ```bash
   python -m cosmonaut_app.doc_generator <job_id_new> <job_id_finished>
   ```
   (requires the local stack running). Pages whose visual surface changed:
   `home`, `user_info`, `data_upload`, `street_selection`, `routing_params`,
   `route_computation`, `route_download`.
2. The originals from the first review, if still archived, for side-by-side.
3. This file as the changelog.
4. The ask (see bottom).

Codebase access is **not** needed — the design system folder already
contains everything Claude Design used in round one.

---

## Status per recommendation

### #1 Step indicator — **shipped**

Replaced the disabled-tab strip with a numbered stepper.

- Completed steps: teal `bg-success` circle with `bi-check-lg`, wrapped in
  `dcc.Link` → clickable, navigates back to that step.
- Current step: navy `bg-primary` circle with the step number, non-interactive.
- Future steps: muted `bg-light text-muted border` circle with the step
  number, non-interactive.
- Steps separated by `bi-chevron-right` glyphs.
- Step-state derived from `CosmonautJob.stage` + `status` (no new DB fields).

**Deviation from your suggestion:** you proposed numbered circles `①…⑥`
throughout; we use Bootstrap-badge circles with the numeral for current /
future and a check icon for done. Reads cleaner at the rendered size.

### #2 Job-ID kicker — **shipped**

`Upload classification data(b56ee901)` is now:

```
b56ee901            ← html.Code, text-muted, small, d-block
Upload classification data    ← H3, no parens
```

Implemented in `layout.create_card_input`. Applies to all wizard pages.

### #3 Page-header banners — **deferred**

Not in scope for this round. The `bg-info` band on Job Manager / Worker
Management / Logs is unchanged. We expect to revisit after the wizard
surfaces settle — the question may answer itself then.

### #4 Landing page brand banner — **shipped**

`front_banner.png` (astronaut + UFZ van) renders inside the Welcome card
above the action button. `img-fluid rounded mb-3` — scales down at narrow
widths.

### #5 Wizard form grouping — **shipped**

`data_upload` is now grouped under three subheads:

- **COORDINATE SYSTEM** — EPSG input + helper
- **MEMBERSHIP DATA** — upload, status, delete, opacity slider
- **PREDICTOR DATA** — upload, status, delete

Subheads are `html.H6` with `text-uppercase text-muted small fw-bold`.

**Deviation:** your sketch had the opacity slider as a sub-row beneath
"Membership data → upload + status + opacity". We kept opacity inside the
Membership group but as a sibling block, not a labelled sub-row — extra
nesting felt heavier than the three-section split warrants.

### #6 Loading modal — **shipped (lighter than proposed)**

Global blocking modal removed from the upload flow. The status row beneath
each upload button now writes "Uploading…" via a clientside callback the
moment a file is selected; the existing "Uploaded" / error / road-network
status replaces it afterward.

**Deviation:** you proposed a button-local `dbc.Spinner` inside the upload
button. We rejected this — `dcc.Upload` wraps the button, and mutating
its children clientside is finicky for marginal gain. The status row
already feels native here (it's how the road-network background task
communicates).

The global modal **is retained** for `route_computation` and
`worker_management` actions, where a full-screen block is the correct
affordance.

---

## Known open issues (not for Claude Design to grade — for our team)

- Wizard step-state derivation depends on `stage` being correctly bumped
  by every page transition. Backtracking via the stepper does not regress
  stage (saves stay `max(...)`).
- `street_selection` route was renamed `/street-selection` to match the
  dash convention used by every other wizard page.

---

## The ask

Please grade the six items above against the new screenshots:

- Anything we got visually wrong? (Spacing, colour, weight, hit-target size.)
- Of the deviations called out (stepper numerals → check icons; opacity
  block; upload spinner → status row), do any read worse to you than the
  original proposal?
- If we did **one** more design pass next, which surface would you go for
  — the deferred #3 banners, or something new you'd flag now?

Brief is fine. Prioritised list beats prose.
