from engine.node import Node
from collections import deque

# Vulnerability base scores by OS type (higher = easier to exploit)
OS_VULN = {"Linux": 1.2, "Windows": 1.0, "Database": 0.8}

class NetworkEnvironment:
    def apply_action(self, command: dict):
        """Processes incoming moves from the AI agents."""
        agent = command.get("agent")       # 'red' or 'blue'
        action = command.get("action")     # e.g., 'scan', 'exploit', 'patch'
        target_id = command.get("target")  # e.g., 'Node_5'

        # If the target doesn't exist, ignore the command
        if target_id not in self.nodes:
            return
            
        target_node = self.nodes[target_id]

        # RED TEAM LOGIC (Offense)
        if agent == "red":
            if action == "scan":
                # Scanning exposes the node
                if target_node.status == "SECURE":
                    target_node.status = "EXPOSED"
            
            elif action == "exploit":
                # Can only exploit if it's already exposed
                if target_node.status == "EXPOSED":
                    target_node.status = "COMPROMISED"
            
            elif action == "privilege_escalation":
                # The final blow
                if target_node.status == "COMPROMISED":
                    target_node.status = "ROOT_ACCESS"

        # BLUE TEAM LOGIC (Defense)
        elif agent == "blue":
            if action == "patch":
                # ROOT_ACCESS requires two patches (drop to COMPROMISED first).
                # COMPROMISED/EXPOSED/SECURE all go straight to SECURE.
                if target_node.status == "ROOT_ACCESS":
                    target_node.status = "COMPROMISED"   # first patch: foothold weakened
                    target_node.scan_rate = 0
                else:
                    target_node.status = "SECURE"        # second patch: fully cleared
                    target_node.scan_rate = 0

            elif action == "kill_process":
                # Downgrades an infection if caught early
                if target_node.status in ["EXPOSED", "COMPROMISED"]:
                    target_node.status = "SECURE"
                    target_node.scan_rate = 0

            elif action == "block_port":
                # Closes a specific port to cut off attack vectors
                port = command.get("port")
                if port and port in target_node.open_ports:
                    target_node.open_ports.remove(port)
                    if port not in target_node.blocked_ports:
                        target_node.blocked_ports.append(port)
    def __init__(self):
        self.nodes = {}
        self.edges = [] # Defines which nodes are connected to each other
        self.setup_initial_network()

    def setup_initial_network(self):
        """Builds the 20-node corporate network."""
        # Layer 0: Gateway
        self.nodes["Node_1"] = Node(node_id="Node_1", os_type="Windows")
        # Layer 1: DMZ
        self.nodes["Node_2"] = Node(node_id="Node_2", os_type="Linux")
        self.nodes["Node_3"] = Node(node_id="Node_3", os_type="Windows")
        self.nodes["Node_4"] = Node(node_id="Node_4", os_type="Linux")
        # Layer 2: Application
        self.nodes["Node_5"] = Node(node_id="Node_5", os_type="Windows")
        self.nodes["Node_6"] = Node(node_id="Node_6", os_type="Linux")
        self.nodes["Node_7"] = Node(node_id="Node_7", os_type="Windows")
        self.nodes["Node_8"] = Node(node_id="Node_8", os_type="Linux")
        self.nodes["Node_9"] = Node(node_id="Node_9", os_type="Windows")
        # Layer 3: Services
        self.nodes["Node_10"] = Node(node_id="Node_10", os_type="Linux")
        self.nodes["Node_11"] = Node(node_id="Node_11", os_type="Windows")
        self.nodes["Node_12"] = Node(node_id="Node_12", os_type="Linux")
        self.nodes["Node_13"] = Node(node_id="Node_13", os_type="Windows")
        self.nodes["Node_14"] = Node(node_id="Node_14", os_type="Linux")
        # Layer 4: Internal
        self.nodes["Node_15"] = Node(node_id="Node_15", os_type="Windows")
        self.nodes["Node_16"] = Node(node_id="Node_16", os_type="Linux")
        self.nodes["Node_17"] = Node(node_id="Node_17", os_type="Windows")
        # Layer 5: Core
        self.nodes["Node_18"] = Node(node_id="Node_18", os_type="Linux")
        self.nodes["Node_19"] = Node(node_id="Node_19", os_type="Windows")
        # Layer 6: Database (target)
        self.nodes["Node_20"] = Node(node_id="Node_20", os_type="Linux", is_database=True)

        #  Network Topology (20 nodes, 7 layers)
        #
        #  Layer 0: Node_1 (Gateway)
        #  Layer 1: Node_2, Node_3, Node_4 (DMZ)
        #  Layer 2: Node_5-9 (App)
        #  Layer 3: Node_10-14 (Services)
        #  Layer 4: Node_15-17 (Internal)
        #  Layer 5: Node_18-19 (Core)
        #  Layer 6: Node_20 (Database)
        self.edges = [
            # Gateway → DMZ
            ("Node_1", "Node_2"),
            ("Node_1", "Node_3"),
            ("Node_1", "Node_4"),
            # DMZ → App
            ("Node_2", "Node_5"),
            ("Node_2", "Node_6"),
            ("Node_3", "Node_6"),
            ("Node_3", "Node_7"),
            ("Node_4", "Node_8"),
            ("Node_4", "Node_9"),
            # App → Services
            ("Node_5", "Node_10"),
            ("Node_6", "Node_10"),
            ("Node_6", "Node_11"),
            ("Node_7", "Node_11"),
            ("Node_7", "Node_12"),
            ("Node_8", "Node_13"),
            ("Node_8", "Node_12"),
            ("Node_9", "Node_14"),
            # Services → Internal
            ("Node_10", "Node_15"),
            ("Node_11", "Node_15"),
            ("Node_11", "Node_16"),
            ("Node_12", "Node_16"),
            ("Node_13", "Node_16"),
            ("Node_13", "Node_17"),
            ("Node_14", "Node_17"),
            # Internal → Core
            ("Node_15", "Node_18"),
            ("Node_16", "Node_18"),
            ("Node_16", "Node_19"),
            ("Node_17", "Node_19"),
            # Core → Database
            ("Node_18", "Node_20"),
            ("Node_19", "Node_20"),
        ]

    def get_adjacency_list(self):
        """Builds a bidirectional adjacency map from the edge list."""
        adjacency = {node_id: [] for node_id in self.nodes}
        for (a, b) in self.edges:
            adjacency[a].append(b)
            adjacency[b].append(a)
        return adjacency

    def bfs_scan(self, start_node_id: str) -> list:
        """
        Performs a real Breadth-First Search (BFS) starting from start_node_id.
        Returns nodes in the order they are discovered (layer by layer).
        This simulates a Red Team reconnaissance sweep of the network graph.
        """
        if start_node_id not in self.nodes:
            return []

        adjacency = self.get_adjacency_list()
        visited = set()
        queue = deque()
        discovery_order = []

        # Seed the BFS with the starting node
        queue.append(start_node_id)
        visited.add(start_node_id)

        while queue:
            current = queue.popleft()
            discovery_order.append(current)

            # Enqueue all unvisited neighbors
            for neighbor in adjacency[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        return discovery_order

    def tick_all_nodes(self):

        for node in self.nodes.values():
            node.simulate_tick()

    def get_state(self):
        return {
            "nodes": {n_id: n.to_dict() for n_id, n in self.nodes.items()},
            "edges": self.edges
        }
        
    def to_dict(self):
        return {
            "nodes": {n_id: n.to_dict() for n_id, n in self.nodes.items()},
            "edges": self.edges
        }

    @classmethod
    def from_dict(cls, data: dict):
        env = cls()
        env.edges = data["edges"]
        env.nodes = {n_id: Node.from_dict(n_data) for n_id, n_data in data["nodes"].items()}
        return env

    # ── Helpers for A* heuristic ──────────────────────────────────────────

    def get_hop_distance(self, from_node: str, to_node: str) -> int:
        """
        Returns the shortest hop count between two nodes using BFS.
        Used as part of A*'s h(n) = hop_distance / vulnerability_score.
        Returns 999 if no path exists.
        """
        if from_node == to_node:
            return 0
        if from_node not in self.nodes or to_node not in self.nodes:
            return 999

        adjacency = self.get_adjacency_list()
        visited = {from_node}
        queue = deque([(from_node, 0)])

        while queue:
            current, dist = queue.popleft()
            for neighbor in adjacency.get(current, []):
                if neighbor == to_node:
                    return dist + 1
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, dist + 1))
        return 999

    def get_vulnerability_score(self, node_id: str) -> float:
        """
        Computes how vulnerable a node is (higher = easier to exploit).
        Based on: open ports count, OS type, and current status.

        Used by A*: h(n) = hop_distance / vulnerability_score
        High vulnerability → low h(n) → A* prefers this path.
        """
        if node_id not in self.nodes:
            return 0.1

        node = self.nodes[node_id]
        # Base score from OS type
        base = OS_VULN.get(node.os_type, 1.0)
        # More open ports = more attack surface
        port_factor = len(node.open_ports) / 3.0   # normalise (default 3 ports)
        # Already compromised nodes are "free" to traverse
        status_bonus = {"SECURE": 1.0, "EXPOSED": 1.5,
                        "COMPROMISED": 2.0, "ROOT_ACCESS": 3.0}
        s_factor = status_bonus.get(node.status, 1.0)

        return max(0.1, base * port_factor * s_factor)