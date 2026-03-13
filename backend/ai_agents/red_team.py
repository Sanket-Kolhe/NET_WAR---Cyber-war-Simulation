import asyncio
import websockets
import json

async def red_team_agent():
    # Connect to Member 1's Backend Engine
    uri = "ws://localhost:8000/ws/combat"

    try:
        async with websockets.connect(uri) as websocket:
            print("🔴 Red Team AI Online. Infiltrating the network...")

            # ─────────────────────────────────────────────────────────────
            # PHASE 1: RECONNAISSANCE — Real BFS Network Scan (Unit II)
            # Request a BFS scan from the server starting at the entry node.
            # The server runs bfs_scan("Node_1") and returns the full graph
            # traversal order so we know *which* nodes exist and in what
            # layer-by-layer sequence to attack them.
            # ─────────────────────────────────────────────────────────────
            print("\n🔴 [PHASE 1] Launching BFS Reconnaissance Sweep from Node_1...")
            bfs_command = {
                "agent": "red",
                "action": "bfs_scan",
                "target": "Node_1"
            }
            await websocket.send(json.dumps(bfs_command))

            # Wait for the server to reply with the BFS result
            raw = await websocket.recv()
            response = json.loads(raw)

            bfs_order = response.get("bfs_order", [])
            if not bfs_order:
                print("❌ BFS scan returned no nodes. Aborting.")
                return

            print(f"🔴 [RECON] BFS Discovery Order: {' → '.join(bfs_order)}")
            print(f"🔴 [RECON] {len(bfs_order)} nodes mapped. Beginning attack sequence...\n")

            # ─────────────────────────────────────────────────────────────
            # PHASE 2 & 3: STRIPS Planner running in BFS-discovered order
            # We attack nodes exactly in the order BFS found them:
            # shallow/easy-to-reach nodes first, deep nodes last.
            # ─────────────────────────────────────────────────────────────
            while True:
                # Observe environment (server pushes state on every tick)
                state_data = await websocket.recv()
                battlefield = json.loads(state_data)
                nodes = battlefield.get("nodes", {})

                # Pick the next un-owned target in BFS order
                target_id = None
                target_state = None

                for node_id in bfs_order:
                    node_info = nodes.get(node_id, {})
                    if node_info.get("status") != "ROOT_ACCESS":
                        target_id = node_id
                        target_state = node_info.get("status", "UNKNOWN")
                        break

                if not target_id:
                    print("🔴 ALL NODES COMPROMISED. RED TEAM WINS. 🔴")
                    break

                print(f"\n🔴 Target (BFS): {target_id} | State: {target_state}")

                # STRIPS Planner — sequential kill chain
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

                if action_to_take:
                    attack_command = {
                        "agent": "red",
                        "action": action_to_take,
                        "target": target_id
                    }
                    await websocket.send(json.dumps(attack_command))

    except ConnectionRefusedError:
        print("❌ Error: Cannot connect. Is the NET WAR backend engine running?")

if __name__ == "__main__":
    asyncio.run(red_team_agent())