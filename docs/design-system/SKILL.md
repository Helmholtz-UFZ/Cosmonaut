---
name: cosmonaut-design
description: Use this skill to generate well-branded interfaces and assets for COSMONAUT — the UFZ Cosmic Ray Neutron Sensor route-planning tool — either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colours, type, fonts, assets, and a UI kit that mirrors the live Plotly Dash + Bootswatch Flatly product.
user-invocable: true
---

Read the `README.md` file within this skill, and explore the other available files.

If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.

If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

## Quick reference

- **Stack the live app uses**: Plotly Dash + dash-bootstrap-components + dash-leaflet + Bootswatch **Flatly v5.2.3** (Bootstrap 5.2). HTML is generated from Python; styling is **Bootstrap utility classes only — no inline CSS**. See `assets/flatly_bootstrap.css`.
- **Brand colours** (see `colors_and_type.css`):
  - Primary navy `#2c3e50` (navbar, primary buttons)
  - Info blue `#3498db` (page-header banners — recurring motif)
  - Success teal `#18bc9c` (links, completed status)
  - Warning orange `#f39c12` (reset/clean, pending)
  - Danger red `#e74c3c` (delete, kill — also the default street-render colour)
  - App background `#ecf0f1`, surfaces white
- **Font**: Lato 400 / 500 / 700. Headings weight 500, line-height 1.2.
- **Iconography**: Bootstrap Icons (`class="bi bi-*"`), self-hosted in `assets/`. **No emoji.**
- **Layout signature**: every job-step page is a fixed two-pane split — `col-7` map (left) + `col-5` form card (right). Admin pages drop the map and centre a `col-md-11 col-lg-10 col-xl-9` block with a hard slate border.
- **Voice**: imperative, second-person, technical but warm, no marketing language. Acronyms (EPSG, GPX, CRNS) are used without glosses.
- **Brand illustration**: `assets/front_banner.png` (astronaut + UFZ research van). Use sparingly.

## Files to read first

1. `README.md` — full content fundamentals, visual foundations, iconography.
2. `colors_and_type.css` — design tokens.
3. `ui_kits/cosmonaut-app/README.md` — the click-through UI kit.
4. `preview/*.html` — quick visual reference for every primitive.
