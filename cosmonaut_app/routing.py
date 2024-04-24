import json
import dash_leaflet as dl
import gpxpy
import requests
import qrcode
import io
import base64
import os


class RouteCreator:
    """
    A class that creates routes and performs various operations on them.

    Args:
        osm_data_path (str): The path to the OSM data file.

    Attributes:
        osm_data (dict): The OSM data loaded from the file.

    Methods:
        create_routes_layer: Creates a routes layer based on the provided routes.
        create_gpx: Creates a GPX file based on the provided routes.
        delete_gpx: Deletes the specified GPX file.
        upload_gpx: Uploads the specified GPX file and returns the link.
        create_qr_code: Creates a QR code image based on the provided URL.

    """

    def __init__(self, osm_data_path):
        with open(osm_data_path) as f:
            self.osm_data = json.load(f)

    def create_routes_layer(self, routes):
        """
        Creates a routes layer based on the provided routes.

        Args:
            routes (list): A list of route objects.

        Returns:
            dl.Polyline: A polyline representing the routes layer.

        """
        coordinates = []
        for route in routes:
            for feature in self.osm_data["features"]:
                if feature["id"] == route["way"]:
                    nodes = feature["properties"]["nodes"]
                    coords = feature["geometry"]["coordinates"]
                    if nodes.index(route["start_node"]) > nodes.index(
                        route["end_node"]
                    ):
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

    def create_gpx(self, routes, filename="route.gpx"):
        """
        Creates a GPX file based on the provided routes.

        Args:
            routes (list): A list of route objects.
            filename (str, optional): The name of the GPX file to be created. Defaults to "route.gpx".

        """
        gpx = gpxpy.gpx.GPX()

        for route in routes:
            gpx_route = gpxpy.gpx.GPXRoute()
            for feature in self.osm_data["features"]:
                if feature["id"] == route["way"]:
                    nodes = feature["properties"]["nodes"]
                    coords = feature["geometry"]["coordinates"]
                    if nodes.index(route["start_node"]) > nodes.index(
                        route["end_node"]
                    ):
                        nodes = nodes[::-1]
                        coords = coords[::-1]
                    start_index = nodes.index(route["start_node"])
                    end_index = nodes.index(route["end_node"]) + 1
                    for coordinate in coords[start_index:end_index]:
                        gpx_route.points.append(
                            gpxpy.gpx.GPXRoutePoint(coordinate[1], coordinate[0])
                        )
            gpx.routes.append(gpx_route)

        with open(filename, "w") as file:
            file.write(gpx.to_xml())

    def delete_gpx(self, filename="route.gpx"):
        """
        Deletes the specified GPX file.

        Args:
            filename (str, optional): The name of the GPX file to be deleted. Defaults to "route.gpx".

        """
        os.remove(filename)

    def upload_gpx(self, filename="route.gpx"):
        """
        Uploads the specified GPX file and returns the link.

        Args:
            filename (str, optional): The name of the GPX file to be uploaded. Defaults to "route.gpx".

        Returns:
            str: The link to the uploaded GPX file.

        Raises:
            Exception: If the upload fails.

        """
        with open(filename, "rb") as file:
            response = requests.post(
                "https://file.io",
                files={"file": ("route.gpx", file, "application/gpx+xml")},
            )
            if response.status_code == 200:
                return response.json()["link"]
            else:
                raise Exception("Failed to upload GPX file")

    def create_qr_code(self, url):
        """
        Creates a QR code image based on the provided URL.

        Args:
            url (str): The URL to be encoded in the QR code.

        Returns:
            str: The base64-encoded data URI of the QR code image.

        """
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill="black", back_color="white")
        img_io = io.BytesIO()
        img.save(img_io, "PNG")
        img_io.seek(0)
        img_data = base64.b64encode(img_io.getvalue()).decode()

        return f"data:image/png;base64,{img_data}"


# # Usage:

# # Define the routes for the example test
# routes = [
#     {"way": "('way', 91403181)", "start_node": 1061793565, "end_node": 1036593570},
#     {"way": "('way', 922732272)", "start_node": 1036593570, "end_node": 845193413},
#     {"way": "('way', 70909551)", "start_node": 845193413, "end_node": 845197359},
#     {"way": "('way', 70909733)", "start_node": 845197359, "end_node": 845197431},
#     {"way": "('way', 70909838)", "start_node": 845197431, "end_node": 845190677},
#     {"way": "('way), 70909517)", "start_node": 845190677, "end_node": 845190684},
#     {"way": "('way', 70909551)", "start_node": 845190684, "end_node": 9232344563},
#     {"way": "('way', 1000189951)", "start_node": 9232344563, "end_node": 845189629},
#     {"way": "('way', 54234166)", "start_node": 845189629, "end_node": 683872135},
#     {"way": "('way', 89369683)", "start_node": 683872135, "end_node": 1036584699},
# ]

# route_creator = RouteCreator("/home/trinkle/git/UFZ-Flask/UFZ-Flask/cosmonaut_app/download/20240424-105506_osm_data_4326.geojson")
# line_layer = route_creator.create_routes_layer(routes)
# google_maps_url = route_creator.create_gmaps_url(routes)
# route_creator.create_gpx(routes)
# gpx_url = route_creator.upload_gpx()
# route_creator.create_qr_code(gpx_url)
# route_creator.delete_gpx()
