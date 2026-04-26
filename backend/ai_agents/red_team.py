"""
Red Team Attacker AI — backend/ai_agents/red_team.py (WebSocket version)
========================================================================
Uses A* Informed Search to find the optimal attack path through the
network graph to the database (crown jewel).

Algorithm:
  f(n) = g(n) + h(n)
  g(n) = steps taken so far + detection risk (exposed/compromised nodes add risk)
  h(n) = hop_distance_to_database / vulnerability_score
  A* expands the node with LOWEST f(n) → optimal least-cost path

Kill chain per node:  SECURE → EXPOSED → COMPROMISED → ROOT_ACCESS
WIN condition:        Database (Node_10) reaches ROOT_ACCESS
"""

import asyncio
import websockets
import json
import heapq

# ── A* Heuristic Constants ────────────────────────────────────────────────────
DETECTION_RISK_WEIGHT = 0.3   # how much each compromised node increases g(n)

# Depth = shortest hops from internet to each node
DEPTH = {
    "Node_1":  0,
    "Node_2":  1, "Node_3":  1,
    "Node_4":  2, "Node_5":  2, "Node_6":  2,
    "Node_7":  3, "Node_8":  3, "Node_9":  3,
    "Node_10": 4,
}

# Network adjacency (matches backend/engine/network.py topology)
ADJACENCY = {
    "Node_1":  ["Node_2", "Node_3"],
    "Node_2":  ["Node_1", "Node_4", "Node_5"],
    "Node_3":  ["Node_1", "Node_5", "Node_6"],
    "Node_4":  ["Node_2", "Node_7", "Node_8"],
    "Node_5":  ["Node_2", "Node_3", "Node_8"],
    "Node_6":  ["Node_3", "Node_8", "Node_9"],
    "Node_7":  ["Node_4", "Node_10"],
    "Node_8":  ["Node_4", "Node_5", "Node_6", "Node_10"],
    "Node_9":  ["Node_6", "Node_10"],
    "Node_10": ["Node_7", "Node_8", "Node_9"],
}

DATABASE_NODE = "Node_10"


# ══════════════════════════════════════════════════════════════════════════════
#  A* SEARCH — finds the optimal attack path to the database
#
#  State space: network nodes
#  Start: Node_1 (internet entry point)
#  Goal:  Node_10 (database / crown jewel)
#
#  g(n) = steps taken + detection risk accumulated
#  h(n) = hop_distance_to_target / vulnerability_score_of_node
#  f(n) = g(n) + h(n)
# ══════════════════════════════════════════════════════════════════════════════

def compute_vulnerability(node_info: dict) -> float:
    """
    Vulnerability score for a node (higher = easier to exploit).
    Based on: status, number of open ports, OS type.
    """
    os_vuln = {"Linux": 1.2, "Windows": 1.0, "Database": 0.8}
    status_bonus = {"SECURE": 1.0, "EXPOSED": 1.5,
                    "COMPROMISED": 2.0, "ROOT_ACCESS": 3.0}

    os_type = node_info.get("os", node_info.get("os_type", "Windows"))
    base = os_vuln.get(os_type, 1.0)

    ports = node_info.get("ports", [])
    port_factor = len(ports) / 3.0 if ports else 1.0

    status = node_info.get("status", "SECURE")
    s_factor = status_bonus.get(status, 1.0)

    return max(0.1, base * port_factor * s_factor)


def compute_detection_risk(nodes: dict, visited_nodes: set) -> float:
    """
    g(n) penalty: more compromised/exposed nodes = higher detection risk.
    This makes A* prefer stealthier paths.
    """
    risk = 0
    for nid in visited_nodes:
        info = nodes.get(nid, {})
        status = info.get("status", "SECURE")
        if status == "EXPOSED":
            risk += DETECTION_RISK_WEIGHT * 0.5
        elif status == "COMPROMISED":
            risk += DETECTION_RISK_WEIGHT * 1.0
        elif status == "ROOT_ACCESS":
            risk += DETECTION_RISK_WEIGHT * 0.2  # already owned, low additional risk
    return risk


def astar_attack_path(nodes: dict, start: str = "Node_1",
                      goal: str = DATABASE_NODE) -> list:
    """
    A* Search to find the optimal attack path from start to goal.

    Returns: list of node_ids in order [start, ..., goal]
             representing the best attack path.
    """
    if start == goal:
        return [start]

    # Priority queue: (f_score, tie_breaker, node_id, path)
    counter = 0
    open_set = []
    heapq.heappush(open_set, (0, counter, start, [start]))
    visited = set()

    while open_set:
        f_score, _, current, path = heapq.heappop(open_set)

        if current == goal:
            return path

        if current in visited:
            continue
        visited.add(current)

        for neighbor in ADJACENCY.get(current, []):
            if neighbor in visited:
                continue

            # g(n): steps taken + detection risk
            new_path = path + [neighbor]
            g_cost = len(new_path) - 1  # steps taken
            g_cost += compute_detection_risk(nodes, set(new_path))

            # h(n): hop distance to goal / vulnerability score
            hop_dist = DEPTH.get(goal, 4) - DEPTH.get(neighbor, 0)
            hop_dist = max(0, hop_dist)
            vuln = compute_vulnerability(nodes.get(neighbor, {}))
            h_cost = hop_dist / vuln

            f = g_cost + h_cost
            counter += 1
            heapq.heappush(open_set, (f, counter, neighbor, new_path))

    # Fallback: no path found (shouldn't happen in connected graph)
    return [start]


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN AGENT LOOP
# ══════════════════════════════════════════════════════════════════════════════

async def red_team_agent():
    uri = "ws://localhost:8000/ws/combat"

    try:
        async with websockets.connect(uri) as websocket:
            print("🔴 Red Team AI Online. A* Attack Engine initialized.")
            print(f"🔴 Target: {DATABASE_NODE} (Database / Crown Jewel)")
            print(f"🔴 Strategy: A* Informed Search — f(n) = g(n) + h(n)\n")

            # ─────────────────────────────────────────────────────────────
            # PHASE 1: Initial reconnaissance — request BFS scan to get
            # the network map, then compute A* optimal path.
            # ─────────────────────────────────────────────────────────────
            print("🔴 [PHASE 1] Requesting network scan for A* pathfinding...")
            bfs_command = {
                "agent": "red",
                "action": "bfs_scan",
                "target": "Node_1"
            }
            await websocket.send(json.dumps(bfs_command))

            raw = await websocket.recv()
            response = json.loads(raw)
            bfs_order = response.get("bfs_order", [])
            if not bfs_order:
                print("❌ Network scan returned no nodes. Aborting.")
                return

            print(f"🔴 [RECON] Network mapped: {' → '.join(bfs_order)}")
            print(f"🔴 [RECON] {len(bfs_order)} nodes discovered.\n")

            # ─────────────────────────────────────────────────────────────
            # PHASE 2: A* Attack — follow the optimal path
            # ─────────────────────────────────────────────────────────────
            attack_path = None
            path_index = 0

            while True:
                # Observe: receive server tick
                state_data = await websocket.recv()
                battlefield = json.loads(state_data)
                nodes = battlefield.get("nodes", {})

                if not nodes:
                    continue

                # Recompute A* path each tick (adapts to Blue Team's patches)
                attack_path = astar_attack_path(nodes)
                print(f"\n🔴 [A*] Optimal path: {' → '.join(attack_path)}")
                print(f"🔴 [A*] f(n) components: g=steps+risk, h=distance/vulnerability")

                # Find the first node on the path that isn't ROOT_ACCESS yet
                target_id = None
                target_state = None

                for node_id in attack_path:
                    node_info = nodes.get(node_id, {})
                    if node_info.get("status") != "ROOT_ACCESS":
                        target_id = node_id
                        target_state = node_info.get("status", "UNKNOWN")
                        break

                if not target_id:
                    # All nodes on path are ROOT_ACCESS — check if database is owned
                    db_info = nodes.get(DATABASE_NODE, {})
                    if db_info.get("status") == "ROOT_ACCESS":
                        print("🔴 💀 DATABASE COMPROMISED. RED TEAM WINS. 🔴")
                        break
                    else:
                        # Path owned but database not yet — keep attacking
                        target_id = DATABASE_NODE
                        target_state = db_info.get("status", "SECURE")

                print(f"🔴 [A*] Target: {target_id} | State: {target_state}")

                # STRIPS Kill Chain — sequential state advancement
                action_to_take = None
                if target_state == "SECURE":
                    action_to_take = "scan"
                    vuln = compute_vulnerability(nodes.get(target_id, {}))
                    print(f"   → Precondition: SECURE. Action: SCAN (vuln={vuln:.2f})")
                elif target_state == "EXPOSED":
                    action_to_take = "exploit"
                    print(f"   → Precondition: EXPOSED. Action: EXPLOIT payload")
                elif target_state == "COMPROMISED":
                    action_to_take = "privilege_escalation"
                    print(f"   → Precondition: COMPROMISED. Action: ESCALATE to ROOT")

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