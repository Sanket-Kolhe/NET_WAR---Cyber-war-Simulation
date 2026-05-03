#!/usr/bin/env python3
"""
Seed armor.db with the 20-node network topology.
Run this after creating a fresh database schema.
"""

import sqlite3
import json

DB_PATH = "armor.db"

# 20-node network definition
NODES = {
    "Node_1":  {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_2":  {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_3":  {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_4":  {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_5":  {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_6":  {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_7":  {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_8":  {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_9":  {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_10": {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_11": {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_12": {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_13": {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_14": {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_15": {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_16": {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_17": {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_18": {"os": "Linux",   "is_db": False, "ports": [22, 80, 443]},
    "Node_19": {"os": "Windows", "is_db": False, "ports": [80, 443, 3389]},
    "Node_20": {"os": "Database", "is_db": True,  "ports": [3306, 5432, 27017]},  # Crown Jewel
}

EDGES = [
    ("Node_1", "Node_2"), ("Node_1", "Node_3"), ("Node_1", "Node_4"),
    ("Node_2", "Node_5"), ("Node_2", "Node_6"), ("Node_3", "Node_6"), ("Node_3", "Node_7"), ("Node_4", "Node_8"), ("Node_4", "Node_9"),
    ("Node_5", "Node_10"), ("Node_6", "Node_10"), ("Node_6", "Node_11"), ("Node_7", "Node_11"), ("Node_7", "Node_12"), ("Node_8", "Node_13"), ("Node_8", "Node_12"), ("Node_9", "Node_14"),
    ("Node_10", "Node_15"), ("Node_11", "Node_15"), ("Node_11", "Node_16"), ("Node_12", "Node_16"), ("Node_13", "Node_16"), ("Node_13", "Node_17"), ("Node_14", "Node_17"),
    ("Node_15", "Node_18"), ("Node_16", "Node_18"), ("Node_16", "Node_19"), ("Node_17", "Node_19"),
    ("Node_18", "Node_20"), ("Node_19", "Node_20"),
]

def seed_database():
    """Populate the database with nodes and network links."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Insert nodes
    for node_name, info in NODES.items():
        node_num = node_name.replace("Node_", "")
        ip_address = f"192.168.1.{node_num}"
        open_ports_json = json.dumps(info["ports"])
        
        cursor.execute("""
            INSERT INTO Nodes (node_name, ip_address, os_type, status, open_ports, blocked_ports, is_database, cpu_usage, scan_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            node_name,
            ip_address,
            info["os"],
            "SECURE",
            open_ports_json,
            "[]",
            1 if info["is_db"] else 0,
            0,
            0,
        ))

    # Insert network links
    for source, target in EDGES:
        # Get node IDs from the newly inserted nodes
        cursor.execute("SELECT node_id FROM Nodes WHERE node_name = ?", (source,))
        source_id = cursor.fetchone()[0]
        
        cursor.execute("SELECT node_id FROM Nodes WHERE node_name = ?", (target,))
        target_id = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO Network_Links (source_node_id, target_node_id)
            VALUES (?, ?)
        """, (source_id, target_id))

    conn.commit()
    conn.close()

    print("✅ Database seeded successfully!")
    print(f"   • Inserted {len(NODES)} nodes")
    print(f"   • Inserted {len(EDGES)} network links")

if __name__ == "__main__":
    seed_database()
