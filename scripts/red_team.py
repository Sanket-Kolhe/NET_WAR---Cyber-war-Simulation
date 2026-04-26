"""
Red Team Attacker AI — scripts/red_team.py (REST version)
=========================================================
Uses A* Informed Search to find the optimal attack path through the
network graph to the database (crown jewel).

Algorithm:
  f(n) = g(n) + h(n)
  g(n) = steps taken so far + detection risk (exposed/compromised nodes)
  h(n) = hop_distance_to_database / vulnerability_score
  A* expands the node with LOWEST f(n) → optimal least-cost path

Kill chain per node:  EXPOSED → COMPROMISED → ROOT_ACCESS
WIN:  Database reaches ROOT_ACCESS
LOSE: Blue Team defends database through full round
"""

import time
import heapq
import requests

API_URL = "http://localhost:8000/api"

# ── Timing ────────────────────────────────────────────────────────────────────
ATTACK_STEP_DELAY  = 1.5
MOVE_NEXT_DELAY    = 1.5
FINAL_STRIKE_DELAY = 2
ROUND_RESET_DELAY  = 3

# ── A* Constants ──────────────────────────────────────────────────────────────
DETECTION_RISK_WEIGHT = 0.3
DATABASE_NODE = "Node_10"

DEPTH = {
    "Node_1":  0,
    "Node_2":  1, "Node_3":  1,
    "Node_4":  2, "Node_5":  2, "Node_6":  2,
    "Node_7":  3, "Node_8":  3, "Node_9":  3,
    "Node_10": 4,
}

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


def print_action(msg):
    print(f"[RED TEAM] {msg}")


# ══════════════════════════════════════════════════════════════════════════════
#  A* SEARCH — finds the optimal attack path to the database
# ══════════════════════════════════════════════════════════════════════════════

def compute_vulnerability(node: dict) -> float:
    """Vulnerability score: higher = easier to exploit."""
    os_vuln = {"Linux": 1.2, "Windows": 1.0, "Database": 0.8}
    status_bonus = {"SECURE": 1.0, "EXPOSED": 1.5,
                    "COMPROMISED": 2.0, "ROOT_ACCESS": 3.0}

    os_type = node.get("os_type", "Windows")
    base = os_vuln.get(os_type, 1.0)
    ports = node.get("ports", [])
    port_factor = len(ports) / 3.0 if ports else 1.0
    s_factor = status_bonus.get(node.get("status", "SECURE"), 1.0)

    return max(0.1, base * port_factor * s_factor)


def compute_detection_risk(nodes_by_id: dict, visited: set) -> float:
    """g(n) penalty: compromised/exposed nodes increase detection risk."""
    risk = 0
    for nid in visited:
        info = nodes_by_id.get(nid, {})
        status = info.get("status", "SECURE")
        if status == "EXPOSED":
            risk += DETECTION_RISK_WEIGHT * 0.5
        elif status == "COMPROMISED":
            risk += DETECTION_RISK_WEIGHT * 1.0
        elif status == "ROOT_ACCESS":
            risk += DETECTION_RISK_WEIGHT * 0.2
    return risk


def astar_attack_path(nodes_list: list, start: str = "Node_1",
                      goal: str = DATABASE_NODE) -> list:
    """
    A* Search: finds optimal attack path from start to goal.

    f(n) = g(n) + h(n)
    g(n) = steps taken + detection risk
    h(n) = hop_distance / vulnerability_score

    Returns: list of node_ids [start, ..., goal]
    """
    nodes_by_id = {n["id"]: n for n in nodes_list}

    if start == goal:
        return [start]

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

            new_path = path + [neighbor]

            # g(n): steps + detection risk
            g_cost = len(new_path) - 1
            g_cost += compute_detection_risk(nodes_by_id, set(new_path))

            # h(n): hop distance / vulnerability
            hop_dist = max(0, DEPTH.get(goal, 4) - DEPTH.get(neighbor, 0))
            vuln = compute_vulnerability(nodes_by_id.get(neighbor, {}))
            h_cost = hop_dist / vuln

            f = g_cost + h_cost
            counter += 1
            heapq.heappush(open_set, (f, counter, neighbor, new_path))

    return [start]


# ══════════════════════════════════════════════════════════════════════════════
#  KILL CHAIN — attacks a single node through the full chain
# ══════════════════════════════════════════════════════════════════════════════

def full_kill_chain(node: dict) -> str:
    """
    Runs the full kill chain on a node.
    Returns: 'ROOT_ACCESS', 'DEFENDED', or 'PARTIAL'.
    """
    node_id = node['id']
    ip = node['ip_address']

    # Hit 1: EXPOSED → COMPROMISED
    print_action(f"⚔️  [{node_id}] Exploit → {ip}...")
    time.sleep(ATTACK_STEP_DELAY)
    r = requests.post(f"{API_URL}/attack", json={"target_node_id": node_id})
    result = r.json() if r.status_code == 200 else {}
    status = result.get("new_status", "UNKNOWN")
    if not result.get("success") or status == "SECURE":
        print_action(f"   → ❌ Blocked by Blue Team on {node_id}")
        return "DEFENDED"
    print_action(f"   → {node_id} is now {status}")

    # Hit 2: COMPROMISED → ROOT_ACCESS
    print_action(f"🔺 [{node_id}] Privilege Escalation → {ip}...")
    time.sleep(ATTACK_STEP_DELAY)
    r2 = requests.post(f"{API_URL}/attack", json={"target_node_id": node_id})
    result2 = r2.json() if r2.status_code == 200 else {}
    status2 = result2.get("new_status", "UNKNOWN")
    if not result2.get("success") or status2 == "SECURE":
        print_action(f"   → ❌ Blue Team killed process on {node_id} mid-escalation!")
        return "DEFENDED"
    print_action(f"   → {node_id} is now {status2}")

    if status2 == "ROOT_ACCESS":
        print_action(f"   → 💀 ROOT_ACCESS on {node_id}!")
        return "ROOT_ACCESS"

    return "PARTIAL"


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════

def run_attacker_ai():
    print_action("Initializing A* Attack Engine...")
    print_action(f"Target: {DATABASE_NODE} (Database / Crown Jewel)")
    print_action("Strategy: A* Informed Search — f(n) = g(n) + h(n)")
    print_action("  g(n) = steps taken + detection risk")
    print_action("  h(n) = hop_distance / vulnerability_score")
    print_action("WIN condition : Database reaches ROOT_ACCESS")
    print_action("LOSE condition: Blue Team defends database through full round\n")
    time.sleep(1)

    round_num = 0

    while True:
        round_num += 1
        print_action(f"\n{'='*55}")
        print_action(f"  ATTACK ROUND {round_num}")
        print_action(f"{'='*55}")

        # ── Phase 1: Scan + A* pathfinding ────────────────────────────────
        print_action("Running network scan...")
        response = requests.post(f"{API_URL}/scan")
        if response.status_code != 200:
            print_action("Scan failed — retrying in 3s")
            time.sleep(3)
            continue

        data = response.json()
        discovered_nodes = data.get("discovered_nodes", [])
        bfs_order = data.get("bfs_order", [])

        # Get full node list for A* computation
        all_nodes = requests.get(f"{API_URL}/nodes").json()

        # Compute A* optimal attack path
        attack_path = astar_attack_path(all_nodes)
        print_action(f"A* Optimal Path: {' → '.join(attack_path)}")

        # Show f(n) breakdown
        for nid in attack_path:
            node_info = next((n for n in all_nodes if n["id"] == nid), {})
            vuln = compute_vulnerability(node_info)
            hop = max(0, DEPTH.get(DATABASE_NODE, 4) - DEPTH.get(nid, 0))
            print_action(f"   {nid}: vuln={vuln:.2f}, hop_dist={hop}, "
                         f"h(n)={hop/vuln:.2f}")
        print()

        # ── Phase 2: Attack nodes along A* path ──────────────────────────
        db_node = None
        owned = 0
        nodes_by_id = {n["id"]: n for n in discovered_nodes}

        for node_id in attack_path:
            node = nodes_by_id.get(node_id)
            if not node:
                continue
            if node['os_type'] == 'Database':
                db_node = node
                continue
            if node.get("status") == "ROOT_ACCESS":
                owned += 1
                continue
            result = full_kill_chain(node)
            if result == "ROOT_ACCESS":
                owned += 1
            time.sleep(MOVE_NEXT_DELAY)

        # ── Phase 3: Final strike on Database ─────────────────────────────
        if db_node:
            print_action(f"\n{'!'*55}")
            print_action(f"  FINAL TARGET: {db_node['id']} ({db_node['ip_address']})")
            print_action(f"{'!'*55}")
            time.sleep(FINAL_STRIKE_DELAY)
            result = full_kill_chain(db_node)

            if result == "ROOT_ACCESS":
                print_action("\n🚨 RED TEAM WINS — Database fully compromised!")
                print_action("   Data exfiltration in progress. Simulation over.")
                break
            else:
                print_action(f"\n🛡️  Blue Team defended the database this round!")
                print_action(f"   Nodes owned: {owned}/9. Regrouping in {ROUND_RESET_DELAY}s...")
                time.sleep(ROUND_RESET_DELAY)

    print_action("Attack sequence terminated.")


if __name__ == "__main__":
    try:
        run_attacker_ai()
    except requests.exceptions.ConnectionError:
        print("[RED TEAM] ❌ Cannot connect to backend. Is uvicorn running?")
    except KeyboardInterrupt:
        print("\n[RED TEAM] Attack sequence aborted.")
