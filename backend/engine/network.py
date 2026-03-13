from engine.node import Node
from collections import deque

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
        """Builds the 10-node corporate network."""
        # Create Nodes
        for i in range(1, 10):
            os = "Linux" if i % 2 == 0 else "Windows"
            self.nodes[f"Node_{i}"] = Node(node_id=f"Node_{i}", os_type=os)
            
        # The ultimate target for the Red Team
        self.nodes["Node_10"] = Node(node_id="Node_10", os_type="Linux", is_database=True)

        # Richer topology: cross-links between layers so BFS forks in multiple
        # directions. Red Team must choose which branch to attack.
        #
        #  Node_1 (entry)
        #    ├─ Node_2 (DMZ)
        #    │    ├─ Node_4 (App)
        #    │    └─ Node_5 (App) ◄─ cross-link from Node_3
        #    └─ Node_3 (DMZ)
        #         └─ Node_5 (App)
        #              ├─ Node_7 (Internal)
        #              └─ Node_8 (Internal) ◄─ cross-link from Node_6
        #   Node_4 ─ Node_6 ─ Node_8
        #   Node_7, Node_8, Node_9 ─► Node_10 (Vault / DB)
        self.edges = [
            # Entry → DMZ
            ("Node_1", "Node_2"),
            ("Node_1", "Node_3"),
            # DMZ → App layer  (cross-link: Node_2 also connects to Node_5)
            ("Node_2", "Node_4"),
            ("Node_2", "Node_5"),
            ("Node_3", "Node_5"),
            ("Node_3", "Node_6"),
            # App → Internal  (cross-link: multiple paths to Node_8)
            ("Node_4", "Node_7"),
            ("Node_4", "Node_8"),
            ("Node_5", "Node_8"),
            ("Node_6", "Node_8"),
            ("Node_6", "Node_9"),
            # Internal → Vault (3 paths to database)
            ("Node_7", "Node_10"),
            ("Node_8", "Node_10"),
            ("Node_9", "Node_10"),
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