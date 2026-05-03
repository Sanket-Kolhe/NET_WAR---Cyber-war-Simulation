"""
ARMOR Battle Simulator - scripts/simulate.py
============================================
Async Red vs Blue battle loop with parallel strike execution.

Run with: python simulate.py
"""

import asyncio
import heapq
from dataclasses import dataclass, field
from collections import deque

import httpx

API_URL = "http://localhost:8000/api"
API_KEY = "supersecret"

ATTACK_DELAY = 0.05
DEFENSE_DELAY = 0.01
TURN_PAUSE = 0.05
WIN_TURNS = 5

RED = "\033[91m"
GREEN = "\033[92m"
YEL = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RST = "\033[0m"

STATUS_ICON = {
    "SECURE": f"{GREEN}SECURE{RST}",
    "EXPOSED": f"{YEL}EXPOSED{RST}",
    "COMPROMISED": f"{YEL}COMPROMISED{RST}",
    "ROOT_ACCESS": f"{RED}ROOT_ACCESS{RST}",
}

NETWORK_GRAPH = {
    "Node_1": ["Node_2", "Node_3", "Node_4"],
    "Node_2": ["Node_1", "Node_5", "Node_6"],
    "Node_3": ["Node_1", "Node_6", "Node_7"],
    "Node_4": ["Node_1", "Node_8", "Node_9"],
    "Node_5": ["Node_2", "Node_10"],
    "Node_6": ["Node_2", "Node_3", "Node_10", "Node_11"],
    "Node_7": ["Node_3", "Node_11", "Node_12"],
    "Node_8": ["Node_4", "Node_12", "Node_13"],
    "Node_9": ["Node_4", "Node_14"],
    "Node_10": ["Node_5", "Node_6", "Node_15"],
    "Node_11": ["Node_6", "Node_7", "Node_15", "Node_16"],
    "Node_12": ["Node_7", "Node_8", "Node_16"],
    "Node_13": ["Node_8", "Node_16", "Node_17"],
    "Node_14": ["Node_9", "Node_17"],
    "Node_15": ["Node_10", "Node_11", "Node_18"],
    "Node_16": ["Node_11", "Node_12", "Node_13", "Node_18", "Node_19"],
    "Node_17": ["Node_13", "Node_14", "Node_19"],
    "Node_18": ["Node_15", "Node_16", "Node_20"],
    "Node_19": ["Node_16", "Node_17", "Node_20"],
    "Node_20": ["Node_18", "Node_19"],
}

NODE_TRAVERSAL_COST = {
    "Node_1": 10,
    "Node_2": 10,
    "Node_3": 10,
    "Node_4": 10,
    "Node_5": 5,
    "Node_6": 5,
    "Node_7": 5,
    "Node_8": 5,
    "Node_9": 5,
    "Node_10": 5,
    "Node_11": 5,
    "Node_12": 5,
    "Node_13": 5,
    "Node_14": 5,
    "Node_15": 2,
    "Node_16": 2,
    "Node_17": 2,
    "Node_18": 2,
    "Node_19": 2,
    "Node_20": 0,
}

STATUS_COST_MULTIPLIER = {
    "SECURE": 1.0,
    "EXPOSED": 0.65,
    "COMPROMISED": 0.35,
    "ROOT_ACCESS": 0.15,
}

DETECTION_PENALTY = {
    "SECURE": 0.0,
    "EXPOSED": 0.6,
    "COMPROMISED": 1.0,
    "ROOT_ACCESS": 0.2,
}

DATABASE_NODE = "Node_20"


def _compute_shortest_hops(goal: str = DATABASE_NODE) -> dict[str, int]:
    distances = {goal: 0}
    queue = deque([goal])
    while queue:
        current = queue.popleft()
        for neighbor in NETWORK_GRAPH.get(current, []):
            if neighbor not in distances:
                distances[neighbor] = distances[current] + 1
                queue.append(neighbor)
    return distances


SHORTEST_HOPS_TO_DB = _compute_shortest_hops()

RULES = [
    {
        "id": "R1",
        "sev": 10,
        "desc": "Database breached - emergency patch",
        "cond": lambda n: n.get("is_database", False)
        and n["status"] in ("COMPROMISED", "ROOT_ACCESS"),
        "act": "patch",
    },
    {
        "id": "R2",
        "sev": 9,
        "desc": "ROOT_ACCESS - full patch",
        "cond": lambda n: n["status"] == "ROOT_ACCESS",
        "act": "patch",
    },
    {
        "id": "R3",
        "sev": 8,
        "desc": "Port scan surge >50/s",
        "cond": lambda n: n.get("scan_rate", 0) > 50,
        "act": "block_port",
    },
    {
        "id": "R4",
        "sev": 7,
        "desc": "Node COMPROMISED",
        "cond": lambda n: n["status"] == "COMPROMISED",
        "act": "patch",
    },
    {
        "id": "R5",
        "sev": 5,
        "desc": "Node EXPOSED",
        "cond": lambda n: n["status"] == "EXPOSED",
        "act": "kill_process",
    },
]


@dataclass
class RuntimeState:
    blue_budget: int = 100
    attack_counts: dict[str, int] = field(default_factory=dict)


def print_board(nodes: list[dict]):
    print(f"\n{CYAN}{'-' * 58}{RST}")
    print(f"{BOLD}  {'NODE':<16} {'OS':<10} {'STATUS':<22} CPU{RST}")
    print(f"{CYAN}{'-' * 58}{RST}")
    for node in nodes:
        icon = STATUS_ICON.get(node["status"], node["status"])
        db_tag = " DB" if node["os_type"] == "Database" else ""
        print(f"  {node['id']:<16} {node['os_type']:<10} {icon:<22}  {node['cpu_usage']:>3}%{db_tag}")
    print(f"{CYAN}{'-' * 58}{RST}\n")


def rprint(msg: str):
    print(f"{RED}  [RED ] {msg}{RST}")


def bprint(msg: str):
    print(f"{CYAN}  [BLUE] {msg}{RST}")


def info(msg: str):
    print(f"           {msg}")


async def get_nodes(client: httpx.AsyncClient) -> list[dict]:
    response = await client.get(f"{API_URL}/nodes")
    response.raise_for_status()
    return response.json()


async def scan_from(client: httpx.AsyncClient, start_node: str) -> dict:
    response = await client.post(f"{API_URL}/scan", json={"start_node": start_node})
    response.raise_for_status()
    return response.json()


def compute_vulnerability(node: dict) -> float:
    """Higher vulnerability means cheaper exploitation."""
    os_vuln = {"Linux": 1.2, "Windows": 1.0, "Database": 0.8}
    status_bonus = {"SECURE": 1.0, "EXPOSED": 1.4, "COMPROMISED": 2.0, "ROOT_ACCESS": 3.0}

    os_type = node.get("os_type", "Windows")
    base = os_vuln.get(os_type, 1.0)
    ports = node.get("ports", [])
    port_factor = len(ports) / 3.0 if ports else 1.0
    status_factor = status_bonus.get(node.get("status", "SECURE"), 1.0)

    return max(0.1, base * port_factor * status_factor)


def compute_step_cost(node_id: str, node: dict) -> float:
    base_cost = NODE_TRAVERSAL_COST.get(node_id, 5)
    status = node.get("status", "SECURE")
    return max(0.1, (base_cost * STATUS_COST_MULTIPLIER.get(status, 1.0)) + DETECTION_PENALTY.get(status, 0.0))


def compute_hop_distance(node_id: str, goal: str = DATABASE_NODE) -> int:
    return SHORTEST_HOPS_TO_DB.get(node_id, 999)


def astar_attack_path(nodes_list: list[dict], start: str, goal: str = DATABASE_NODE) -> tuple[list[str], float]:
    """Return the optimal path and final accumulated cost for the current graph state."""
    nodes_by_id = {node["id"]: node for node in nodes_list}
    if start not in nodes_by_id or goal not in nodes_by_id:
        return [start], float("inf")
    if start == goal:
        return [start], 0.0

    open_set: list[tuple[float, int, str, list[str], float]] = []
    counter = 0
    heapq.heappush(open_set, (compute_hop_distance(start, goal), counter, start, [start], 0.0))
    best_costs: dict[str, float] = {start: 0.0}

    while open_set:
        _, _, current, path, g_cost = heapq.heappop(open_set)
        if current == goal:
            return path, g_cost

        for neighbor in NETWORK_GRAPH.get(current, []):
            if neighbor not in nodes_by_id:
                continue

            neighbor_node = nodes_by_id[neighbor]
            new_g = g_cost + compute_step_cost(neighbor, neighbor_node)
            if new_g >= best_costs.get(neighbor, float("inf")):
                continue

            best_costs[neighbor] = new_g
            counter += 1
            heapq.heappush(
                open_set,
                (new_g + compute_hop_distance(neighbor, goal), counter, neighbor, path + [neighbor], new_g),
            )

    return [start], float("inf")


def choose_best_attack_path(nodes: list[dict]) -> tuple[list[str], float, str]:
    nodes_by_id = {node["id"]: node for node in nodes}
    footholds = [node["id"] for node in nodes if node["status"] in ("EXPOSED", "COMPROMISED", "ROOT_ACCESS")]
    if "Node_1" not in footholds:
        footholds.insert(0, "Node_1")

    best_path = ["Node_1"]
    best_cost = float("inf")
    best_start = "Node_1"

    for start in dict.fromkeys(footholds):
        if start not in nodes_by_id:
            continue
        path, cost = astar_attack_path(nodes, start=start, goal=DATABASE_NODE)
        if cost < best_cost:
            best_path, best_cost, best_start = path, cost, start

    return best_path, best_cost, best_start


def path_breakdown(path: list[str], nodes_by_id: dict[str, dict]) -> list[dict]:
    report = []
    running_g = 0.0
    for index, node_id in enumerate(path):
        node = nodes_by_id.get(node_id, {})
        if index > 0:
            running_g += compute_step_cost(node_id, node)
        h = compute_hop_distance(node_id)
        report.append(
            {
                "node_id": node_id,
                "status": node.get("status", "UNKNOWN"),
                "g": round(running_g, 2),
                "h": h,
                "f": round(running_g + h, 2),
            }
        )
    return report


async def apply_a_star_kill_chain(
    client: httpx.AsyncClient,
    state: RuntimeState,
    owned_nodes: set[str],
    nodes: list[dict],
    path: list[str],
) -> tuple[bool, set[str]]:
    nodes_by_id = {node["id"]: node for node in nodes}
    if len(path) < 2:
        return False, owned_nodes

    for index in range(1, len(path)):
        target_id = path[index]
        target = nodes_by_id.get(target_id)
        if not target:
            continue

        pivot_id = path[index - 1]
        if target["status"] == "ROOT_ACCESS":
            continue

        if target["status"] == "SECURE":
            rprint(f"A* selected {target_id} as a secure target; scanning from {pivot_id} to expose it.")
            await scan_from(client, pivot_id)
            nodes = await get_nodes(client)
            nodes_by_id = {node["id"]: node for node in nodes}
            target = nodes_by_id.get(target_id, target)

        won, owned_nodes = await attack_node(client, state, owned_nodes, target, pivot_id)
        if won:
            return True, owned_nodes

        refreshed_nodes = await get_nodes(client)
        refreshed_by_id = {node["id"]: node for node in refreshed_nodes}
        refreshed_target = refreshed_by_id.get(target_id, target)
        if refreshed_target.get("status") == "COMPROMISED":
            won, owned_nodes = await attack_node(client, state, owned_nodes, refreshed_target, pivot_id)
            if won:
                return True, owned_nodes

        # Replan each turn after a single chain step; Blue may have altered the graph.
        return False, owned_nodes

    return False, owned_nodes


async def attack_node(
    client: httpx.AsyncClient,
    state: RuntimeState,
    owned_nodes: set[str],
    target: dict,
    pivot: str,
) -> tuple[bool, set[str]]:
    node_id = target["id"]
    status = target["status"]

    state.attack_counts[node_id] = state.attack_counts.get(node_id, 0) + 1
    burnout = state.attack_counts[node_id]

    desc = "EXPLOIT -> COMPROMISED" if status == "EXPOSED" else "ESCALATE -> ROOT_ACCESS"
    rprint(f"[pivot:{pivot}] {node_id} - {desc} (Attempts: {burnout}/3)")

    await asyncio.sleep(ATTACK_DELAY)
    response = await client.post(f"{API_URL}/attack", json={"target_node_id": node_id})
    response.raise_for_status()
    payload = response.json()

    if not payload.get("success"):
        return False, owned_nodes

    new_status = payload.get("new_status", "?")
    rprint(f"  -> {node_id} now {new_status}")

    if new_status == "ROOT_ACCESS":
        owned_nodes = owned_nodes | {node_id}
        rprint(f"  -> {node_id} OWNED (hop_to_db={compute_hop_distance(node_id)}, total={len(owned_nodes)})")
        scan_payload = await scan_from(client, node_id)
        exposed = scan_payload.get("exposed_this_scan", [])
        rprint(f"  -> New targets exposed: {exposed}")

        if target.get("is_database", False):
            return True, owned_nodes

    return False, owned_nodes


async def red_team_turn(
    client: httpx.AsyncClient,
    state: RuntimeState,
    nodes: list[dict],
    owned_nodes: set[str],
) -> tuple[bool, set[str]]:
    path, path_cost, start = choose_best_attack_path(nodes)
    nodes_by_id = {node["id"]: node for node in nodes}

    if len(path) < 2 or path_cost == float("inf"):
        rprint("A* could not find a viable route; falling back to reconnaissance from Node_1.")
        bfs_payload = await scan_from(client, "Node_1")
        bfs = bfs_payload.get("bfs_order", [])
        rprint(f"BFS from [{bfs_payload.get('pivot', 'Node_1')}]: {' -> '.join(bfs)}")
        return False, owned_nodes

    rprint(f"A* optimal kill chain from {start}: {' -> '.join(path)}")
    rprint(f"A* total path cost: {path_cost:.2f}")
    for step in path_breakdown(path, nodes_by_id):
        rprint(
            f"  {step['node_id']}: status={step['status']} | g={step['g']:.2f} | "
            f"h={step['h']} | f={step['f']:.2f}"
        )

    red_wins, owned_nodes = await apply_a_star_kill_chain(
        client=client,
        state=state,
        owned_nodes=owned_nodes,
        nodes=nodes,
        path=path,
    )

    return red_wins, owned_nodes


async def blue_team_turn(client: httpx.AsyncClient, state: RuntimeState, nodes: list[dict]):
    if state.blue_budget <= 0:
        bprint("BLUE TEAM IS EXHAUSTED! Out of budget, turn skipped.")
        return

    alerts: list[tuple[int, dict, dict]] = []
    for node in nodes:
        for rule in RULES:
            if rule["cond"](node):
                alerts.append((rule["sev"], rule, node))
    alerts.sort(key=lambda item: item[0], reverse=True)

    if not alerts:
        secure_nodes = [node for node in nodes if node["status"] == "SECURE" and node["id"] != "Node_1"]
        if secure_nodes and state.blue_budget >= 15:
            worst = max(secure_nodes, key=lambda node: compute_hop_distance(node["id"]))
            state.blue_budget -= 15
            bprint(f"[PROACTIVE] Preemptive hardening -> {worst['id']} (-15 pts)")
            await client.post(f"{API_URL}/patch", json={"target_node_id": worst["id"]})
            info(f"  Patch -> {worst['id']}")
        else:
            bprint("All nodes SECURE. Monitoring...")
        return

    handled = set()
    for severity, rule, node in alerts:
        if len(handled) >= 1 and severity < 9:
            break

        node_id = node["id"]
        if node_id in handled:
            continue

        action = rule["act"]
        cost = 15 if action == "patch" else 10 if action == "block_port" else 5
        if state.blue_budget < cost:
            continue

        state.blue_budget -= cost
        bprint(f"[Rule {rule['id']} | sev={severity}] {rule['desc']} -> {node_id} (-{cost} pts)")

        if action == "patch":
            await client.post(f"{API_URL}/patch", json={"target_node_id": node_id})
            info(f"  Patch -> {node_id}")
        elif action == "kill_process":
            await client.post(f"{API_URL}/kill_process", json={"target_node_id": node_id})
            info(f"  Kill -> {node_id}")
        elif action == "block_port":
            port = 22 if node.get("os_type") in ("Linux", "Database") else 3389
            await client.post(f"{API_URL}/block_port", json={"target_node_id": node_id, "port": port})
            info(f"  Port {port} blocked on {node_id}")

        handled.add(node_id)
        await asyncio.sleep(DEFENSE_DELAY)


async def run_simulation():
    state = RuntimeState()
    owned_nodes: set[str] = set()
    secure_turns = 0
    turn = 0

    headers = {"X-API-Key": API_KEY}

    print(f"\n{BOLD}{CYAN}{'=' * 58}{RST}")
    print("   A.R.M.O.R  -  RED vs BLUE  (Async + Parallel Red Strikes)")
    print(f"{'=' * 58}{RST}")

    async with httpx.AsyncClient(headers=headers, timeout=15.0) as client:
        reset_response = await client.post(f"{API_URL}/reset")
        reset_response.raise_for_status()

        scan_response = await scan_from(client, "Node_1")
        print(f"BFS from Node_1: {' -> '.join(scan_response.get('bfs_order', []))}\n")

        while True:
            turn += 1
            nodes = await get_nodes(client)

            print(f"\n{BOLD}--- TURN {turn} {'-' * 42}{RST}")
            print_board(nodes)

            print(f"{BOLD}RED TEAM (parallel strikes):{RST}")
            red_wins, owned_nodes = await red_team_turn(client, state, nodes, owned_nodes)
            if red_wins:
                nodes = await get_nodes(client)
                print_board(nodes)
                print(f"\n{RED}{BOLD}RED TEAM WINS - Database compromised!{RST}\n")
                break

            await asyncio.sleep(TURN_PAUSE)
            nodes = await get_nodes(client)

            print(f"\n{BOLD}BLUE TEAM (response):{RST}")
            await blue_team_turn(client, state, nodes)

            nodes = await get_nodes(client)
            reclaimed = {
                node_id
                for node_id in owned_nodes
                if any(node["id"] == node_id and node["status"] == "SECURE" for node in nodes)
            }
            if reclaimed:
                owned_nodes -= reclaimed
                bprint(f"Reclaimed {sorted(reclaimed)}")

            await asyncio.sleep(TURN_PAUSE)

            nodes = await get_nodes(client)
            if all(node["status"] == "SECURE" for node in nodes):
                secure_turns += 1
                bprint(f"Network clean! ({secure_turns}/{WIN_TURNS})")
                if secure_turns >= WIN_TURNS:
                    print_board(nodes)
                    print(f"\n{GREEN}{BOLD}BLUE TEAM WINS - Network secured!{RST}\n")
                    break
            else:
                secure_turns = 0

            await asyncio.sleep(0.3)

    print(f"{BOLD}Simulation ended after {turn} turns.{RST}\n")


if __name__ == "__main__":
    try:
        asyncio.run(run_simulation())
    except httpx.RequestError:
        print("Backend not running. Start backend server first.")
    except KeyboardInterrupt:
        print(f"\n{BOLD}Simulation aborted.{RST}")
