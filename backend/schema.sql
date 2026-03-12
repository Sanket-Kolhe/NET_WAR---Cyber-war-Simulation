-- schema.sql
-- ARMOR Project Database Schema (SQLite)

CREATE TABLE IF NOT EXISTS Nodes (
    node_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address TEXT UNIQUE NOT NULL,
    os_type TEXT NOT NULL,
    status TEXT DEFAULT 'Safe' -- 'Safe', 'Infected', 'Scanning'
);

CREATE TABLE IF NOT EXISTS Event_Logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    source_node_id INTEGER,
    target_node_id INTEGER,
    action TEXT NOT NULL,
    description TEXT,
    FOREIGN KEY(source_node_id) REFERENCES Nodes(node_id),
    FOREIGN KEY(target_node_id) REFERENCES Nodes(node_id)
);

CREATE TABLE IF NOT EXISTS Attack_Signatures (
    signature_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    pattern TEXT NOT NULL,
    severity INTEGER DEFAULT 1 -- 1 (Low) to 5 (Critical)
);
