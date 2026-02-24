from engine.node import Node

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
                # Secures a node completely
                target_node.status = "SECURE"
                
            elif action == "kill_process":
                # Downgrades an infection if caught early
                if target_node.status in ["EXPOSED", "COMPROMISED"]:
                    target_node.status = "SECURE"
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

        # Create connections (Edges)
        # e.g., Node 1 is connected to Node 2 and Node 3
        self.edges = [
            ("Node_1", "Node_2"), ("Node_1", "Node_3"),
            ("Node_2", "Node_4"), ("Node_3", "Node_5"),
            ("Node_4", "Node_6"), ("Node_5", "Node_7"),
            ("Node_6", "Node_8"), ("Node_7", "Node_9"),
            ("Node_8", "Node_10"), ("Node_9", "Node_10")
        ]

    def tick_all_nodes(self):
        for node in self.nodes.values():
            node.simulate_tick()

    def get_state(self):
        return {
            "nodes": {n_id: n.to_dict() for n_id, n in self.nodes.items()},
            "edges": self.edges
        }