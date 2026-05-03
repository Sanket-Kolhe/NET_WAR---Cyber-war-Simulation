-- schema.sql
-- ARMOR Project Database Schema (SQLite)
-- Aligned with Red Team A* pathfinding and Blue Team Minimax AI expectations

CREATE TABLE IF NOT EXISTS Nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    node_name TEXT UNIQUE NOT NULL,
    ip_address TEXT UNIQUE NOT NULL,
    os_type TEXT NOT NULL,  -- 'Linux', 'Windows', 'Database'
    status TEXT DEFAULT 'SECURE',  -- Kill Chain: 'SECURE' → 'EXPOSED' → 'COMPROMISED' → 'ROOT_ACCESS'
    open_ports TEXT,  -- JSON array: '[22, 80, 443, 3306]'
    blocked_ports TEXT,  -- JSON array: '[]'
    is_database INTEGER DEFAULT 0,  -- 1 for Database (Crown Jewel), 0 for regular nodes
    cpu_usage INTEGER DEFAULT 0,  -- CPU utilization percentage
    scan_rate INTEGER DEFAULT 0  -- Port scan rate (packets/sec)
);

-- Defines the network topology: which nodes are directly connected
CREATE TABLE IF NOT EXISTS Network_Links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_node_id INTEGER NOT NULL,
    target_node_id INTEGER NOT NULL,
    FOREIGN KEY(source_node_id) REFERENCES Nodes(node_id),
    FOREIGN KEY(target_node_id) REFERENCES Nodes(node_id),
    UNIQUE(source_node_id, target_node_id)
);

CREATE TABLE IF NOT EXISTS Event_Logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source_node_id INTEGER,
    target_node_id INTEGER,
    action TEXT NOT NULL,  -- 'scan', 'exploit', 'patch', 'block_port', etc.
    description TEXT,
    FOREIGN KEY(source_node_id) REFERENCES Nodes(node_id),
    FOREIGN KEY(target_node_id) REFERENCES Nodes(node_id)
);

CREATE TABLE IF NOT EXISTS Attack_Signatures (
    signature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    pattern TEXT NOT NULL,
    severity INTEGER DEFAULT 1  -- 1 (Low) to 5 (Critical)
);
