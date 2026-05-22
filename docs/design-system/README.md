# COSMONAUT Design System

> **COS**mic ray based soil **MO**isture **P**rediction **NA**vigation and **UT**ility **T**ool

COSMONAUT is a Python-based web application that helps researchers at the
**Helmholtz Centre for Environmental Research (UFZ)** plan optimal field routes
for mobile **Cosmic Ray Neutron Sensor (CRNS) rover surveys**. Researchers
upload a fuzzy cluster *membership* file plus a *predictor* file, the app
downloads the OpenStreetMap road network for the survey area, lets them
select / deselect streets, then runs an Ant-Colony-style optimisation in a
Celery worker to emit a final GPX route as a QR-code download.

The whole tool is a single multi-page **Plotly Dash** application styled with
**Bootswatch Flatly v5.2.3** and rendered through **dash-bootstrap-components**.
Maps are **dash-leaflet** (Leaflet.js); tables are **dash-ag-grid**; forms
are auto-generated with `dash-form-factory`. There is *no* React, no JSX
framework, no Tailwind — every UI rule maps to a Bootstrap utility class.

This design system therefore mirrors the Flatly/Bootstrap vocabulary so that
mocks and prototypes feel native to the real product.

---

## Sources

- **Codebase**  — `uploads/ufz-cosmonaut-main/` (provided as a zipped upload of
  the `ufz-cosmonaut` repo).  Key files referenced while building this system:
  - `cosmonaut_app/layout.py` — navbar, page shells, cards, footers
  - `cosmonaut_app/assets/flatly_bootstrap.css` — base theme (Bootswatch Flatly)
  - `cosmonaut_app/assets/style.css` — six COSMONAUT-specific overrides
  - `cosmonaut_app/assets/bootstrap-icons.min.css` — full Bootstrap-Icons set
  - `cosmonaut_app/pages/*.py` — one file per workflow step
  - `docs/conventions/bootstrap_styling.md` — "Bootstrap classes only, NO inline CSS"
- **Static brand assets**  — `cosmonaut_app/static/`:
  - `sample_logo.svg`  → folded map icon used in the navbar
  - `front_banner.png` → cartoon astronaut driving a UFZ research van
  - `small_banner.jpg` → square crop of the same illustration
- **Screenshots** — `cosmonaut_app/assets/docs/screenshots/*.png` (one per page)
- **No Figma file** was provided. Visual decisions in this system are
  back-derived from the codebase + screenshots.

Everything mentioned above has been copied (read-only) into this project
under `assets/` so designers without codebase access can still build on top.

---

## Content Fundamentals

COSMONAUT's voice is **functional, second-person, lightly technical, and
warmly inviting in the few places a non-expert lands**. It is not a marketing
product; it is an internal scientific tool, and the copy treats the reader as
a colleague who already knows what a CRNS rover and an EPSG code are.

### Tone & voice
- **Direct, imperative, action-first.** Instructional copy is phrased as
  commands: *"Please enter a valid EPSG code and then upload your membership
  data file."*  *"Create a new routing job and follow the steps to upload your
  data, select streets, and download navigation."*
- **Second person** ("you", "your") for the user, **never** "we" / "our".
- **Warm welcome only on the landing card** ("Welcome to COSMONAUT"). After
  that, every page is task-oriented with no flourish.
- **Acknowledges expertise.** Acronyms (EPSG, GPX, CRNS, HPE) appear without
  glosses; helper text is brief, e.g. *"Common choices: 4326, 25832, 3857, …"*.
- **No marketing adjectives.** Never "powerful", "seamless", "next-gen".

### Casing
- **Page titles**: Title Case + the job id in parentheses, e.g.
  *"Upload classification data(b56ee901)"*, *"Set routing parameters(b56ee901)"*.
- **Page-header banners**: Title Case headline + sentence-case subtitle, e.g.
  *"Job Manager"* / *"Centralized management of all COSMONAUT jobs"*.
- **Buttons & tabs**: Title Case (*"Create new job"*, *"Upload membership
  file"*, *"Delete Selection"*, *"Refresh Jobs"*). Short verbs preferred.
- **Form labels**: Sentence case (*"EPSG code"*, *"Email address"*, *"Time limit [h]"*).
- **Brand name**: always set in ALL CAPS as **COSMONAUT**; never "Cosmonaut".

### Status, error & help copy
- **Status verbs read as past-participle facts**: *"Uploaded"*, *"Not uploaded"*,
  *"Road network is constructed"*, *"Road network is being built…"*.
- **Failures are written as actionable retry instructions**:
  *"Road network construction failed! Re-upload membership file. If the
  problem persists, contact the maintainer."*
- **Banners speak in the imperative** about the *reset* action:
  *"This job is currently running. Reset to cancel and restart."*
- **Validation is reassuring**: a green "Looks good!" appears below a valid
  email; a teal check mark sits inside the input.
- **Warnings name the risk plainly**, e.g.
  *"Warning: Your email is visible from inside the UFZ network."*

### Emoji & symbolic chars
- **No emoji.** No 🚀, 🛰, ✅. The single rocket on the landing button is a
  `bi-rocket-takeoff` glyph from Bootstrap Icons, not an emoji.
- **Ellipsis** is the proper character (`…`) in helper text.
- The German *ß* and umlauts (`ü`, `ö`) are used correctly in the UFZ
  illustration ("UFZ — Helmholtz Zentrum für Umweltforschung") and must
  survive copy-edits.

### Example copy in the wild
| Where | Example |
|---|---|
| Hero card body | *"Create a new routing job and follow the steps to upload your data, select streets, and download navigation."* |
| Empty-state hint | *"Or load an existing job using the search bar in the navbar."* |
| EPSG help | *"Common choices: 4326, 25832, 3857, …"* |
| Membership file help | *"The membership file should be a CSV file with fuzzy cluster membership values."* |
| Privacy reassurance | *"We never share your email."* |
| Job-manager subhead | *"Centralized management of all COSMONAUT jobs"* |
| Worker page subhead | *"Monitor and control Celery background workers"* |
| Live-log placeholder | *"Live mode active — waiting for first refresh…"* |
| Destructive confirm | *"This will delete all computation results (logs, routes, GPX files) and reset the job status to PENDING. Your uploaded data and selected streets will be preserved."* |

---

## Visual Foundations

COSMONAUT is **Bootswatch Flatly with two structural inversions**: the navbar
is dark instead of light, and each page is split into a fixed **two-pane
layout** (`col-7` map / `col-5` form-card). Everything else is "stock
Flatly" — flat colours, no gradients on chrome, generous radii, gentle
shadows.

### Colour
- **Brand / primary** is `#2c3e50` — a dark slate-navy. Used for: navbar
  background, primary buttons, the navbar logo+wordmark, and the secondary
  toolbar buttons on the Job/Worker manager pages (*Refresh Jobs*).
- **Info `#3498db`** is the *page-header* colour. Every admin-style page
  (Job Manager, Worker Management, Logs, the Reset banner when a job is
  running) opens with a sky-blue full-bleed banner — this is a strong,
  recurring motif.
- **Success `#18bc9c`** doubles as **link colour** and as the *Completed*
  status pill in the job table. Linked text in markdown cells, the QR-code
  download URL, the valid-input check inside `<dbc.Input valid>` — all teal.
- **Warning `#f39c12`** = "reset" / "clean" buttons + *Pending* status pill.
- **Danger `#e74c3c`** = destructive (delete, kill task, "remove clicked
  roads") and is also the **default street-render colour on the map**.
- **Light `#ecf0f1`** is the outer app background (`bg-light`). All cards
  sit on this very pale neutral on white.
- **Gradients**: none on chrome. The only gradient is `--bs-gradient` (a
  faint white overlay) which Flatly *defines* but COSMONAUT never enables.

See `colors_and_type.css` for the full token set including map-vis colours.

### Type
- **Lato** is the body font (300 / 400 / 700 / 900). Loaded via the user's
  OS in production; for design mocks load from Google Fonts (already done at
  the top of `colors_and_type.css`).
- Headings are **weight 500** with `line-height: 1.2` — slightly tighter
  than Bootstrap default. Body is 400 / 1.5.
- `h1` is 3 rem (clamps down on mobile via Bootstrap's RFS).
- **Monospace** uses the system stack (`SFMono-Regular, Menlo, Monaco, …`)
  and shows up in **two** places only: log output (the `<pre>` in the
  computation page) and the `task_id` column in AgGrid tables.
- **No serifs anywhere**, no display fonts.

### Spacing, radii, layout
- Spacing is the Bootstrap scale (`m-1` 4 px … `m-5` 48 px). Cards live on
  `m-3 me-4`; sections inside a card use `mt-2`, `mb-3`, `gap-2`.
- **Radius**: `0.375rem` default, `0.5rem` on large elements. Buttons,
  inputs, cards, modals, alerts — all share the same family of round corners.
- **No pill buttons** anywhere in the product. The *Selected: 0* counter on
  the street-selection page is the one exception (a square hard-corner
  badge in the source — keep that consistency).
- **Borders**: subtle `1px solid #dee2e6` on cards; the column-layout pages
  use `border border-dark` to draw a stronger 1px slate frame around the
  full-width content block.

### Shadows & depth
- Two shadows only:
  - `shadow-sm`  → `0 .125rem .25rem rgba(0,0,0,.075)` — cards.
  - `shadow`    → `0 .5rem 1rem rgba(0,0,0,.15)` — used by modals.
- **No inner shadows. No glow rings.** Focus state is Bootstrap's default 3 px
  rgba ring in primary-blue.

### Backgrounds & imagery
- App shell: flat `#ecf0f1`. Cards: flat white.
- **No patterns, no full-bleed photos, no parallax**.
- **One brand illustration** — `assets/front_banner.png`, the astronaut +
  research van. It is **only** used:
  - inside the README of the source repo, and
  - (recommended for mocks) on landing / login / 404 — sparingly.
  The illustration's style is **comic-line + flat fill, slightly desaturated
  greens and blues**, with the UFZ wordmark visible. It is *not* a navbar
  element and should never be tiled.

### Motion
- **Almost none.** Dash Leaflet uses `transition: flyTo` for camera moves
  when the map recentres on a new job — that's the only smooth motion.
- Bootstrap's collapse/fade/spinner defaults are used as-is:
  - Modal fade-in: 150 ms ease-out.
  - Dropdown / Collapse: 350 ms ease.
  - Spinner: 0.75 s linear infinite (`dbc.Spinner size="lg"` in the loading
    modal).
- **No bounces, no spring physics, no scroll-triggered animation.**

### Hover & press states
- **Buttons**: Bootstrap default → on hover, background darkens ~10 %, border
  matches. On press (`:active`), background darkens ~15 %. No shrink, no
  shadow lift.
- **Links**: teal `#18bc9c` → darker teal `#13967d`.
- **Nav-link tabs**: active tab gets a white background, primary-coloured
  text, and a faint underline; inactive tabs are flat secondary-grey.
- **Map streets**: hover → `#ff6666` + 22 px stroke; selected (clicked) →
  yellow `#ffd400`; selected + hover → orange `#fd7e14`. These are
  authoritative — preserve in any map mock.

### Transparency & blur
- **Zero blur**. No `backdrop-filter`, no glass surfaces.
- The only transparency in product surfaces is the map's **opacity slider
  on the Membership tile** (0 – 100 %, default 70 %). This is a data-vis
  control, not a chrome decoration.
- Map polylines render at **0.85 opacity** (streets) and **0.8** (route).

### Fixed elements
- **Navbar**: `sticky-top`, full-width, dark.
- **Map**: locked to `col-7` on the left of every job-step page; *not*
  scrollable — the right pane (`.content-panel`) is the only scroll region.
- **Loading modal**: `backdrop="static"`, `keyboard=False`, centred, sm.
- On admin pages without a map (Job Manager, Worker Management, Logs),
  `.no-map-page` hides the map column and the content centres in a
  `col-md-11 col-lg-10 col-xl-9` frame with a hard slate border.

### Forms
- Inputs are Bootstrap-default: 1 px grey border, 0.375 rem radius,
  `padding: 0.375rem 0.75rem`.
- **Valid state** shows a teal check (`background-image` icon, Bootstrap
  built-in) and a teal border `#18bc9c`.
- **Invalid state** shows a red `!` and red border.
- **Helper text** sits below the input as `dbc.FormText`, secondary-grey,
  small.
- Toggles (Bootstrap switches) are used heavily for filters (log levels,
  road-type filters, "Filter by PID"). Off-state: grey rail; On-state:
  primary-blue rail.

### Cards
- Flat white, 1 px border (`#dee2e6`), `0.375rem` radius, `shadow-sm`.
- A **header H3** sits in the card header on the wizard steps and shows
  *"<Action><Job ID in parens>"*.  Tabs sit *under* the header.
- Card body padding is Bootstrap default `1rem`.
- Card footers carry the *Previous / Next* button pair right-aligned.

### Tables (AgGrid)
- Compact 8 px cell padding, alternating row background `#f8f9fa`.
- Column header text is bold-ish (weight 600), small.
- The first column (`task_id`) uses **monospace** with `font-size: 12 px`.
- Sortable columns show the Bootstrap-icon arrow on hover.
- Status cells (PENDING / COMPLETED / FAILED) are rendered as **filled
  full-cell colour bars**, not pills — a strong COSMONAUT idiom that
  appears in the Job Manager. See screenshot `assets/screenshots/job_manager.png`.

---

## Iconography

### What COSMONAUT uses
- **Bootstrap Icons v1.x**, self-hosted from the codebase
  (`cosmonaut_app/assets/bootstrap-icons.min.css` + `fonts/bootstrap-icons.woff2`).
  These have been copied verbatim into `assets/` so designs in this project
  resolve `class="bi bi-*"` exactly as the live app does.
- **Style**: 1-px linear stroke, slightly rounded terminals, mostly outline
  but with a few filled variants (`bi-check-circle-fill`). Stroke-weight is
  consistent across the set.
- **Sizing**: icons inherit text font-size. Inline icons get `me-1` or
  `me-2` spacing from the adjacent label.
- **Colour**: icons inherit text colour. They are *never* multi-colour, never
  brand-coloured on their own.

### Vocabulary in the live app
Inventoried from `cosmonaut_app/pages/*.py` and `layout.py`:

| Where | Bootstrap Icon |
|---|---|
| Navbar — Documentation | `bi-book` |
| Navbar — Logs | `bi-journal-text` |
| Navbar — Worker manager | `bi-cpu` |
| Navbar — Job manager | `bi-list-task` |
| Home — *Create new job* | `bi-rocket-takeoff` |
| Wizard — *Previous* / *Next* | `bi-arrow-left-circle` / `bi-arrow-right-circle` |
| Upload buttons | `bi-upload` |
| Delete (destructive) | `bi-trash` |
| Reset banner | `bi-arrow-counterclockwise` |
| Reset confirm modal | `bi-exclamation-triangle` |
| Help / info tooltip | `bi-info-circle` |
| Refresh buttons | `bi-arrow-clockwise` (also rendered as a unicode ↻ in places) |
| Job-manager *Clean* | `bi-recycle` |
| Job-manager *Delete Selection* | `bi-trash` |
| Street-selection *Remove* | `bi-eraser` |
| Worker page *Submit Test Task* | `bi-play` |
| Download | `bi-download` |

### Logos & illustrations
- **`assets/logo.svg`** — folded-map-with-pin icon, single colour
  (`currentColor`). Sized at 30×30 in the navbar next to the wordmark.
  This is the only logomark; no full / horizontal lockup exists.
- **`assets/front_banner.png`** — 1536×1024 cartoon astronaut driving a
  UFZ research van across the German Harz countryside. The brand
  illustration. Use sparingly (landing, README, 404).
- **`assets/small_banner.jpg`** — square crop of the same.
- **`assets/screenshots/*`** — reference shots of every live page.

### Emoji
**Not used.** Any "icon-looking" character in the live app is a Bootstrap
Icon glyph. Do not introduce emoji in mocks.

### Substitutions
- The "spinner" graphic is **`dbc.Spinner`** which renders Bootstrap's
  built-in CSS spinner — no SVG sprite required.
- For map markers the app relies on Leaflet's default blue pin. Do not
  swap for custom markers without an explicit request.

---

## Index

Files and folders in this design system:

| Path | What's in it |
|---|---|
| `README.md` | You are here. |
| `SKILL.md` | Skill manifest so this folder works as a Claude Code skill. |
| `colors_and_type.css` | All design tokens (CSS custom properties) + minimal semantic CSS. |
| `assets/logo.svg` | The COSMONAUT folded-map mark. |
| `assets/front_banner.png` | Astronaut + UFZ van brand illustration. |
| `assets/small_banner.jpg` | Square crop of the brand illustration. |
| `assets/favicon.ico` | Browser tab icon. |
| `assets/bootstrap-icons.min.css` | Full Bootstrap-Icons stylesheet (self-hosted). |
| `assets/fonts/bootstrap-icons.woff(2)` | Bootstrap-Icons font files. |
| `assets/flatly_bootstrap.css` | The exact Bootswatch Flatly v5.2.3 build used by the live app. |
| `assets/screenshots/*.png` | Reference screenshots of every COSMONAUT page. |
| `preview/*.html` | Design-system cards (typography, colour, components, etc.) — rendered in the *Design System* tab. |
| `ui_kits/cosmonaut-app/` | Interactive UI kit: click-through recreation of the COSMONAUT 7-step wizard. |

---

## CAVEATS

- **No Figma file was provided.** Every spacing/colour/copy decision here is
  derived from the running Dash code + screenshots; visual snapshots from a
  designer's source-of-truth (if one exists) would let me tighten the kit.
- **No production Lato `.ttf`/`.woff` ship with the codebase.** Flatly's
  `--bs-font-sans-serif` lists Lato first and falls back to system sans — the
  live app uses whichever Lato the user's OS provides. For mocks I load Lato
  from Google Fonts. Please confirm this matches what UFZ users actually see;
  if Lato is *not* installed there, the production rendering will silently fall
  through to `-apple-system` / Segoe UI.
- **No formal logo wordmark.** The navbar pairs `assets/logo.svg` with the
  string `" COSMONAUT"` typeset in plain Lato — there's no kerned wordmark.
  If brand wants a real wordmark, please send.
- The Bootswatch Flatly file is **vendored, not authored** by UFZ; if a
  designer wants the system to *fork* Flatly, that's a separate engineering
  task.
