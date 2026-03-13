"""
Blue Team Defender AI — backend/ai_agents/blue_team.py (WebSocket version)
==========================================================================
Mirrors the architecture of scripts/blue_team.py but communicates with the
backend engine via WebSocket instead of REST polling.

Architecture:
  Layer 1 — Expert System  (PROLOG-style production rules)
  Layer 2 — Minimax + Alpha-Beta pruning (proactive defense)
  Layer 3 — Execution via WebSocket send
"""

import asyncio
import websockets
import json

# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 1 — KNOWLEDGE BASE  (PROLOG-style Production Rules)
# ══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = [
    {
        "id": "R1",
        "desc": "Database under attack — emergency countermeasure",
        "condition": lambda n: n.get("is_database") and n["status"] != "SECURE",
        "action": "patch",
        "severity": 10,
    },
    {
        "id": "R2",
        "desc": "Node has ROOT_ACCESS — full patch required",
        "condition": lambda n: n["status"] == "ROOT_ACCESS",
        "action": "patch",
        "severity": 9,
    },
    {
        "id": "R3",
        "desc": "Port scan rate > 50/sec — block entry port",
        "condition": lambda n: n.get("scan_rate", 0) > 50,
        "action": "block_port",
        "port_selector": lambda n: 22 if n["os"] in ("Linux",) or n.get("is_database") else 3389,
        "severity": 8,
    },
    {
        "id": "R4",
        "desc": "Node COMPROMISED — full patch",
        "condition": lambda n: n["status"] == "COMPROMISED",
        "action": "patch",
        "severity": 7,
    },
    {
        "id": "R5",
        "desc": "Node EXPOSED — kill malicious process",
        "condition": lambda n: n["status"] == "EXPOSED",
        "action": "kill_process",
        "severity": 5,
    },
    {
        "id": "R6",
        "desc": "CPU anomaly on SECURE node (early malware indicator)",
        "condition": lambda n: n.get("cpu", 0) > 80 and n["status"] == "SECURE",
        "action": "kill_process",
        "severity": 4,
    },
]

def run_expert_system(nodes: dict) -> list:
    """Evaluates all rules vs all nodes. Returns alerts sorted by severity desc."""
    alerts = []
    for node_id, node in nodes.items():
        for rule in KNOWLEDGE_BASE:
            if rule["condition"](node):
                alerts.append((rule["severity"], rule["id"], rule, node_id, node))
    alerts.sort(key=lambda x: x[0], reverse=True)
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 2 — MINIMAX WITH ALPHA-BETA PRUNING
# ══════════════════════════════════════════════════════════════════════════════

STATUS_SCORE  = {"SECURE": 10, "EXPOSED": 5, "COMPROMISED": 2, "ROOT_ACCESS": -5}
DB_WEIGHT     = 3
MINIMAX_DEPTH = 3

def evaluate(state: dict, db_nodes: set) -> int:
    return sum(
        STATUS_SCORE.get(status, 0) * (DB_WEIGHT if nid in db_nodes else 1)
        for nid, status in state.items()
    )

RED_KILL_CHAIN = {"SECURE": "EXPOSED", "EXPOSED": "COMPROMISED", "COMPROMISED": "ROOT_ACCESS"}

def red_successors(state: dict) -> list:
    result = []
    for nid, status in state.items():
        if status in RED_KILL_CHAIN:
            s = dict(state); s[nid] = RED_KILL_CHAIN[status]
            result.append((nid, s))
    return result

def blue_successors(state: dict) -> list:
    result = []
    for nid, status in state.items():
        if status != "SECURE":
            s = dict(state); s[nid] = "SECURE"
            result.append((nid, s))
    return result

def minimax(state, depth, alpha, beta, maximizing, db_nodes) -> int:
    if depth == 0:
        return evaluate(state, db_nodes)
    if maximizing:
        best = -999
        for _, succ in red_successors(state):
            val  = minimax(succ, depth-1, alpha, beta, False, db_nodes)
            best = max(best, val); alpha = max(alpha, best)
            if beta <= alpha: break
        return best
    else:
        best = 999
        for _, succ in blue_successors(state):
            val  = minimax(succ, depth-1, alpha, beta, True, db_nodes)
            best = min(best, val); beta = min(beta, best)
            if beta <= alpha: break
        return best

def find_best_preemptive_target(nodes: dict) -> str | None:
    state    = {nid: n["status"] for nid, n in nodes.items()}
    db_nodes = {nid for nid, n in nodes.items() if n.get("is_database")}
    candidates = [nid for nid, s in state.items() if s != "SECURE"]
    if not candidates:
        return None
    best_node, best_score = None, 999
    for nid in candidates:
        sim = dict(state); sim[nid] = "SECURE"
        score = minimax(sim, MINIMAX_DEPTH-1, -999, 999, True, db_nodes)
        if score < best_score:
            best_score, best_node = score, nid
    return best_node


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ASYNC AGENT LOOP
# ══════════════════════════════════════════════════════════════════════════════

async def blue_team_agent():
    uri = "ws://localhost:8000/ws/combat"

    try:
        async with websockets.connect(uri) as websocket:
            print("🔵 Blue Team AI Online. IDS monitoring active...")

            patched_this_round: set = set()

            while True:
                # ── Observe: receive server tick ──────────────────────────
                raw       = await websocket.recv()
                battlefield = json.loads(raw)
                nodes     = battlefield.get("nodes", {})

                if not nodes:
                    continue

                # ── Layer 1: Expert System ────────────────────────────────
                alerts = run_expert_system(nodes)

                if alerts:
                    patched_this_round.clear()
                    print(f"\n🔵 Expert System: {len(alerts)} alert(s)")

                    for severity, rule_id, rule, node_id, node in alerts:
                        if node_id in patched_this_round:
                            continue

                        print(f"   [RULE {rule_id} | sev={severity}] {rule['desc']} → {node_id}")
                        action = rule["action"]

                        if action == "patch":
                            cmd = {"agent": "blue", "action": "patch", "target": node_id}
                        elif action == "kill_process":
                            cmd = {"agent": "blue", "action": "kill_process", "target": node_id}
                        elif action == "block_port":
                            port = rule["port_selector"](node)
                            cmd  = {"agent": "blue", "action": "block_port",
                                    "target": node_id, "port": port}
                            print(f"   -> Blocking port {port} on {node_id}")
                        else:
                            continue

                        await websocket.send(json.dumps(cmd))
                        patched_this_round.add(node_id)
                        await asyncio.sleep(0.3)

                else:
                    # ── Layer 2: Minimax — proactive defense ───────────────
                    target = find_best_preemptive_target(nodes)
                    if target:
                        print(f"\n🔵 [MINIMAX] Network stable. Preemptive hardening → {target}")
                        cmd = {"agent": "blue", "action": "patch", "target": target}
                        await websocket.send(json.dumps(cmd))
                    else:
                        print("🔵 ✅ All nodes SECURE.")

    except ConnectionRefusedError:
        print("❌ Error: Cannot connect. Is the NET WAR backend engine running?")


if __name__ == "__main__":
    asyncio.run(blue_team_agent())
