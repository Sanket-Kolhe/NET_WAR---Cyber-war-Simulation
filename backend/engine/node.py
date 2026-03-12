import random

class Node:
    def __init__(self, node_id: str, os_type: str, is_database: bool = False):
        self.node_id = node_id
        self.os_type = os_type
        self.is_database = is_database
        
        # State can be: SECURE, EXPOSED, COMPROMISED, ROOT_ACCESS
        self.status = "SECURE" 
        
        # Default ports based on OS
        self.open_ports = [80, 443, 22] if os_type == "Linux" else [80, 443, 3389]
        self.cpu_usage = random.randint(5, 15)
        
    def simulate_tick(self):
        """Simulates the OS running. CPU spikes if the node is under attack or compromised."""
        if self.status in ["COMPROMISED", "ROOT_ACCESS"]:
            # High CPU usage indicates a malware infection
            self.cpu_usage = random.randint(75, 100)
        elif self.status == "EXPOSED":
            # Medium-High CPU indicates active scanning/brute force by Red Team
            self.cpu_usage = random.randint(40, 70)
        else:
            # Normal idle operation
            self.cpu_usage = random.randint(5, 15)

    def to_dict(self):
        """Prepares the node data to be sent over JSON to the frontend."""
        return {
            "id": self.node_id,
            "os": self.os_type,
            "status": self.status,
            "cpu": self.cpu_usage,
            "ports": self.open_ports,
            "is_database": self.is_database
        }