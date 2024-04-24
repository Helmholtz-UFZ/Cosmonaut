import json
import dash_leaflet as dl

# Load the example osm file
with open(
    "/home/trinkle/git/UFZ-Flask/UFZ-Flask/cosmonaut_app/download/20240424-105506_osm_data_4326.geojson"
) as f:
    osm_data = json.load(f)


# Define the node ids
def create_line_layer(routes):
    coordinates = []
    for route in routes:
        for feature in osm_data["features"]:
            if feature["id"] == route["way"]:
                nodes = feature["properties"]["nodes"]
                coords = feature["geometry"]["coordinates"]
                if nodes.index(route["start_node"]) > nodes.index(route["end_node"]):
                    nodes = nodes[::-1]
                    coords = coords[::-1]
                start_index = nodes.index(route["start_node"])
                end_index = nodes.index(route["end_node"]) + 1
                for _, coordinate in zip(
                    nodes[start_index:end_index], coords[start_index:end_index]
                ):
                    coordinates.append([coordinate[1], coordinate[0]])

    line_layer = dl.Polyline(positions=coordinates, color="red")
    return line_layer


# # Usage:

# # Define the routes
# routes = [
#     {'way': "('way', 922732272)", 'start_node': 845193413, 'end_node': 1036593570},
#     {'way': "('way', 91403181)", 'start_node': 1036593570, 'end_node': 1061793565}
# ]

# # Call the function with the routes
# create_line_layer(routes)
