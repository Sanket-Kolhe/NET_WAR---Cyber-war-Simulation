from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from engine.network import NetworkEnvironment
import asyncio
import json

# ── Pydantic models for REST request bodies ────────────────────────────────────
class TargetNodeRequest(BaseModel):
    target_node_id: str

class BlockPortRequest(BaseModel):
    target_node_id: str
    port: int

class ScanRequest(BaseModel):
    start_node: str = "Node_1"   # default entry point; pivot node after lateral movement

# ── Helper: format a Node for the REST scripts ─────────────────────────────────
def node_to_rest_dict(node_id: str, node) -> dict:
    """
    Maps internal Node fields to the shape expected by scripts/red_team.py
    and scripts/blue_team.py.  A fake IP is derived from the node number so
    the log output looks realistic.
    """
    num = node_id.replace("Node_", "")
    return {
        "id":            node_id,
        "ip_address":    f"192.168.1.{num}",
        "os_type":       "Database" if node.is_database else node.os_type,
        "status":        node.status,
        "cpu_usage":     node.cpu_usage,
        "ports":         node.open_ports,
        "blocked_ports": node.blocked_ports,
        "scan_rate":     node.scan_rate,
        "is_database":   node.is_database,
    }

app = FastAPI(title="NET WAR API")

# Initialize the simulated world
battlefield = NetworkEnvironment()

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
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()

# Background task that acts as the "Time" in our simulation
async def simulation_loop():
    while True:
        # 1. Update OS states (CPU spikes, etc.)
        battlefield.tick_all_nodes()
        
        # 2. Broadcast the current map to all connected clients
        current_state = battlefield.get_state()
        await manager.broadcast(current_state)
        
        # 3. Wait 1.5 seconds before the next tick
        await asyncio.sleep(1.5)

@app.on_event("startup")
async def startup_event():
    # Start the simulation loop when the server starts
    asyncio.create_task(simulation_loop())

@app.websocket("/ws/combat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # 1. Wait for an incoming command from Red/Blue AI agents
            data = await websocket.receive_text()
            command = json.loads(data)
            
            print(f"Executing command: {command}")
            
            # 2. Handle BFS scan specially — reply only to the requesting client
            if command.get("action") == "bfs_scan":
                start_node = command.get("target", "Node_1")
                bfs_order = battlefield.bfs_scan(start_node)
                print(f"🔴 BFS scan from {start_node}: {bfs_order}")
                await websocket.send_text(json.dumps({"bfs_order": bfs_order}))
                continue  # Don't apply as a regular action

            # 3. Apply the action to the battlefield
            battlefield.apply_action(command)

            # 4. Instantly broadcast the updated state to everyone so the UI reacts immediately
            await manager.broadcast(battlefield.get_state())

            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    return {"message": "NET WAR Engine is running."}


# ══════════════════════════════════════════════════════════════════════════════
#  REST API  —  used by scripts/red_team.py and scripts/blue_team.py
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/nodes")
def get_nodes():
    """Returns all current node states (used by blue_team.py to poll for anomalies)."""
    return [
        node_to_rest_dict(nid, node)
        for nid, node in battlefield.nodes.items()
    ]


@app.post("/api/reset")
async def reset_battlefield():
    """
    Resets the entire battlefield to its initial state (all nodes SECURE).
    Called at the start of each simulate.py run so previous state is never
    carried over between simulation runs.
    """
    global battlefield
    battlefield = NetworkEnvironment()
    await manager.broadcast(battlefield.get_state())
    print("🔄 /api/reset — Battlefield reset. All nodes SECURE.")
    return {"status": "reset", "nodes": len(battlefield.nodes)}


@app.post("/api/scan")
async def scan_network(body: ScanRequest = None):
    """
    Phase 1 – Reconnaissance (Unit II: Uninformed Search).
    Only exposes the pivot node + its DIRECT NEIGHBORS (1 hop).
    Red Team must actually own a node to scan outward from it.
    The database stays hidden until Red reaches a depth-3 node next to it.
    """
    start = body.start_node if body else "Node_1"
    if start not in battlefield.nodes:
        start = "Node_1"

    adjacency = battlefield.get_adjacency_list()

    # 1-hop exposure: only start node + its immediate neighbors
    to_expose = [start] + adjacency.get(start, [])

    for node_id in to_expose:
        node = battlefield.nodes[node_id]
        if node.status == "SECURE":
            node.status = "EXPOSED"

    # Still run full BFS for display/return (shows the path structure)
    bfs_order = battlefield.bfs_scan(start)

    await manager.broadcast(battlefield.get_state())

    discovered = [node_to_rest_dict(nid, battlefield.nodes[nid]) for nid in to_expose]
    print(f"🔴 /api/scan — pivot:{start} | exposed: {to_expose}")
    return {"discovered_nodes": discovered, "bfs_order": bfs_order,
            "pivot": start, "exposed_this_scan": to_expose}



@app.post("/api/attack")
async def attack_node(body: TargetNodeRequest):
    """
    Phase 2 – Exploitation (Unit VI: STRIPS kill chain).
    Advances the node one step through: EXPOSED → COMPROMISED → ROOT_ACCESS.
    Also broadcasts the updated state to all WebSocket clients.
    """
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        return {"success": False, "reason": f"Node {node_id} not found."}

    node = battlefield.nodes[node_id]

    if node.status == "EXPOSED":
        battlefield.apply_action({"agent": "red", "action": "exploit",               "target": node_id})
    elif node.status == "COMPROMISED":
        battlefield.apply_action({"agent": "red", "action": "privilege_escalation",  "target": node_id})
    elif node.status == "SECURE":
        # Fallback — expose first if somehow still SECURE
        battlefield.apply_action({"agent": "red", "action": "scan",                  "target": node_id})
    else:
        return {"success": False, "reason": f"Node {node_id} already at {node.status}."}

    await manager.broadcast(battlefield.get_state())
    print(f"🔴 /api/attack — {node_id} now {battlefield.nodes[node_id].status}")
    return {"success": True, "node_id": node_id, "new_status": battlefield.nodes[node_id].status}


@app.post("/api/patch")
async def patch_node(body: TargetNodeRequest):
    """
    Blue Team countermeasure — restores a compromised node to SECURE.
    Also broadcasts the updated state to all WebSocket clients.
    """
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        return {"success": False, "reason": f"Node {node_id} not found."}

    battlefield.apply_action({"agent": "blue", "action": "patch", "target": node_id})
    await manager.broadcast(battlefield.get_state())
    print(f"🔵 /api/patch — {node_id} restored to SECURE")
    return {"success": True, "node_id": node_id, "new_status": "SECURE"}


@app.post("/api/kill_process")
async def kill_process(body: TargetNodeRequest):
    """
    Blue Team: kill_process downgrades EXPOSED/COMPROMISED → SECURE.
    Cheaper than a full patch — used for early-stage threats.
    """
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        return {"success": False, "reason": f"Node {node_id} not found."}

    node = battlefield.nodes[node_id]
    if node.status not in ["EXPOSED", "COMPROMISED"]:
        return {"success": False, "reason": f"Node {node_id} is {node.status} — kill_process has no effect."}

    battlefield.apply_action({"agent": "blue", "action": "kill_process", "target": node_id})
    await manager.broadcast(battlefield.get_state())
    print(f"🔵 /api/kill_process — {node_id} process terminated, status: SECURE")
    return {"success": True, "node_id": node_id, "new_status": "SECURE"}


@app.post("/api/block_port")
async def block_port(body: BlockPortRequest):
    """
    Blue Team: close a specific port on a node to cut off Red Team attack vectors.
    E.g., block port 22 to stop SSH-based lateral movement.
    """
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        return {"success": False, "reason": f"Node {node_id} not found."}

    battlefield.apply_action({"agent": "blue", "action": "block_port", "target": node_id, "port": body.port})
    await manager.broadcast(battlefield.get_state())
    print(f"🔵 /api/block_port — Port {body.port} closed on {node_id}")
    return {"success": True, "node_id": node_id, "port_blocked": body.port}