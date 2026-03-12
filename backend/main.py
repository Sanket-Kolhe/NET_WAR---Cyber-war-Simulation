import asyncio
import random
import sqlite3
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional

app = FastAPI()

# Add CORS middleware for the frontend to access /api/logs
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- DB INIT ---
DB_FILE = "armor.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Read schema.sql to define tables
    with open("schema.sql", "r") as f:
        cursor.executescript(f.read())
    conn.commit()
    conn.close()

def log_event(source: str, action: str, description: str, level: str = "info"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # We will repurpose target_node_id column temporarily to store the 'level' for UI colors
    cursor.execute(
        "INSERT INTO Event_Logs (source_node_id, action, description, target_node_id) VALUES (?, ?, ?, ?)",
        (source, action, description, level)
    )
    conn.commit()
    conn.close()


# In-memory "database" for the boilerplate
class NodeBase(BaseModel):
    id: int
    ip_address: str
    os_type: str
    status: str = "Safe"
    cpu_usage: int = 0
    mem_usage: int = 0

nodes: Dict[int, NodeBase] = {
    1: NodeBase(id=1, ip_address="192.168.1.10", os_type="Linux", status="Safe"),
    2: NodeBase(id=2, ip_address="192.168.1.11", os_type="Windows", status="Safe"),
    3: NodeBase(id=3, ip_address="192.168.1.12", os_type="Linux", status="Safe"),
    4: NodeBase(id=4, ip_address="192.168.1.13", os_type="Windows", status="Safe"),
    5: NodeBase(id=5, ip_address="192.168.1.14", os_type="Linux", status="Safe"),
    6: NodeBase(id=6, ip_address="192.168.1.15", os_type="Windows", status="Safe"),
    7: NodeBase(id=7, ip_address="192.168.1.16", os_type="Linux", status="Safe"),
    8: NodeBase(id=8, ip_address="192.168.1.17", os_type="Linux", status="Safe"),
    9: NodeBase(id=9, ip_address="192.168.1.18", os_type="Windows", status="Safe"),
    10: NodeBase(id=10, ip_address="10.0.0.50", os_type="Database", status="Safe"), # The target
}

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

# --- NEW: Member 1 & 4 API Control Endpoints ---

class ActionRequest(BaseModel):
    target_node_id: int

@app.on_event("startup")
async def startup_event():
    init_db()
    log_event("System", "Boot", "ARMOR Command Server Online", "info")

@app.get("/api/nodes", response_model=List[NodeBase])
async def get_nodes():
    """Member 4 Integration: Return all nodes"""
    return list(nodes.values())

@app.get("/api/logs")
async def get_logs():
    """Member 4: Fetch historical logs for the React Dashboard"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # We map source_node_id to 'source', and target_node_id to 'level' based on our schema hack above
    cursor.execute("SELECT timestamp, source_node_id, description, target_node_id FROM Event_Logs ORDER BY log_id DESC LIMIT 50")
    rows = cursor.fetchall()
    conn.close()
    
    formatted_logs = []
    for row in rows:
        formatted_logs.append({
            "id": random.random(), # Unique ID for React map
            "time": row[0],
            "source": row[1],
            "message": row[2],
            "level": row[3] or "info"
        })
    return formatted_logs

@app.post("/api/scan")
async def scan_network():
    """Member 2 Integration: Attacker maps the network. Returns IP addresses."""
    log_event("Red Team", "Scan", "Initiated subnet reconnaissance", "warning")
    return {"message": "Subnet scan complete", "discovered_nodes": [n.dict() for n in nodes.values()]}

@app.post("/api/attack")
async def execute_attack(req: ActionRequest):
    """Member 2 Integration: Attacker exploits a node."""
    if req.target_node_id not in nodes:
        raise HTTPException(status_code=404, detail="Node not found")
        
    node = nodes[req.target_node_id]
    if node.status == "Infected":
        return {"message": f"Node {req.target_node_id} is already infected."}
        
    # Simulate Exploitation
    node.status = "Infected"
    node.cpu_usage = random.randint(85, 100) # CPU Spike from malware
    node.mem_usage = random.randint(80, 95)
    
    # DB Insertion
    log_event("Red Team", "Exploit", f"Successfully compromised Node {node.id} ({node.ip_address})", "critical")
    
    # Broadcast to frontend
    await manager.broadcast({"type": "update", "data": [node.dict()]})
    return {"message": f"Successfully compromised Node {req.target_node_id}", "node": node.dict()}

@app.post("/api/patch")
async def execute_patch(req: ActionRequest):
    """Member 3 Integration: Defender repairs a node."""
    if req.target_node_id not in nodes:
        raise HTTPException(status_code=404, detail="Node not found")
        
    node = nodes[req.target_node_id]
    if node.status != "Infected":
        return {"message": f"Node {req.target_node_id} is already safe."}
        
    # Simulate Remediation
    node.status = "Safe"
    node.cpu_usage = random.randint(5, 30) # CPU back to normal
    node.mem_usage = random.randint(10, 40)
    
    # DB Insertion
    log_event("Blue Team", "Patch", f"Removed malware and secured Node {node.id} ({node.ip_address})", "info")
    
    # Broadcast to frontend
    await manager.broadcast({"type": "update", "data": [node.dict()]})
    return {"message": f"Successfully patched Node {req.target_node_id}", "node": node.dict()}


# --- WebSockets ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Member 1 Integration: WebSockets for real-time frontend updates (Member 5)"""
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_json({"type": "init", "data": [n.dict() for n in nodes.values()]})
        while True:
            # Wait for any messages from client (if needed)
            data = await websocket.receive_text()
            print(f"Received from client: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    print("Run using: uvicorn main:app --reload")
