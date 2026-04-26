import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from engine.network import NetworkEnvironment

# ─── Settings & Auth ──────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
API_KEY = os.getenv("API_KEY", "supersecret")
API_KEY_NAME = "X-API-Key"

api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if api_key_header == API_KEY:
        return api_key_header
    raise HTTPException(status_code=403, detail="Could not validate API KEY")

# ─── Pydantic Models for Validation ───────────────────────────────────────────
class TargetNodeRequest(BaseModel):
    target_node_id: str

class BlockPortRequest(BaseModel):
    target_node_id: str
    port: int

class ScanRequest(BaseModel):
    start_node: str = "Node_1"

class NodeResponse(BaseModel):
    id: str
    ip_address: str
    os_type: str
    status: str
    cpu_usage: int
    ports: List[int]
    blocked_ports: List[int]
    scan_rate: int
    is_database: bool
    
class ScanResponse(BaseModel):
    discovered_nodes: List[NodeResponse]
    bfs_order: List[str]
    pivot: str
    exposed_this_scan: List[str]

class ActionCommand(BaseModel):
    agent: str
    action: str
    target: Optional[str] = None
    port: Optional[int] = None


class RootResponse(BaseModel):
    message: str


class ResetResponse(BaseModel):
    status: str
    nodes: int


class ActionResponse(BaseModel):
    success: bool
    action: Optional[str] = None
    new_status: Optional[str] = None
    node: Optional[NodeResponse] = None


class WsSnapshotMessage(BaseModel):
    type: str
    nodes: dict[str, NodeResponse]


class WsDeltaMessage(BaseModel):
    type: str
    changed_nodes: dict[str, NodeResponse]

# Helper map
def node_to_rest_dict(node_id: str, node) -> dict:
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

# ─── Redis State Management ───────────────────────────────────────────────────

def battlefield_nodes_to_rest_map(env: NetworkEnvironment) -> dict[str, dict]:
    return {
        node_id: node_to_rest_dict(node_id, node)
        for node_id, node in env.nodes.items()
    }


async def init_redis_state(redis_client):
    state_str = await redis_client.get("battlefield_state")
    if not state_str:
        env = NetworkEnvironment()
        await redis_client.set("battlefield_state", json.dumps(env.to_dict()))

async def get_battlefield() -> NetworkEnvironment:
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        state_str = await r.get("battlefield_state")
        if state_str:
            return NetworkEnvironment.from_dict(json.loads(state_str))
        env = NetworkEnvironment()
        return env
    finally:
        await r.aclose()

async def save_battlefield(env: NetworkEnvironment, changed_node_ids: Optional[list[str]] = None):
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    try:
        await r.set("battlefield_state", json.dumps(env.to_dict()))

        nodes_map = battlefield_nodes_to_rest_map(env)
        if changed_node_ids is None:
            changed = nodes_map
        else:
            changed = {node_id: nodes_map[node_id] for node_id in changed_node_ids if node_id in nodes_map}

        payload = WsDeltaMessage(type="delta", changed_nodes=changed).model_dump()
        await r.publish("battlefield_updates", json.dumps(payload))
    finally:
        await r.aclose()

# ─── Connection Manager ───────────────────────────────────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        tasks = [connection.send_text(json.dumps(message)) for connection in self.active_connections]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

manager = ConnectionManager()

# Background Redis subscriber for WebSockets
async def redis_listener():
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe("battlefield_updates")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await manager.broadcast(data)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe()
        await pubsub.close()
        await r.aclose()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    await init_redis_state(r)
    await r.aclose()
    
    # Start background listener
    task = asyncio.create_task(redis_listener())
    yield
    # Shutdown
    task.cancel()

app = FastAPI(title="NET WAR API", lifespan=lifespan)

@app.websocket("/ws/combat")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        snapshot_battlefield = await get_battlefield()
        snapshot = WsSnapshotMessage(
            type="snapshot",
            nodes=battlefield_nodes_to_rest_map(snapshot_battlefield),
        ).model_dump()
        await websocket.send_text(json.dumps(snapshot))

        while True:
            data = await websocket.receive_text()
            try:
                command_data = json.loads(data)
                command = ActionCommand(**command_data)
            except (json.JSONDecodeError, ValueError):
                continue
                
            battlefield = await get_battlefield()
            
            # Offload BFS scan to thread pool if it gets heavy
            if command.action == "bfs_scan":
                start_node = command.target or "Node_1"
                bfs_order = await asyncio.to_thread(battlefield.bfs_scan, start_node)
                await websocket.send_text(json.dumps({"bfs_order": bfs_order}))
                continue
                
            # Apply action
            async def apply_and_save():
                battlefield.apply_action(command.model_dump())
                changed = [command.target] if command.target else None
                await save_battlefield(battlefield, changed_node_ids=changed)
            
            asyncio.create_task(apply_and_save())
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/", response_model=RootResponse)
def read_root():
    return {"message": "NET WAR Engine is running."}

@app.get("/api/nodes", response_model=List[NodeResponse])
async def get_nodes(api_key: str = Depends(get_api_key)):
    battlefield = await get_battlefield()
    return [
        node_to_rest_dict(nid, node)
        for nid, node in battlefield.nodes.items()
    ]

@app.post("/api/reset", response_model=ResetResponse)
async def reset_battlefield(api_key: str = Depends(get_api_key)):
    battlefield = NetworkEnvironment()
    await save_battlefield(battlefield)
    return {"status": "reset", "nodes": len(battlefield.nodes)}

@app.post("/api/scan", response_model=ScanResponse)
async def scan_network(body: ScanRequest = None, api_key: str = Depends(get_api_key)):
    battlefield = await get_battlefield()
    start = body.start_node if body else "Node_1"
    if start not in battlefield.nodes:
        raise HTTPException(status_code=404, detail=f"Start node '{start}' not found")

    adjacency = battlefield.get_adjacency_list()
    to_expose = [start] + adjacency.get(start, [])
    
    for node_id in to_expose:
        if node_id in battlefield.nodes:
            node = battlefield.nodes[node_id]
            if node.status == "SECURE":
                node.status = "EXPOSED"

    bfs_order = await asyncio.to_thread(battlefield.bfs_scan, start)
    await save_battlefield(battlefield, changed_node_ids=to_expose)

    discovered = [node_to_rest_dict(nid, battlefield.nodes[nid]) for nid in to_expose]
    return {
        "discovered_nodes": discovered, 
        "bfs_order": bfs_order,
        "pivot": start, 
        "exposed_this_scan": to_expose
    }

@app.post("/api/attack", response_model=ActionResponse)
async def attack_node(body: TargetNodeRequest, api_key: str = Depends(get_api_key)):
    battlefield = await get_battlefield()
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        raise HTTPException(status_code=404, detail="Node not found")
        
    node = battlefield.nodes[node_id]
    if node.status == "SECURE":
        node.status = "EXPOSED"
    elif node.status == "EXPOSED":
        node.status = "COMPROMISED"
    elif node.status == "COMPROMISED":
        node.status = "ROOT_ACCESS"

    await save_battlefield(battlefield, changed_node_ids=[node_id])
    return {
        "success": True,
        "action": "attack",
        "new_status": node.status,
        "node": node_to_rest_dict(node_id, node),
    }

@app.post("/api/backdoor", response_model=ActionResponse)
async def backdoor_node(body: TargetNodeRequest, api_key: str = Depends(get_api_key)):
    battlefield = await get_battlefield()
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        raise HTTPException(status_code=404, detail="Node not found")

    node = battlefield.nodes[node_id]
    if node.status in ["SECURE", "EXPOSED"]:
        raise HTTPException(status_code=400, detail="Cannot backdoor a non-compromised node")
        
    await save_battlefield(battlefield, changed_node_ids=[node_id])
    return {
        "success": True,
        "action": "backdoor_installed",
        "new_status": node.status,
        "node": node_to_rest_dict(node_id, node),
    }

@app.post("/api/patch", response_model=ActionResponse)
async def patch_node(body: TargetNodeRequest, api_key: str = Depends(get_api_key)):
    battlefield = await get_battlefield()
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        raise HTTPException(status_code=404, detail="Node not found")

    node = battlefield.nodes[node_id]
    if node.status == "ROOT_ACCESS":
        node.status = "COMPROMISED"
        node.scan_rate = 0
    else:
        node.status = "SECURE"
        node.scan_rate = 0

    await save_battlefield(battlefield, changed_node_ids=[node_id])
    return {
        "success": True,
        "action": "patched",
        "new_status": node.status,
        "node": node_to_rest_dict(node_id, node),
    }

@app.post("/api/kill_process", response_model=ActionResponse)
async def kill_process(body: TargetNodeRequest, api_key: str = Depends(get_api_key)):
    battlefield = await get_battlefield()
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        raise HTTPException(status_code=404, detail="Node not found")

    node = battlefield.nodes[node_id]
    if node.status in ["EXPOSED", "COMPROMISED"]:
        node.status = "SECURE"
        node.scan_rate = 0

    await save_battlefield(battlefield, changed_node_ids=[node_id])
    return {
        "success": True,
        "action": "process_killed",
        "new_status": node.status,
        "node": node_to_rest_dict(node_id, node),
    }

@app.post("/api/block_port", response_model=ActionResponse)
async def block_port(body: BlockPortRequest, api_key: str = Depends(get_api_key)):
    battlefield = await get_battlefield()
    node_id = body.target_node_id
    if node_id not in battlefield.nodes:
        raise HTTPException(status_code=404, detail="Node not found")

    node = battlefield.nodes[node_id]
    port = body.port

    if port in node.open_ports:
        node.open_ports.remove(port)
        if port not in node.blocked_ports:
            node.blocked_ports.append(port)

    await save_battlefield(battlefield, changed_node_ids=[node_id])
    return {
        "success": True,
        "action": "port_blocked",
        "new_status": node.status,
        "node": node_to_rest_dict(node_id, node),
    }
