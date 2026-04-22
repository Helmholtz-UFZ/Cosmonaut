import networkx as nx


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
