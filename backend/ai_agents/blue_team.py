"""
Blue Team Defender AI — backend/ai_agents/blue_team.py (WebSocket version)
==========================================================================
Architecture (unified flow on the Game Tree):

  Game Tree Node (current network state)
        │
        ▼
  [Expert System]         ← Classifies each node (HIGH / MEDIUM / LOW threat)
        │
        ▼
  [Minimax + α-β]         ← Blue evaluates best defensive response
        │
        ▼
  Execute defense action

Layer 1 — Expert System (PROLOG-style production rules)
          Classifies threat levels and fires immediate responses.
          HIGH-threat classifications feed into Minimax's evaluation.

Layer 2 — Minimax + Alpha-Beta pruning (proactive defense)
          Searches the game tree to anticipate Red's A* moves.
          Expert System threat levels bias the evaluation function.
"""

import asyncio
import websockets
import json
from engine.game_tree import (
    evaluate, minimax, find_best_defensive_move,
    red_successors, blue_successors,
    STATUS_SCORE, DB_WEIGHT, MINIMAX_DEPTH,
)


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 1 — KNOWLEDGE BASE  (PROLOG-style Production Rules)
#
#  Each rule classifies a THREAT LEVEL and triggers an action.
#  Threat levels:   HIGH (immediate response) / MEDIUM / LOW
#  HIGH threats also feed into Minimax's evaluation function.
# ══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = [
    {
        "id": "R1",
        "desc": "Database under attack — emergency countermeasure",
        "condition": lambda n: n.get("is_database") and n["status"] != "SECURE",
        "action": "patch",
        "threat_level": "HIGH",
        "severity": 10,
    },
    {
        "id": "R2",
        "desc": "Node has ROOT_ACCESS — full patch required",
        "condition": lambda n: n["status"] == "ROOT_ACCESS",
        "action": "patch",
        "threat_level": "HIGH",
        "severity": 9,
    },
    {
        "id": "R3",
        "desc": "Port scan rate > 50/sec — lateral movement detected → escalate to Minimax",
        "condition": lambda n: n.get("scan_rate", 0) > 50,
        "action": "block_port",
        "threat_level": "HIGH",
        "port_selector": lambda n: 22 if n["os"] in ("Linux",) or n.get("is_database") else 3389,
        "severity": 8,
    },
    {
        "id": "R4",
        "desc": "Node COMPROMISED — full patch",
        "condition": lambda n: n["status"] == "COMPROMISED",
        "action": "patch",
        "threat_level": "MEDIUM",
        "severity": 7,
    },
    {
        "id": "R5",
        "desc": "Node EXPOSED — kill malicious process",
        "condition": lambda n: n["status"] == "EXPOSED",
        "action": "kill_process",
        "threat_level": "MEDIUM",
        "severity": 5,
    },
    {
        "id": "R6",
        "desc": "CPU anomaly on SECURE node (early malware indicator)",
        "condition": lambda n: n.get("cpu", 0) > 80 and n["status"] == "SECURE",
        "action": "kill_process",
        "threat_level": "LOW",
        "severity": 4,
    },
    {
        "id": "R7",
        "desc": "Privilege escalation detected — isolate node immediately",
        "condition": lambda n: n["status"] == "COMPROMISED" and n.get("scan_rate", 0) > 30,
        "action": "patch",
        "threat_level": "HIGH",
        "severity": 9,
    },
]


def run_expert_system(nodes: dict) -> tuple:
    """
    Evaluates all rules vs all nodes.

    Returns
    -------
    alerts : list
        Sorted by severity desc: (severity, rule_id, rule, node_id, node)
    threat_levels : dict
        { node_id: "HIGH" / "MEDIUM" / "LOW" } — fed into Minimax evaluate()
    """
    alerts = []
    threat_levels = {}

    for node_id, node in nodes.items():
        for rule in KNOWLEDGE_BASE:
            if rule["condition"](node):
                alerts.append((rule["severity"], rule["id"], rule, node_id, node))
                # Keep the highest threat level per node
                current = threat_levels.get(node_id)
                rule_level = rule["threat_level"]
                if current is None or _threat_rank(rule_level) > _threat_rank(current):
                    threat_levels[node_id] = rule_level

    alerts.sort(key=lambda x: x[0], reverse=True)
    return alerts, threat_levels


def _threat_rank(level: str) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(level, 0)


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ASYNC AGENT LOOP
#
#  Flow per tick:
#    1. Receive network state from server
#    2. Expert System classifies threat levels
#    3. If alerts → execute immediate responses
#    4. Expert System threat_levels feed into Minimax evaluate()
#    5. If no alerts → Minimax finds best preemptive target
# ══════════════════════════════════════════════════════════════════════════════

async def blue_team_agent():
    uri = "ws://localhost:8000/ws/combat"

    try:
        async with websockets.connect(uri) as websocket:
            print("🔵 Blue Team AI Online. IDS monitoring active.")
            print("🔵 Architecture: Expert System → Minimax + α-β Pruning")
            print(f"🔵 Minimax depth: {MINIMAX_DEPTH} plies | Eval weights: {STATUS_SCORE}")
            print(f"🔵 Database weight: {DB_WEIGHT}×\n")

            patched_this_round: set = set()

            while True:
                # ── Observe: receive server tick ──────────────────────────
                raw = await websocket.recv()
                battlefield = json.loads(raw)
                nodes = battlefield.get("nodes", {})

                if not nodes:
                    continue

                # ── Layer 1: Expert System — classify + respond ──────────
                alerts, threat_levels = run_expert_system(nodes)

                if alerts:
                    patched_this_round.clear()
                    print(f"\n🔵 Expert System: {len(alerts)} alert(s)")

                    # Log threat classifications
                    if threat_levels:
                        high_threats = [nid for nid, lvl in threat_levels.items() if lvl == "HIGH"]
                        if high_threats:
                            print(f"🔵 [THREAT MAP] HIGH: {high_threats}")

                    for severity, rule_id, rule, node_id, node in alerts:
                        if node_id in patched_this_round:
                            continue

                        threat = rule.get("threat_level", "MEDIUM")
                        print(f"   [RULE {rule_id} | sev={severity} | {threat}] "
                              f"{rule['desc']} → {node_id}")

                        action = rule["action"]

                        if action == "patch":
                            cmd = {"agent": "blue", "action": "patch", "target": node_id}
                        elif action == "kill_process":
                            cmd = {"agent": "blue", "action": "kill_process", "target": node_id}
                        elif action == "block_port":
                            port = rule["port_selector"](node)
                            cmd = {"agent": "blue", "action": "block_port",
                                   "target": node_id, "port": port}
                            print(f"   → Blocking port {port} on {node_id}")
                        else:
                            continue

                        await websocket.send(json.dumps(cmd))
                        patched_this_round.add(node_id)
                        await asyncio.sleep(0.3)

                else:
                    # ── Layer 2: Minimax + α-β — proactive defense ────────
                    # threat_levels from Expert System feed into evaluate()
                    target = find_best_defensive_move(nodes, threat_levels)
                    if target:
                        print(f"\n🔵 [MINIMAX + α-β] Network stable. "
                              f"Preemptive hardening → {target}")
                        print(f"   (threat context: {threat_levels or 'none'})")
                        cmd = {"agent": "blue", "action": "patch", "target": target}
                        await websocket.send(json.dumps(cmd))
                    else:
                        print("🔵 ✅ All nodes SECURE. Network defended.")

    except ConnectionRefusedError:
        print("❌ Error: Cannot connect. Is the NET WAR backend engine running?")


if __name__ == "__main__":
    asyncio.run(blue_team_agent())
