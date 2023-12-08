# I dont want a dash app, I want a python script that does the following:
# I want have csv with the following columns:
# Easting (m),Northing (m),Class1,Class2,Class3,Class4,Class5,Class6, ... ,ClassN
# the values of the classes added together are 1.0, so the values are percentages.
# I want to extract the highest class for each point and create a new column with the name of the class and drop the other columns except the Easting and Northing columns.
# convert the EPSG 31468 to 4326 with from transformation import transfrom_csv where the input_file is the csv file and the epsg_input is 31468 and the epsg_output is 4326
# save the result as a geojson file into the upload_data folder

from transformation import transfrom_csv
import pandas as pd
import numpy as np
import geopandas as gpd
import json
import os

csv = 'upload_data/8-col-31468_short.csv'
epsg_input = 31468
epsg_output = 4326

df = transfrom_csv(csv, epsg_input, epsg_output)
# get the maximum value of each point for the classes and add it to a new column. drop the other class columns afterwards.
class_columns = [col for col in df.columns if col.startswith('Class')]
df['highest_class'] = df[class_columns].apply(lambda row: row.idxmax() if row.max() > 0 else 'NoClass', axis=1)
df.drop(class_columns, axis=1, inplace=True)
# extract the points for each highest_class separately and store them in separate dataframes
dfs = []
for class_name in df['highest_class'].unique():
    dfs.append(df[df['highest_class'] == class_name])
# convert the dataframes to geodataframes
gdfs = []
for df in dfs:
    gdfs.append(gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude, df.Latitude)))
    # drop the Latitude and Longitude columns
    gdfs[-1].drop(['Latitude', 'Longitude'], axis=1, inplace=True)

# take every point of each geodataframe and make a convex hull around it
for gdf in gdfs:
    gdf['geometry'] = gdf['geometry'].unary_union.convex_hull
    # drop the points except one
    gdf.drop(gdf.index[1:], inplace=True)
    print(gdf)
    # save the geodataframe as a geojson file
    gdf.to_file(os.path.join('upload_data', gdf['highest_class'].unique()[0] + '.geojson'), driver='GeoJSON')



# # make a rectangle buffer of the points (10m)
# for gdf in gdfs:
#     gdf['geometry'] = gdf['geometry'].buffer(0.001, cap_style=3)
#     # drop the points that are not in the polygon
#     gdf = gdf[gdf.within(gdf.unary_union)]
#     # save the geodataframe as a geojson file
#     gdf.to_file(os.path.join('upload_data', gdf['highest_class'].unique()[0] + '.geojson'), driver='GeoJSON')