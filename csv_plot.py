import matplotlib.pyplot as plt
import matplotlib

matplotlib.use("Agg")
import pandas as pd
import geopandas as gpd
from transformation import transform_csv

# import os
import base64
import io


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
        # base_filename = os.path.splitext(os.path.basename(self.csv_file))[0]
        # output_file = 'images/' + base_filename + '_plot.png'
        fig, ax = plt.subplots(figsize=(8, 8))
        self.gdf.plot(
            column="Class", legend=True, marker="s", markersize=0.2, cmap="tab10", ax=ax
        )

        ax.set_axis_off()
        ax.set_xlim(self.gdf.geometry.x.min(), self.gdf.geometry.x.max())
        ax.set_ylim(self.gdf.geometry.y.min(), self.gdf.geometry.y.max())

        # legend = ax.get_legend()
        # legend.set_bbox_to_anchor((0.25, 0.95))

        image_stream = io.BytesIO()
        plt.savefig(
            image_stream,
            format="png",
            bbox_inches="tight",
            pad_inches=0,
            dpi=600,
            transparent=True,
        )
        plt.close(fig)
        # Convert the BytesIO object to a base64 string
        image_base64 = base64.b64encode(image_stream.getvalue()).decode()
        return image_base64


# Usage:
# plotter = Plotter('upload_data/8-col-31468.csv', 31468, 4326)
# plotter.assign_classes()
# plotter.plot_data('assets/test.png')
