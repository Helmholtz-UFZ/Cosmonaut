from __future__ import annotations

from dash import html
import dash_bootstrap_components as dbc
import math


def progress_steps(current: int, variant: str = "default") -> html.Div:
    """Render a 5-step progress rail with labeled nodes.

    variant: 'default' (in-flow) or 'home' (pre-start: no fill, all upcoming).
    """
    steps = [
        ("User information", "bi-1-circle"),
        ("Data upload", "bi-2-circle"),
        ("Street selection", "bi-3-circle"),
        ("Navigation", "bi-4-circle"),
        ("QR code", "bi-5-circle"),
    ]

    total = len(steps)
    # Use internal points: positions at k/(n+1) for k=1..n (exclude 0 and 1).
    if variant == "home" or total <= 1:
        width_value = "0%"
    else:
        # Cosine-spaced internal points: x_i = ((1 - cos(i*pi/(n+1))) / 2) * 100
        widths = [
            (1 - math.cos(math.pi * i / (total + 1))) * 50.0
            for i in range(1, total + 1)
        ]
        width_value = f"{widths[current - 1]:.6f}%"

    nodes = []
    for i, (label, _icon) in enumerate(steps, start=1):
        if variant == "home":
            state_cls = "upcoming"
        else:
            state_cls = (
                "done" if i < current else ("current" if i == current else "upcoming")
            )
        nodes.append(
            html.Div(
                [html.Span(className="dot"), html.Span(label, className="label")],
                className=f"node {state_cls}",
                role="listitem",
            )
        )

    return html.Div(
        [
            html.Div(
                [html.Div(className="rail-fill", style={"width": width_value})],
                className="rail",
            ),
            html.Div(nodes, className="nodes", role="list"),
        ],
        className=f"progress-steps{' home' if variant == 'home' else ''}",
        role="group",
        **{"aria-label": "Progress steps"},
    )


def page_layout(
    title: str,
    body,
    job_id: str | None = None,
    footer=None,
    below=None,
    step_index: int | None = None,
) -> html.Main:
    """Standard page layout used by all job pages.

    step_index is 1-based and, when provided, will render a 5-step progress
    header across the app (User Info → Data Upload → Street Selection →
    Navigation Selection → QR Code Navigation). Completed steps are shown in
    green (light), current in primary, upcoming in secondary outline.
    """

    # use shared renderer; include optional stepper in header for consistent placement
    header_children = [
        dbc.Row(
            [
                dbc.Col(html.H4(title, className="mb-0"), xs=12, md="auto"),
                dbc.Col(
                    dbc.Badge(
                        f"Job: {job_id or '—'}", color="primary", className="ms-md-3"
                    ),
                    xs=12,
                    md="auto",
                ),
            ],
            className="g-2 align-items-center",
            justify="between",
        )
    ]
    if step_index is not None:
        header_children.append(html.Div(progress_steps(step_index), className="mt-2"))
    header = dbc.CardHeader(header_children)

    # Build card children; include stepper (if any) at the top of the body
    body_children = []
    body_children.extend(body if isinstance(body, list) else [body])

    card_children = [header, dbc.CardBody(body_children)]
    if footer is not None:
        card_children.append(footer)  # footer is a CardFooter (see below)

    content = [dbc.Card(card_children, className="shadow-sm modern-card")]
    if below is not None:
        content.append(below)

    return html.Main(content, role="main", tabIndex=0, className="p-3 p-md-4 page-main")


def progress_footer(
    prev=None,
    next_=None,
    progress_label: str | None = None,
    progress_value: int | None = None,
):
    """Modern footer: just actions; optional progress bar if explicitly provided."""
    left = (
        dbc.Col(
            dbc.Progress(
                label=progress_label or "",
                value=progress_value or 0,
                className="w-100",
                style={"height": "6px"},
            ),
            className="flex-grow-1",
        )
        if (progress_label is not None and progress_value is not None)
        else dbc.Col()
    )

    actions = html.Div(
        [prev or html.Span(), next_ or html.Span()],
        className="footer-actions d-flex gap-2 justify-content-end align-items-center flex-wrap",
    )

    right = dbc.Col(actions, width="auto")

    return dbc.CardFooter(
        dbc.Row([left, right], className="g-2 align-items-center"),
        className="page-footer",
    )
