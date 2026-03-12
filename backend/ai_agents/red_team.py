import asyncio
import websockets
import json
import random

async def red_team_agent():
    # Connect to Member 1's Backend Engine
    uri = "ws://localhost:8000/ws/combat"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("🔴 Red Team AI Online. Infiltrating the network...")
            
            while True:
                # 1. Observe the Environment (Listen to the Server)
                # This will automatically pause the AI until the server sends the next update
                state_data = await websocket.recv()
                battlefield = json.loads(state_data)
                nodes = battlefield.get("nodes", {})
                
                # 2. Reconnaissance (Unit II: Basic Search)
                target_id = None
                target_state = None
                
                for n_id, node_info in nodes.items():
                    if node_info["status"] != "ROOT_ACCESS":
                        target_id = n_id
                        target_state = node_info["status"]
                        break 
                
                if not target_id:
                    print("🔴 ALL NODES COMPROMISED. RED TEAM WINS. 🔴")
                    break
                    
                print(f"\n🔴 Target Locked: {target_id} | Current State: {target_state}")
                
                # 3. The STRIPS Planner (Unit VI)
                action_to_take = None
                
                if target_state == "SECURE":
                    action_to_take = "scan"
                    print("   -> Precondition missing. Must SCAN to expose node.")
                    
                elif target_state == "EXPOSED":
                    action_to_take = "exploit"
                    print("   -> Node exposed. Executing EXPLOIT payload.")
                    
                elif target_state == "COMPROMISED":
                    action_to_take = "privilege_escalation"
                    print("   -> Node compromised. Escalating to ROOT_ACCESS.")
                    
                # 4. Execute the Plan 
                if action_to_take:
                    attack_command = {
                        "agent": "red",
                        "action": action_to_take,
                        "target": target_id
                    }
                    await websocket.send(json.dumps(attack_command))
                    
                # NOTE: We removed the asyncio.sleep(2) from here!
                # The AI now acts exactly at the speed of the server ticks.
                
    except ConnectionRefusedError:
        print("❌ Error: Cannot connect. Is the NET WAR backend engine running?")

if __name__ == "__main__":
    # Start the async loop
    asyncio.run(red_team_agent())