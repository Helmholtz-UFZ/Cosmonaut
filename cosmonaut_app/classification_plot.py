import logging
import os
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import rasterio
from osgeo import gdal
from contextlib import contextmanager

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
        self.df = pd.read_csv(self.csv_path)
        self.src_epsg = src_epsg
        self.base_dir = os.path.join(
            os.getcwd(), "cosmonaut_app/work_dir", str(job_id), "plots"
        )
        self._prepare_data()

    def _prepare_data(self):
        logging.info("Preparing data.")
        # Dynamically rename columns that are not 'Easting (m)' or 'Northing (m)' to 'class_i'
        non_coordinate_columns = [
            col for col in self.df.columns if col not in ["Easting (m)", "Northing (m)"]
        ]
        for i, col in enumerate(non_coordinate_columns, start=1):
            self.df.rename(columns={col: f"class_{i}"}, inplace=True)

        # Dynamically identify all numeric columns as class columns
        self.classes = [
            col
            for col in self.df.columns
            if col.startswith("class_") and pd.api.types.is_numeric_dtype(self.df[col])
        ]

        # Ensure 'Easting (m)' and 'Northing (m)' are numeric
        self.df["Easting (m)"] = pd.to_numeric(self.df["Easting (m)"], errors="coerce")
        self.df["Northing (m)"] = pd.to_numeric(
            self.df["Northing (m)"], errors="coerce"
        )

        # Drop rows with NaN values
        self.df.dropna(
            subset=["Easting (m)", "Northing (m)"] + self.classes, inplace=True
        )

        # Get the highest class per point
        self.df["highest_class"] = self.df[self.classes].idxmax(axis=1)

        # Extract coordinates and bounds
        self.x = self.df["Northing (m)"].values
        self.y = self.df["Easting (m)"].values
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
