import logging

from pydantic import BaseModel
import math
import geojson
import uuid


logging.basicConfig(
    format="%(levelname)s - %(asctime)s - %(message)s", level=logging.DEBUG
)


class Point(BaseModel):
    """A class representing a point with x, y coordinates."""

    x: float
    y: float
    classification: int

    def distance_to(self, other):
        """
        Calculate the Euclidean distance between two points.

        Parameters:
        - other (Point): Another Point instance.

        Returns:
        - float: The Euclidean distance between self and other.
        """
        distance = math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)
        return distance


def find_classification(fields):
    class_percentages = dict(zip(fields, range(1, len(fields) + 1)))
    highest_percentage = max(class_percentages.keys())

    return class_percentages[highest_percentage]


def cluster_points(points):
    # Assumes the points are ordered and first and second point are neighbours
    neighbour_dist = points[0].distance_to(points[1])
    classified_points = []
    cluster_list = []
    for point in points:
        if point in classified_points:
            continue
        logging.debug(f"Next cluster starts with {point}")

        classified_points.append(point)
        cluster = [point]

        more_neighbours = True

        while more_neighbours:
            more_neighbours = False
            for other_point in points:
                if other_point in classified_points:
                    continue
                # logging.debug(f"Is {other_point} in cluster?")
                distance_cluster = min(
                    [
                        other_point.distance_to(cluster_point)
                        for cluster_point in cluster
                    ]
                )
                if (
                    distance_cluster > neighbour_dist
                    or point.classification != other_point.classification
                ):
                    # logging.debug("No")
                    continue
                # logging.debug("Yes")
                more_neighbours = True
                cluster.append(other_point)
                classified_points.append(other_point)
        cluster_list.append(cluster)

    return cluster_list


def main():
    csv_path = "upload_data/8-col-31468.csv"
    # epsg_input = 31468
    # epsg_output = 4326

    points = []
    with open(csv_path, "r", encoding="UTF-8") as f_handle:
        next(f_handle)
        for line in f_handle:
            logging.debug(line)
            fields = line.strip().split(",")

            x = float(fields[0])
            y = float(fields[1])
            classification = find_classification([float(e) for e in fields[2:]])
            points.append(Point(x=x, y=y, classification=classification))
            # logging.debug(points[-1])

    cluster_list = cluster_points(points)

    for cluster in cluster_list:
        print(cluster)
        filename = f"upload_data/cluster_{uuid.uuid4()}.geojson"

        features = []
        for point in cluster:
            features.append(
                geojson.Feature(
                    geometry=geojson.Point((point.x, point.y)),
                    properties={"classification": point.classification},
                )
            )

        feature_collection = geojson.FeatureCollection(features)

        with open(filename, "w") as f:
            geojson.dump(feature_collection, f)

        


if __name__ == "__main__":
    main()
