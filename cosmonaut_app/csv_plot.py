import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")
import base64
import io
import os

import geopandas as gpd
import pandas as pd

from cosmonaut_app.transformation import transform_csv


class Plotter:
    def __init__(self, csv_file, epsg_from, epsg_to):
        self.csv_file = csv_file
        self.csv = transform_csv(csv_file, epsg_from, epsg_to)
        self.gdf = gpd.GeoDataFrame(
            self.csv,
            geometry=gpd.points_from_xy(self.csv["Longitude"], self.csv["Latitude"]),
        )
        self.gdf.crs = "epsg:" + str(epsg_to)
        self.bounds = self.gdf.total_bounds

    def assign_classes(self):
        num_classes = len([col for col in self.gdf.columns if "Class" in col])
        class_cols = ["Class" + str(i + 1) for i in range(num_classes)]
        self.gdf["Class"] = self.gdf[class_cols].idxmax(axis=1)

    def plot_data(self):
        num_points = len(self.gdf)
        dpi = 100  # Adjust this value as needed
        fig, ax = plt.subplots(figsize=(num_points / dpi, num_points / dpi), dpi=dpi)
        self.gdf.plot(
            column="Class", legend=True, marker="s", markersize=1, cmap="tab10", ax=ax
        )

        ax.set_axis_off()
        ax.set_xlim(self.gdf.geometry.x.min(), self.gdf.geometry.x.max())
        ax.set_ylim(self.gdf.geometry.y.min(), self.gdf.geometry.y.max())

        # Save the image to the 'images' folder
        image_path = os.path.join("images", "image.png")
        plt.savefig(
            image_path,
            format="png",
            bbox_inches="tight",
            pad_inches=0,
            dpi=dpi,
            transparent=True,
        )
        plt.close(fig)

        # Convert the BytesIO object to a base64 string
        image_base64 = base64.b64encode(open(image_path, "rb").read()).decode()
        return image_base64


# Usage:
# plotter = Plotter('upload_data/8-col-31468.csv', 31468, 4326)
# plotter.assign_classes()
# plotter.plot_data('assets/test.png')
