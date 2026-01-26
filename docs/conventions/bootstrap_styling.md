# Bootstrap Styling Conventions

## Bootstrap Classes Only

**NO inline CSS (`style={}`).** Use Bootstrap classes exclusively.

Existing inline CSS usages are violations to be cleaned up later.

---

## Common Utility Classes

### Spacing
- `m-3`, `mb-3`, `mt-2`, `mt-3` - margin
- `me-2`, `me-4` - margin-end (right)
- `p-0`, `p-3` - padding

### Flexbox
- `d-flex` - enable flex display
- `flex-column` - vertical direction
- `flex-grow-1` - fill available space
- `justify-content-center`, `justify-content-end`, `justify-content-between`
- `align-items-center` - vertical centering
- `flex-wrap` - wrapping behavior
- `gap-2` - spacing between items

### Grid & Columns
- `col-7`, `col-5` - fixed ratio columns
- `col-md-11 col-lg-10 col-xl-9` - responsive widths

### Visual
- `shadow-sm` - subtle drop shadow
- `rounded`, `rounded-top` - border radius
- `border`, `border-dark` - borders
- `bg-light`, `bg-white`, `bg-info` - backgrounds
- `text-center`, `text-muted`, `text-secondary` - text

### Sizing
- `fs-4`, `fs-5` - font sizes
- `mw-100` - max-width 100%
- `min-vh-100` - minimum viewport height

---

## Component-Specific Classes

### Cards
```python
className="shadow-sm m-3 me-4"
```

### Footer Actions
```python
className="footer-actions d-flex gap-2 justify-content-end align-items-center flex-wrap"
```

### Main Layout
```python
className="d-flex flex-column min-vh-100 bg-light"
```

### Split Layout
```python
# Map column
className="col-7 p-0"
# Controls column
className="col-5 p-0"
```

---

## Bootstrap Icons

Use `html.I()` with Bootstrap icon classes:
```python
html.I(className="bi bi-arrow-right-circle me-1")
```
