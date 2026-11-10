# Example data: Harz

A complete input set for one COSMONAUT job in the Harz region, Germany: a
250 m grid of 65 211 cells (x 619500–680750, y 5713500–5786500, EPSG:25832).

| File | Content | Upload field |
|---|---|---|
| `memberships_harz.csv.xz` | x, y and 15 fuzzy c-means cluster memberships per cell | Membership upload |
| `predictors_harz.csv.xz` | x, y, mask and 5 predictors (normalised, log10-transformed) per cell | Predictor upload |

Both files have no header row. Values are rounded to four decimals to keep the
repository small. Each membership row still sums to 1 within 0.0004, well inside
the validator's tolerance of 0.01.

## Use

1. Decompress: `unxz -k examples/harz/*.xz`
2. Start the app (see the Quick Start in the top-level README) and create a job.
3. On the data upload page, keep the EPSG code at `25832`, upload
   `memberships_harz.csv`, then `predictors_harz.csv`.
4. Continue through street selection, routing parameters and route computation.

The area is large on purpose, so expect waiting time: with the default routing
parameters the route computation took about 25 minutes on a laptop (36 606 street
segments). The street download after the membership upload adds a few minutes,
depending on the Overpass server.
