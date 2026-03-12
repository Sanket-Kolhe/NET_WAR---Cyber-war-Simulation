from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from engine.network import NetworkEnvironment
import asyncio
import json

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
            
            # 2. Apply the action to the battlefield
            battlefield.apply_action(command)
            
            # 3. Instantly broadcast the updated state to everyone so the UI reacts immediately
            await manager.broadcast(battlefield.get_state())
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/")
def read_root():
    return {"message": "NET WAR Engine is running."}