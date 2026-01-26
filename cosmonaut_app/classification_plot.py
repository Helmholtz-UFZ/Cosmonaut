import logging
import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import rasterio
from osgeo import gdal
from contextlib import contextmanager
from typing import Optional, Tuple, List
import csv

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")
gdal.DontUseExceptions()
logging.getLogger("rasterio").setLevel(logging.CRITICAL)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)


@contextmanager
def temporary_file(suffix):
    import tempfile

    try:
        temp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        yield temp.name
    finally:
        os.remove(temp.name)


class ClassificationPlot:
    def __init__(self, csv_path, job_id, src_epsg="EPSG:25832"):
        logging.info("Initializing ClassificationPlot.")
        if not os.path.exists(csv_path):
            logging.error(f"File not found: {csv_path}")
            raise FileNotFoundError(f"File not found: {csv_path}")
        self.csv_path = csv_path
        # Read CSV with automatic delimiter and header detection
        self.df = self._read_csv_auto(self.csv_path)
        self.src_epsg = src_epsg
        self.base_dir = os.path.join(
            os.getcwd(), "cosmonaut_app/work_dir", str(job_id), "plots"
        )
        self._prepare_data()

    def _sniff_csv(self, path: str) -> Tuple[str, bool]:
        """Detect delimiter and header presence using csv.Sniffer with fallbacks.

        Returns (delimiter, has_header)
        """
        with open(path, "r", newline="", encoding="utf-8") as f:
            sample = f.read(4096)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                delimiter = dialect.delimiter
            except Exception:
                delimiter = ","
            try:
                # Sniffer can be unreliable with all-numeric rows; use additional check later
                has_header = csv.Sniffer().has_header(sample)
            except Exception:
                has_header = False
        return delimiter, has_header

    def _first_row_all_numeric(self, path: str, delimiter: str) -> bool:
        try:
            with open(path, "r", encoding="utf-8") as f:
                line = f.readline().strip()
                if not line:
                    return False
                tokens = [t.strip() for t in line.split(delimiter)]
                for t in tokens:
                    # Allow empty tokens to be treated as non-numeric
                    if t == "":
                        return False
                    float(t)
                return True
        except Exception:
            return False

    def _read_csv_auto(self, path: str) -> pd.DataFrame:
        """Read CSV whether it has a header or not, with delimiter auto-detection."""
        delimiter, has_header = self._sniff_csv(path)
        # If sniffer said header but first row is all numeric, override
        if has_header and self._first_row_all_numeric(path, delimiter):
            logging.debug(
                "CSV Sniffer indicated header but first row is numeric; treating as no header."
            )
            has_header = False

        logging.info(
            f"Reading CSV with delimiter='{delimiter}' and has_header={has_header} from {os.path.basename(path)}"
        )
        df = pd.read_csv(
            path,
            sep=delimiter,
            header=0 if has_header else None,
            engine="python",
            skipinitialspace=True,
        )
        # Ensure columns have string names for downstream processing
        df.columns = [str(c).strip() for c in df.columns]
        return df

    def _guess_coord_columns_by_name(
        self, columns: List[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Try to guess coordinate columns from their names.

        Returns (easting_col, northing_col) or (None, None) if not found.
        """
        lowered = [c.lower() for c in columns]
        # Preference order for projected coordinates
        easting_candidates = [
            "easting (m)",
            "easting",
            "x (m)",
            "x",
            "lon",
            "longitude",
        ]
        northing_candidates = [
            "northing (m)",
            "northing",
            "y (m)",
            "y",
            "lat",
            "latitude",
        ]
        east_idx = None
        north_idx = None
        for cand in easting_candidates:
            if cand in lowered:
                east_idx = lowered.index(cand)
                break
        for cand in northing_candidates:
            if cand in lowered:
                north_idx = lowered.index(cand)
                break
        easting_col = columns[east_idx] if east_idx is not None else None
        northing_col = columns[north_idx] if north_idx is not None else None
        return easting_col, northing_col

    def _guess_coord_columns_by_values(self, df: pd.DataFrame) -> Tuple[int, int]:
        """Fallback heuristic: assume first two columns are coordinates.

        Returns column indices (easting_idx, northing_idx).
        Also attempts to determine which is Easting vs Northing based on value ranges
        typical for EPSG:25832 (Easting ~ 100k-900k, Northing ~ millions).
        """
        if df.shape[1] < 2:
            raise ValueError("CSV must contain at least two columns for coordinates.")
        c0 = pd.to_numeric(df.iloc[:, 0], errors="coerce")
        c1 = pd.to_numeric(df.iloc[:, 1], errors="coerce")
        # Heuristic: larger magnitude likely Northing in UTM; Easting typically < 1,000,000
        c0_med = np.nanmedian(c0.values)
        c1_med = np.nanmedian(c1.values)
        # Prefer to assign Easting to the one with smaller median
        if np.isnan(c0_med) or np.isnan(c1_med):
            # If NaNs, just default to first=Easting, second=Northing
            return 0, 1
        if c0_med <= c1_med:
            return 0, 1
        else:
            return 1, 0

    def _prepare_data(self):
        logging.info("Preparing data.")

        easting_col_name: Optional[str] = None
        northing_col_name: Optional[str] = None

        # Try name-based detection when there are string headers
        try:
            easting_col_name, northing_col_name = self._guess_coord_columns_by_name(
                list(self.df.columns)
            )
        except Exception:
            easting_col_name, northing_col_name = None, None

        if easting_col_name is None or northing_col_name is None:
            # Fallback to value-based heuristic on first two columns
            e_idx, n_idx = self._guess_coord_columns_by_values(self.df)
            # Build a working copy with guaranteed standard names
            cols = list(self.df.columns)
            easting_col_name = cols[e_idx]
            northing_col_name = cols[n_idx]

        logging.debug(
            f"Detected coordinate columns: Easting='{easting_col_name}', Northing='{northing_col_name}'"
        )

        self.easting_col = easting_col_name
        self.northing_col = northing_col_name

        self.df[self.easting_col] = pd.to_numeric(
            self.df[self.easting_col], errors="coerce"
        )
        self.df[self.northing_col] = pd.to_numeric(
            self.df[self.northing_col], errors="coerce"
        )

        coord_set = {self.easting_col, self.northing_col}
        candidate_class_cols = [c for c in self.df.columns if c not in coord_set]
        # Keep only numeric
        numeric_class_cols = [
            c for c in candidate_class_cols if pd.api.types.is_numeric_dtype(self.df[c])
        ]
        # If dtypes aren't numeric yet (because of header=None), coerce to numeric
        coerced_numeric_cols = []
        for c in numeric_class_cols:
            # Already numeric
            coerced_numeric_cols.append(c)
        # Also consider non-numeric candidates and try to coerce
        for c in candidate_class_cols:
            if c in numeric_class_cols:
                continue
            coerced = pd.to_numeric(self.df[c], errors="coerce")
            if coerced.notna().any():
                self.df[c] = coerced
                coerced_numeric_cols.append(c)

        self.classes = sorted(coerced_numeric_cols, key=lambda x: str(x))

        self.df.dropna(
            subset=[self.easting_col, self.northing_col] + self.classes, inplace=True
        )

        # Get the highest class per point
        self.df["highest_class"] = self.df[self.classes].idxmax(axis=1)

        # Extract coordinates and bounds (use detected column names)
        self.x = self.df[self.northing_col].values
        self.y = self.df[self.easting_col].values
        self.x_unique = np.unique(self.x)
        self.y_unique = np.unique(self.y)
        self.x_min, self.x_max = self.x.min(), self.x.max()
        self.y_min, self.y_max = self.y.min(), self.y.max()
        logging.debug(
            f"Data bounds: x_min={self.x_min}, x_max={self.x_max}, y_min={self.y_min}, y_max={self.y_max}"
        )

    def _create_3d_grid(self):
        logging.info("Creating 3D grid.")
        x_mapping = {value: i for i, value in enumerate(self.x_unique)}
        y_mapping = {value: i for i, value in enumerate(self.y_unique)}
        self.grid_3d = np.zeros(
            (len(self.x_unique), len(self.y_unique), len(self.classes))
        )

        df_values = self.df[self.classes].values
        for i in range(len(self.x)):
            x_index = x_mapping[self.x[i]]
            y_index = y_mapping[self.y[i]]
            self.grid_3d[x_index, y_index, :] = df_values[i]

        self.grid_3d[self.grid_3d == 0] = np.nan
        self.grid_max_class = np.argmax(self.grid_3d, axis=2)
        self.grid_max_value = np.nanmax(self.grid_3d, axis=2)

    def _create_image(self, cmap):
        logging.info("Creating image.")
        num_classes = len(self.classes)
        self.image = np.zeros((len(self.x_unique), len(self.y_unique), 4))
        for i in range(num_classes):
            mask = self.grid_max_class == i
            self.image[mask] = cmap(i / num_classes)

    def _save_image(self, cmap):
        logging.info("Saving image.")
        self.image = np.nan_to_num(np.moveaxis(self.image, -1, 0))
        transform = rasterio.transform.from_bounds(
            self.y_min,
            self.x_max,
            self.y_max,
            self.x_min,
            len(self.y_unique),
            len(self.x_unique),
        )
        crs = self.src_epsg

        # Dynamically name the output files
        base_filename = f"job_{self.base_dir.split('/')[-2]}_{self.src_epsg}"
        output_tif = os.path.join(self.base_dir, f"{base_filename}_output.tif")
        output_tif_4326 = os.path.join(
            self.base_dir, f"{base_filename}_output_4326.tif"
        )

        # Save the GeoTIFF file
        with rasterio.open(
            output_tif,
            "w",
            driver="GTiff",
            height=self.image.shape[1],
            width=self.image.shape[2],
            count=self.image.shape[0],
            dtype=self.image.dtype,
            crs=crs,
            transform=transform,
            nodata=0,
        ) as ds:
            ds.write(self.image)

        # Reproject to EPSG:4326 and save
        raster = gdal.Open(output_tif)
        gdal.Warp(
            output_tif_4326,
            raster,
            format="GTiff",
            srcSRS=self.src_epsg,
            dstSRS="EPSG:4326",
            xRes=0.0003,
            yRes=0.0003,
            srcNodata=0,
            dstNodata=0,
            targetAlignedPixels=True,
            creationOptions=["COMPRESS=LZW", "BIGTIFF=YES"],
        )

        logging.info(f"Saved files: {output_tif}, {output_tif_4326}")

    def generate_plots(self):
        logging.info("Generating plots.")
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        self._create_3d_grid()
        cmap = plt.get_cmap("tab20", len(self.classes))
        self._create_image(cmap)
        self._save_image(cmap)
        logging.info("Plots generated successfully.")
