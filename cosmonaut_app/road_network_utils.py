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

def is_critical_road(road):
    """
    Check if a road is critical (e.g., a bridge or highway).

    Parameters:
    road (dict): The road feature from the GeoJSON data.

    Returns:
    bool: True if the road is critical, False otherwise.
    """
    highway_type = road["properties"].get("highway", "")
    is_bridge = road["properties"].get("bridge", False)
    critical_highways = []  # ["motorway", "trunk", "primary", "secondary", "tertiary"]

    return is_bridge or highway_type in critical_highways

def find_connected_roads(nodes, all_roads, exclude_road_id):
    """
    Find roads connected to a set of nodes, excluding a specific road.

    Parameters:
    nodes (list): List of node ids.
    all_roads (list): List of all roads (features) in the dataset.
    exclude_road_id (str): ID of the road to exclude from the search.

    Returns:
    list: List of connected road ids.
    """
    connected_roads = []
    for road in all_roads:
        if road["id"] == exclude_road_id:
            continue  # Skip the excluded road
        road_nodes = road["properties"]["nodes"]
        if any(node in road_nodes for node in nodes):
            connected_roads.append(road["id"])
    return connected_roads

def is_road_connected(road_id, all_roads, graph):
    """
    Check if a road is still connected to the rest of the network.

    Parameters:
    road_id (str): The road ID to check.
    all_roads (list): List of all road features.
    graph (networkx.Graph): The road network graph.

    Returns:
    bool: True if the road is connected to the network, False otherwise.
    """
    road_to_check = next((road for road in all_roads if road["id"] == road_id), None)
    if road_to_check is None:
        return False  # Road doesn't exist

    road_nodes = road_to_check["properties"]["nodes"]
    for node in road_nodes:
        if graph.degree(node) > 1:  # Node has connections beyond the current road
            return True
    return False  # All nodes are isolated if removed


def remove_dead_roads(road_id, all_roads, graph):
    """
    Recursively remove dead roads connected to the deleted road.

    Parameters:
    road_id (str): The id of the road being removed.
    all_roads (list): List of all road features.
    graph (networkx.Graph): The road network graph.

    Returns:
    list: Updated list of roads with dead roads removed.
    """
    road_to_remove = next((road for road in all_roads if road["id"] == road_id), None)
    if road_to_remove is None or is_critical_road(road_to_remove):
        # Do not remove critical roads
        return all_roads

    road_nodes = road_to_remove["properties"]["nodes"]
    all_roads = [road for road in all_roads if road["id"] != road_id]

    # Update the graph to remove the road
    for i in range(len(road_nodes) - 1):
        graph.remove_edge(road_nodes[i], road_nodes[i + 1])

    # Find connected roads and check if they are now isolated
    connected_roads = find_connected_roads(road_nodes, all_roads, road_id)

    for connected_road in connected_roads:
        if not is_road_connected(connected_road, all_roads, graph):
            # If the connected road is now isolated, remove it
            all_roads = remove_dead_roads(connected_road, all_roads, graph)

    return all_roads