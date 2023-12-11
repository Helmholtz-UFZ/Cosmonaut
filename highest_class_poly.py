import pandas as pd
from scipy.spatial import ConvexHull
import geopandas as gpd
from shapely.geometry import Point
from transformation import transfrom_csv
import os

csv = 'upload_data/8-col-31468_short.csv'
epsg_input = 31468
epsg_output = 4326

df = transfrom_csv(csv, epsg_input, epsg_output)

# Calculate highest class and drop other class columns
class_columns = [col for col in df.columns if col.startswith('Class')]
df['highest_class'] = df[class_columns].apply(lambda row: row.idxmax() if row.max() > 0 else 'NoClass', axis=1)
df.drop(class_columns, axis=1, inplace=True)

# Print the DataFrame with highest class information
print(df)
