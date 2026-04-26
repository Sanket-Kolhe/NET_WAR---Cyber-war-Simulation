"""
ARMOR Battle Simulator - scripts/simulate.py
============================================
Async Red vs Blue battle loop with parallel strike execution.

Run with: python simulate.py
"""

import asyncio
from dataclasses import dataclass, field

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

DEPTH = {
    "Node_1": 0,
    "Node_2": 1,
    "Node_3": 1,
    "Node_4": 1,
    "Node_5": 2,
    "Node_6": 2,
    "Node_7": 2,
    "Node_8": 2,
    "Node_9": 2,
    "Node_10": 3,
    "Node_11": 3,
    "Node_12": 3,
    "Node_13": 3,
    "Node_14": 3,
    "Node_15": 4,
    "Node_16": 4,
    "Node_17": 4,
    "Node_18": 5,
    "Node_19": 5,
    "Node_20": 6,
}


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
        rprint(f"  -> {node_id} OWNED (depth={DEPTH.get(node_id, 0)}, total={len(owned_nodes)})")
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
    pivot = max(owned_nodes, key=lambda nid: DEPTH.get(nid, 0)) if owned_nodes else "Node_1"

    db_targets = [
        node
        for node in nodes
        if node.get("is_database", False)
        and node["status"] in ("EXPOSED", "COMPROMISED")
        and state.attack_counts.get(node["id"], 0) < 3
    ]

    compromised = sorted(
        [
            node
            for node in nodes
            if node["status"] == "COMPROMISED"
            and not node.get("is_database", False)
            and state.attack_counts.get(node["id"], 0) < 3
        ],
        key=lambda node: DEPTH.get(node["id"], 0),
        reverse=True,
    )

    exposed = sorted(
        [
            node
            for node in nodes
            if node["status"] == "EXPOSED"
            and not node.get("is_database", False)
            and state.attack_counts.get(node["id"], 0) < 3
        ],
        key=lambda node: DEPTH.get(node["id"], 0),
        reverse=True,
    )

    if not db_targets and not compromised and not exposed:
        label = f"{pivot} (foothold)" if pivot != "Node_1" else "Node_1 (internet)"
        rprint(f"No targets. Pivot BFS from {label}...")
        bfs_payload = await scan_from(client, pivot)
        bfs = bfs_payload.get("bfs_order", [])
        rprint(f"BFS from [{bfs_payload.get('pivot', pivot)}]: {' -> '.join(bfs)}")
        return False, owned_nodes

    strike_targets: list[dict] = []

    if db_targets and db_targets[0]["status"] == "COMPROMISED":
        strike_targets.append(db_targets[0])
    elif compromised:
        strike_targets.append(compromised[0])

    skip_ids = {target["id"] for target in strike_targets}

    fresh_exposed = [node for node in exposed if node["id"] not in skip_ids]
    if db_targets and db_targets[0]["status"] == "EXPOSED" and db_targets[0]["id"] not in skip_ids:
        strike_targets.append(db_targets[0])
    elif fresh_exposed:
        strike_targets.append(fresh_exposed[0])

    if not strike_targets:
        return False, owned_nodes

    tasks = [attack_node(client, state, owned_nodes, target, pivot) for target in strike_targets[:2]]
    results = await asyncio.gather(*tasks)

    red_wins = False
    for won, updated_owned in results:
        owned_nodes = owned_nodes | updated_owned
        red_wins = red_wins or won

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
            worst = min(secure_nodes, key=lambda node: DEPTH.get(node["id"], 99))
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
