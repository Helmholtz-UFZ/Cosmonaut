import logging
import os
import tempfile

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from osgeo import gdal

from cosmonaut_app.constants.general import MEMBERSHIP_TIF

log = logging.getLogger(__name__)


class ClassificationPlot:
    def __init__(self, df, work_dir, src_epsg):
        log.info("Initializing ClassificationPlot")
        self.df = df.copy()
        self.src_epsg = src_epsg
        self.base_dir = work_dir
        self._prepare_data()

    def _prepare_data(self):
        log.debug("Preparing data")

        coord_cols = {"Easting", "Northing"}
        self.classes = sorted(c for c in self.df.columns if c not in coord_cols)

        self.df["highest_class"] = self.df[self.classes].idxmax(axis=1)

        # Northing = x (rows), Easting = y (columns) for raster orientation
        self.x = self.df["Northing"].values
        self.y = self.df["Easting"].values
        self.x_unique = np.unique(self.x)
        self.y_unique = np.unique(self.y)
        self.x_min, self.x_max = self.x.min(), self.x.max()
        self.y_min, self.y_max = self.y.min(), self.y.max()
        log.debug(
            f"Data bounds: x_min={self.x_min}, x_max={self.x_max}, "
            f"y_min={self.y_min}, y_max={self.y_max}"
        )

    def _create_3d_grid(self):
        log.debug("Creating 3D grid")
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

    def _create_image(self):
        log.debug("Creating image")
        cmap = plt.get_cmap("tab20", len(self.classes))
        num_classes = len(self.classes)
        self.image = np.zeros(
            (len(self.x_unique), len(self.y_unique), 4), dtype=np.uint8
        )
        for i in range(num_classes):
            mask = self.grid_max_class == i
            rgba = np.array(cmap(i / num_classes))
            self.image[mask] = (rgba * 255).astype(np.uint8)

    def _save_image(self):
        log.debug("Saving image")
        self.image = np.moveaxis(self.image, -1, 0)
        transform = rasterio.transform.from_bounds(
            self.y_min,
            self.x_max,
            self.y_max,
            self.x_min,
            len(self.y_unique),
            len(self.x_unique),
        )

        output_tif_4326 = os.path.join(self.base_dir, MEMBERSHIP_TIF)

        # Write intermediate TIF to a temp file, then reproject to EPSG:4326.
        # rasterio and GDAL don't share /vsimem/, so a real file is needed.
        with tempfile.NamedTemporaryFile(suffix=".tif", delete=True) as tmp:
            with rasterio.open(
                tmp.name,
                "w",
                driver="GTiff",
                height=self.image.shape[1],
                width=self.image.shape[2],
                count=self.image.shape[0],
                dtype=np.uint8,
                crs=self.src_epsg,
                transform=transform,
            ) as ds:
                ds.write(self.image)

            # Reproject to EPSG:4326 and save as tiled GeoTIFF for TiTiler
            raster = gdal.Open(tmp.name)
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
                creationOptions=[
                    "COMPRESS=LZW",
                    "BIGTIFF=YES",
                    "TILED=YES",
                    "BLOCKXSIZE=256",
                    "BLOCKYSIZE=256",
                ],
            )
            raster = None

        log.debug(f"Saved membership raster: {output_tif_4326}")

    def generate_plots(self):
        log.info("Generating plots")
        assert os.path.isdir(self.base_dir), f"Work dir missing: {self.base_dir}"
        self._create_3d_grid()
        self._create_image()
        self._save_image()
        log.info("Plots generated successfully")
