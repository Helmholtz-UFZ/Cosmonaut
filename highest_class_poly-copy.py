from transformation import transfrom_csv
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from sklearn.neighbors import BallTree
import os

csv = 'upload_data/8-col-31468.csv'
epsg_input = 31468
epsg_output = 4326

df = transfrom_csv(csv, epsg_input, epsg_output)

# get the maximum value of each point for the classes and add it to a new column
class_columns = [col for col in df.columns if col.startswith('Class')]
df['highest_class'] = df[class_columns].apply(lambda row: row.idxmax() if row.max() > 0 else 'NoClass', axis=1)

# Function to create separate convex hulls for clusters of points with the same class
def create_convex_hulls(group):
    points = group[['Longitude', 'Latitude']].values
    tree = BallTree(points, metric='haversine')

    labels = tree.query_radius(points, r=20)

    convex_hulls = []
    visited = set()

    for i, label in enumerate(labels):
        if i not in visited:
            # Create convex hull for the cluster
            cluster = group.iloc[label]
            convex_hull = gpd.GeoSeries([Point(lon, lat) for lon, lat in cluster[['Longitude', 'Latitude']].values]).unary_union.convex_hull
            convex_hulls.append(convex_hull)

            # Mark points as visited
            visited.update(label)

    return convex_hulls

# Create GeoDataFrames for each class and compute separate convex hulls
for class_name, group in df.groupby('highest_class'):
    convex_hulls = create_convex_hulls(group)

    # Save each convex hull as a GeoJSON file
    for i, hull in enumerate(convex_hulls):
        hull_gdf = gpd.GeoDataFrame(geometry=[hull])
        hull_gdf.to_file(os.path.join('upload_data', f'{class_name}.geojson'), driver='GeoJSON')
