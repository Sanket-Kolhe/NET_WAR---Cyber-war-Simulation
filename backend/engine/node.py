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
        self.blocked_ports: list[int] = []   # ports closed by Blue Team

        self.cpu_usage = random.randint(5, 15)

        # Packets-per-second hitting this node — spikes when under active scan
        self.scan_rate: int = 0

    def simulate_tick(self):
        """Simulates the OS running. CPU and scan_rate spike under attack."""
        if self.status in ["COMPROMISED", "ROOT_ACCESS"]:
            self.cpu_usage  = random.randint(75, 100)
            self.scan_rate  = random.randint(60, 120)   # heavy exfil traffic
        elif self.status == "EXPOSED":
            self.cpu_usage  = random.randint(40, 70)
            self.scan_rate  = random.randint(30, 65)    # active brute-force
        else:
            self.cpu_usage  = random.randint(5, 15)
            self.scan_rate  = random.randint(0, 10)     # normal idle noise

    def to_dict(self) -> dict:
        """Prepares the node data to be sent over JSON."""
        return {
            "id":            self.node_id,
            "os":            self.os_type,
            "status":        self.status,
            "cpu":           self.cpu_usage,
            "ports":         self.open_ports,
            "blocked_ports": self.blocked_ports,
            "scan_rate":     self.scan_rate,
            "is_database":   self.is_database,
        }