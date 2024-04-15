import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors
import rasterio
from osgeo import gdal
import datetime
import os
from contextlib import contextmanager
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

gdal.DontUseExceptions()

@contextmanager
def temporary_file(suffix):
    import tempfile

    try:
        temp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        yield temp.name
    finally:
        os.remove(temp.name)

# TODO: Use the Download directory for the output files
# TODO: Make the Coloring of the classes more flexible (dont let the user define the colormaps)

class ClassificationPlot:
    """
    A class for generating classification plots from a CSV file as pre-step for TileServer rendering.
    """

    def __init__(self, csv_path):
        """Initialize the ClassificationPlot with the path to a CSV file."""
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"File not found: {csv_path}")
        self.csv_path = csv_path
        self.df = pd.read_csv(self.csv_path)
        self.classes = [col for col in self.df.columns if "Class" in col]
        self.x_unique = None
        self.y_unique = None
        self.grid_3d = None
        self.grid_max_class = None
        self.grid_max_value = None
        self.image = None
        self.crs = None
        self.transform = None
        self.saved_files = []

    def _process_data(self):
        """Read the data from the CSV file and preprocess it."""
        if self.df is None:
            raise ValueError("No data found. Need to read data first.")
        self.df["highest_class"] = self.df[self.classes].idxmax(axis=1)
        self.x = self.df["Easting (m)"].values
        self.y = self.df["Northing (m)"].values
        self.x_unique = np.unique(self.x)
        self.y_unique = np.unique(self.y)

        # get the bounds of df
        self.x_min = self.df["Easting (m)"].min()
        self.x_max = self.df["Easting (m)"].max()
        self.y_min = self.df["Northing (m)"].min()
        self.y_max = self.df["Northing (m)"].max()

    def _create_3d_grid(self):
        """Create a 3D grid from the data."""
        if self.x_unique is None or self.y_unique is None:
            raise ValueError("The data has not been read yet. Call _read_data() first.")
        self.x_unique_len = len(self.x_unique)
        self.y_unique_len = len(self.y_unique)
        self.grid_3d = np.zeros(
            (self.x_unique_len, self.y_unique_len, len(self.classes))
        )
        df_values = self.df[self.classes].values
        x_mapping = {value: i for i, value in enumerate(self.x_unique)}
        y_mapping = {value: i for i, value in enumerate(self.y_unique)}
        for i in range(len(self.x)):
            x_index = x_mapping[self.x[i]]
            y_index = y_mapping[self.y[i]]
            self.grid_3d[x_index, y_index, :] = df_values[i]
        self.grid_3d[self.grid_3d == 0] = np.nan
        self.grid_max_class = np.argmax(self.grid_3d, axis=2)
        self.grid_max_value = np.max(self.grid_3d, axis=2)

    def _create_image(self, cmaps):
        """Create an image from the 3D grid using the provided colormaps."""
        if not all(isinstance(cmap, matplotlib.colors.Colormap) for cmap in cmaps):
            raise ValueError(
                "All elements of 'cmaps' must be instances of matplotlib.colors.Colormap."
            )
        self.image = np.zeros((len(self.x_unique), len(self.y_unique), 4))
        for i, cmap in enumerate(cmaps):
            mask = self.grid_max_class == i
            self.image[mask] = cmap(self.grid_max_value[mask])

    def _transform_to_4326(self):
        """Transform the image to the EPSG:4326 coordinate system."""
        self.transform = rasterio.transform.from_bounds(
            self.y_min - 50,
            self.x_max + 50,
            self.y_max + 50,
            self.x_min - 50,
            self.y_unique_len,
            self.x_unique_len,
        )
        self.crs = "EPSG:31468"

    def _save_plots(self, cmaps):
        """Create and save a plot for each colormap."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d")
        base_name = os.path.splitext(os.path.basename(self.csv_path))[0]
        base_name = base_name.replace("31468", "4326")
        for i, cmap in enumerate(cmaps):
            self.image = np.moveaxis(self.image, 0, -1)
            mask = self.grid_max_class == i
            self.image = np.zeros((len(self.x_unique), len(self.y_unique), 4))
            self.image[mask] = cmap(self.grid_max_value[mask])
            fig, ax = plt.subplots(frameon=False)
            ax.imshow(self.image, origin="lower", interpolation="none")
            ax.axis("off")
            self.image = np.moveaxis(self.image, -1, 0)
            num_bands = self.image.shape[0]
            dtype = self.image.dtype
            height = self.image.shape[1]
            width = self.image.shape[2]
            filename = f"{timestamp}_{base_name}_class-{i+1}"
            output = f"{filename}.tif"
            with temporary_file(".tif") as temp_filename:
                with rasterio.open(
                    temp_filename,
                    "w",
                    driver="GTiff",
                    height=height,
                    width=width,
                    count=num_bands,
                    dtype=dtype,
                    crs=self.crs,
                    transform=self.transform,
                    nodata=0,
                ) as ds:
                    ds.write(self.image)
                raster = gdal.Open(temp_filename)
                gdal.Warp(
                    output,
                    raster,
                    format="GTiff",
                    srcSRS="EPSG:31468",
                    dstSRS="EPSG:4326",
                    xRes=0.0003,
                    yRes=0.0003,
                    srcNodata=0,
                    dstNodata=0,
                    targetAlignedPixels=True,
                    creationOptions=["COMPRESS=LZW", "BIGTIFF=YES"],
                )
                if not os.path.exists(output):
                    raise IOError(f"Failed to create output file: {output}")
                self.saved_files.append(output)

    def generate_plots(self, cmaps):
        """Combine the steps to generate the plots."""
        self._process_data()
        self._create_3d_grid()
        self._create_image(cmaps)
        self._transform_to_4326()
        self._save_plots(cmaps)


# EXAMPLE USAGE:
        
# from classification_plot import ClassificationPlot
# from matplotlib import pyplot as plt

# plot = ClassificationPlot('test_data/8-col-31468.csv')
# plot.generate_plots([plt.cm.Blues, plt.cm.Oranges, plt.cm.Greens, plt.cm.Purples, plt.cm.Reds, plt.cm.Greys])