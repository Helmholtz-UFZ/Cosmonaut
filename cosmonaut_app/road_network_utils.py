import networkx as nx

from cosmonaut_app.constants.general import TRACK_GRADES, UNGRADED_TRACK_GRADE


def track_grade_allowed(properties, allowed_grades):
    """Return True if a feature passes the track-grade filter.

    Only ``highway=track`` features are graded; every other feature always
    passes. Tracks whose ``tracktype`` is missing or not a standard
    grade1..grade5 value fall into the ``UNGRADED_TRACK_GRADE`` bucket, which
    is selectable in the UI ("No grade tag") like any grade.

    Lives here (not in street_selector) so both users import it without a
    cycle: street_selector -> osm.projection -> osm/__init__ -> downloader.

    Parameters:
    properties (dict): GeoJSON feature properties with highway and tracktype.
    allowed_grades (list): Allowed tracktype values incl. the ungraded bucket.

    Returns:
    bool: Whether the feature stays in the network.
    """
    if properties["highway"] != "track":
        return True
    # .get(): legacy (osmnx-era) download files omit the key entirely when no
    # way in the AOI carried a tracktype tag; same handling as the None the
    # current transform writes — the ungraded bucket.
    grade = properties.get("tracktype")
    if grade not in TRACK_GRADES:
        grade = UNGRADED_TRACK_GRADE
    return grade in allowed_grades


def build_graph(all_roads):
    """
    Build a graph from the roads using nodes as connections.

    Parameters:
    all_roads (list): List of road features from the GeoJSON data.

    Returns:
    Graph: A NetworkX graph representing the road network.
    """
    G = nx.Graph()
    for road in all_roads:
        nodes = road["properties"]["nodes"]
        for i in range(len(nodes) - 1):
            G.add_edge(nodes[i], nodes[i + 1], road_id=road["id"])
    return G


def get_largest_subnetwork(G):
    """
    Find the largest connected subnetwork in the graph.

    Parameters:
    G (Graph): A NetworkX graph representing the road network.

    Returns:
    set: The set of nodes in the largest connected subnetwork.
    """
    largest_subnetwork = max(nx.connected_components(G), key=len)
    return largest_subnetwork


def remove_disconnected_roads(G, largest_subnetwork, all_roads):
    """
    Remove roads that are not connected to the largest subnetwork.

    Parameters:
    G (Graph): A NetworkX graph representing the road network.
    largest_subnetwork (set): Set of nodes in the largest subnetwork.
    all_roads (list): List of road features from the GeoJSON data.

    Returns:
    list: Updated list of roads with disconnected roads removed.
    """
    remaining_roads = []
    for road in all_roads:
        road_nodes = road["properties"]["nodes"]
        if any(node in largest_subnetwork for node in road_nodes):
            remaining_roads.append(road)
    return remaining_roads
