"""
Blue Team Defender AI — scripts/blue_team.py (REST version)
============================================================
Architecture (unified flow on the Game Tree):

  Game Tree Node (current network state)
        │
        ▼
  [Expert System]         ← Classifies each node: HIGH / MEDIUM / LOW threat
        │
        ▼
  [Minimax + α-β]         ← Blue evaluates best defensive response
        │
        ▼
  Execute defense action

Layer 1 — Expert System (PROLOG-style Production Rules)
          Classifies threat levels and fires immediate responses.
          HIGH-threat classifications feed into Minimax's evaluation.

Layer 2 — Minimax + Alpha-Beta pruning (proactive defense)
          Searches the game tree to anticipate Red's A* moves.
          Expert System threat levels bias the evaluation function.
"""

import time
import requests

session = requests.Session()
session.headers.update({"X-API-Key": "supersecret"})

API_URL = "http://localhost:8000/api"

def print_action(msg):
    print(f"[BLUE TEAM] {msg}")


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 1 — KNOWLEDGE BASE  (PROLOG-style Production Rules)
#
#  Each rule classifies a THREAT LEVEL and triggers an action.
#  Threat levels:   HIGH (immediate response) / MEDIUM / LOW
#  HIGH threats also feed into Minimax's evaluation function.
#
#  Rules are evaluated against ALL nodes. The highest-severity match
#  fires first (priority queue ordering).
# ══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = [
    # R1: Database under ANY threat → emergency patch (highest priority)
    {
        "id": "R1",
        "desc": "Database under attack — emergency countermeasure",
        "condition": lambda n: n["os_type"] == "Database" and n["status"] != "SECURE",
        "action": "patch",
        "threat_level": "HIGH",
        "severity": 10,
    },
    # R2: Node fully owned — full patch required
    {
        "id": "R2",
        "desc": "Node has ROOT_ACCESS — full patch required",
        "condition": lambda n: n["status"] == "ROOT_ACCESS",
        "action": "patch",
        "threat_level": "HIGH",
        "severity": 9,
    },
    # R7: Privilege escalation detected — isolate node immediately
    {
        "id": "R7",
        "desc": "Privilege escalation detected — isolate node immediately",
        "condition": lambda n: n["status"] == "COMPROMISED" and n.get("scan_rate", 0) > 30,
        "action": "patch",
        "threat_level": "HIGH",
        "severity": 9,
    },
    # R3: Port scan surge > 50 pkt/s — lateral movement detected
    {
        "id": "R3",
        "desc": "Port scan rate > 50/sec — lateral movement detected → escalate to Minimax",
        "condition": lambda n: n["scan_rate"] > 50,
        "action": "block_port",
        "threat_level": "HIGH",
        "port_selector": lambda n: 22 if n["os_type"] in ("Linux", "Database") else 3389,
        "severity": 8,
    },
    # R4: Node compromised — full patch
    {
        "id": "R4",
        "desc": "Node COMPROMISED — patch to restore",
        "condition": lambda n: n["status"] == "COMPROMISED",
        "action": "patch",
        "threat_level": "MEDIUM",
        "severity": 7,
    },
    # R5: Node exposed — kill the scanning process
    {
        "id": "R5",
        "desc": "Node EXPOSED — kill malicious process",
        "condition": lambda n: n["status"] == "EXPOSED",
        "action": "kill_process",
        "threat_level": "MEDIUM",
        "severity": 5,
    },
    # R6: High CPU on a SECURE node — early warning
    {
        "id": "R6",
        "desc": "CPU anomaly on SECURE node (malware indicator)",
        "condition": lambda n: n["cpu_usage"] > 80 and n["status"] == "SECURE",
        "action": "kill_process",
        "threat_level": "LOW",
        "severity": 4,
    },
]


def _threat_rank(level: str) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}.get(level, 0)


def run_expert_system(nodes: list) -> tuple:
    """
    Evaluates ALL rules against ALL nodes.

    Returns
    -------
    alerts : list
        Sorted by severity desc: (severity, rule_id, rule, node)
    threat_levels : dict
        { node_id: "HIGH" / "MEDIUM" / "LOW" } — fed into Minimax evaluate()
    """
    alerts = []
    threat_levels = {}

    for node in nodes:
        for rule in KNOWLEDGE_BASE:
            if rule["condition"](node):
                alerts.append((rule["severity"], rule["id"], rule, node))
                # Keep the highest threat level per node
                nid = node["id"]
                current = threat_levels.get(nid)
                rule_level = rule["threat_level"]
                if current is None or _threat_rank(rule_level) > _threat_rank(current):
                    threat_levels[nid] = rule_level

    alerts.sort(key=lambda x: x[0], reverse=True)
    return alerts, threat_levels


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 2 — MINIMAX WITH ALPHA-BETA PRUNING  (Proactive Defense)
#
#  Game model:
#    State  — simplified dict { node_id: status }
#    Red    — MAXIMIZER: tries to get as many nodes to ROOT_ACCESS as possible
#    Blue   — MINIMIZER: tries to keep as many nodes SECURE as possible
#    Depth  — 3 plies (Blue looks 3 moves ahead)
#
#  evaluate(state):
#    eval(n) = w1 × (assets_compromised)
#            − w2 × (defenses_triggered)
#            + w3 × (privilege_level_gained)
#
#  Expert System threat_levels modify the evaluation weights:
#    HIGH-threat nodes get an extra penalty → Minimax prioritizes defending them.
#
#  Complexity: O(b^(m/2)) with alpha-beta pruning (best case)
#              vs O(b^m) without pruning
# ══════════════════════════════════════════════════════════════════════════════

STATUS_SCORE  = {"SECURE": 10, "EXPOSED": 5, "COMPROMISED": 2, "ROOT_ACCESS": -5}
DB_WEIGHT     = 3    # database node counts 3× in the evaluation
MINIMAX_DEPTH = 3

THREAT_PENALTY = {"HIGH": -4, "MEDIUM": -2, "LOW": 0}


def evaluate(state: dict, db_nodes: set, threat_levels: dict = None) -> int:
    """
    Heuristic score for a game-tree node (network state snapshot).

    Higher score = better for Blue (more nodes SECURE).
    Expert System threat_levels bias the score so HIGH-threat nodes
    are weighted more heavily.
    """
    score = 0
    for node_id, status in state.items():
        weight = DB_WEIGHT if node_id in db_nodes else 1
        base = STATUS_SCORE.get(status, 0) * weight

        # Expert System integration: threat level adjusts the score
        if threat_levels and node_id in threat_levels:
            base += THREAT_PENALTY.get(threat_levels[node_id], 0)

        score += base
    return score


# ── Red move generator ─────────────────────────────────────────────────────
RED_KILL_CHAIN = {"SECURE": "EXPOSED", "EXPOSED": "COMPROMISED",
                  "COMPROMISED": "ROOT_ACCESS"}

def red_successors(state: dict) -> list:
    """All states reachable by one Red Team move (game tree edges)."""
    successors = []
    for node_id, status in state.items():
        if status in RED_KILL_CHAIN:
            new_state = dict(state)
            new_state[node_id] = RED_KILL_CHAIN[status]
            successors.append((node_id, new_state))
    return successors


# ── Blue move generator ────────────────────────────────────────────────────
def blue_successors(state: dict) -> list:
    """All states reachable by one Blue Team move (game tree edges)."""
    successors = []
    for node_id, status in state.items():
        if status != "SECURE":
            new_state = dict(state)
            new_state[node_id] = "SECURE"
            successors.append((node_id, new_state))
    return successors


# ── Minimax core ───────────────────────────────────────────────────────────
def minimax(state: dict, depth: int, alpha: int, beta: int,
            is_maximizing: bool, db_nodes: set,
            threat_levels: dict = None) -> int:
    """
    Minimax with Alpha-Beta pruning over the game tree.

    Red  = maximizer (wants to maximize damage)
    Blue = minimizer (wants to minimize damage)

    Alpha-Beta pruning cuts branches that won't affect the outcome:
    - β cut-off: Blue already has a better option → prune Red's branch
    - α cut-off: Red already has a better option → prune Blue's branch

    Complexity: O(b^(m/2)) best case vs O(b^m) without pruning
    """
    if depth == 0:
        return evaluate(state, db_nodes, threat_levels)

    if is_maximizing:
        # Red Team's turn — pick the move that hurts Blue the most
        best = -999
        for _, succ in red_successors(state):
            val = minimax(succ, depth - 1, alpha, beta, False, db_nodes,
                          threat_levels)
            best = max(best, val)
            alpha = max(alpha, best)
            if beta <= alpha:
                break   # β cut-off — prune this branch
        return best
    else:
        # Blue Team's turn — pick the move that limits Red the most
        best = 999
        for _, succ in blue_successors(state):
            val = minimax(succ, depth - 1, alpha, beta, True, db_nodes,
                          threat_levels)
            best = min(best, val)
            beta = min(beta, best)
            if beta <= alpha:
                break   # α cut-off — prune this branch
        return best


def find_best_preemptive_target(nodes: list, threat_levels: dict = None) -> str | None:
    """
    Runs Minimax from Blue's perspective to find the node that,
    if proactively hardened NOW, minimizes the worst-case future damage.

    Expert System threat_levels are passed through to evaluate() so
    that HIGH-threat nodes are weighted more heavily in the search.
    """
    state    = {n["id"]: n["status"] for n in nodes}
    db_nodes = {n["id"] for n in nodes if n["os_type"] == "Database"}

    candidates = [n["id"] for n in nodes if n["status"] != "SECURE"]
    if not candidates:
        return None

    best_node, best_score = None, 999

    for node_id in candidates:
        simulated = dict(state)
        simulated[node_id] = "SECURE"
        score = minimax(simulated, MINIMAX_DEPTH - 1, -999, 999, True, db_nodes,
                        threat_levels)
        if score < best_score:
            best_score, best_node = score, node_id

    return best_node


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 3 — EXECUTION  (sends commands to the backend)
# ══════════════════════════════════════════════════════════════════════════════

def execute_action(rule: dict, node: dict):
    """Executes the Blue Team action specified by the rule."""
    node_id = node["id"]
    action  = rule["action"]

    if action == "patch":
        r = session.post(f"{API_URL}/patch", json={"target_node_id": node_id})
        status = "✅" if r.status_code == 200 else "❌"
        print_action(f"  📦 Patch {status} → {node_id}")

    elif action == "kill_process":
        r = session.post(f"{API_URL}/kill_process", json={"target_node_id": node_id})
        status = "✅" if r.status_code == 200 else "❌"
        print_action(f"  🔪 Kill {status} → {node_id}")

    elif action == "block_port":
        port = rule["port_selector"](node)
        r = session.post(f"{API_URL}/block_port",
                          json={"target_node_id": node_id, "port": port})
        status = "✅" if r.status_code == 200 else "❌"
        print_action(f"  🔒 Block port {port} {status} → {node_id}")


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════

def run_defender_ai():
    print_action("Initializing IDS (Intrusion Detection System)...")
    print_action(f"Knowledge Base loaded: {len(KNOWLEDGE_BASE)} production rules")
    print_action(f"Minimax depth: {MINIMAX_DEPTH} plies with Alpha-Beta pruning")
    print_action(f"Evaluation: STATUS_SCORE={STATUS_SCORE}, DB_WEIGHT={DB_WEIGHT}×")
    print_action("WIN condition : All nodes SECURE for 5 consecutive polls")
    print_action("LOSE condition: Database reaches ROOT_ACCESS\n")

    patched_this_round: set = set()
    secure_streak = 0
    WIN_STREAK_NEEDED = 5

    while True:
        try:
            # ── Observe ─────────────────────────────────────────────────────
            response = session.get(f"{API_URL}/nodes")
            if response.status_code != 200:
                print_action("Failed to fetch node states.")
                time.sleep(1)
                continue

            nodes = response.json()

            # ── Check lose condition ────────────────────────────────────────
            db = next((n for n in nodes if n["os_type"] == "Database"), None)
            if db and db["status"] == "ROOT_ACCESS":
                print_action("\n💀 BLUE TEAM LOSES — Database has been fully compromised!")
                print_action("   RED TEAM wins. Simulation over.")
                break

            # ── Layer 1: Expert System — classify threats + respond ─────────
            alerts, threat_levels = run_expert_system(nodes)

            if alerts:
                secure_streak = 0
                print_action(f"⚠️  Expert System: {len(alerts)} alert(s) detected")

                # Log threat classifications
                if threat_levels:
                    high = [nid for nid, lvl in threat_levels.items() if lvl == "HIGH"]
                    med  = [nid for nid, lvl in threat_levels.items() if lvl == "MEDIUM"]
                    if high:
                        print_action(f"   [THREAT MAP] HIGH: {high}")
                    if med:
                        print_action(f"   [THREAT MAP] MEDIUM: {med}")

                patched_this_round.clear()

                for severity, rule_id, rule, node in alerts:
                    node_id = node["id"]
                    if node_id in patched_this_round:
                        continue

                    threat = rule.get("threat_level", "MEDIUM")
                    print_action(
                        f"[RULE {rule_id} FIRED | sev={severity} | {threat}] "
                        f"{rule['desc']} → {node_id} ({node['ip_address']})"
                    )
                    execute_action(rule, node)
                    patched_this_round.add(node_id)
                    time.sleep(0.2)

            else:
                # ── Layer 2: Minimax + α-β — proactive defense ──────────────
                # threat_levels from Expert System feed into evaluate()
                target = find_best_preemptive_target(nodes, threat_levels)
                if target:
                    print_action(f"[MINIMAX + α-β] Network stable. "
                                 f"Preemptive hardening → {target}")
                    if threat_levels:
                        print_action(f"   (threat context: {threat_levels})")
                    r = session.post(f"{API_URL}/patch",
                                      json={"target_node_id": target})
                    status = "✅" if r.status_code == 200 else "❌"
                    print_action(f"[MINIMAX] Preemptive patch {status} on {target}")
                    secure_streak = 0
                else:
                    secure_streak += 1
                    print_action(f"✅ All nodes SECURE. "
                                 f"({secure_streak}/{WIN_STREAK_NEEDED} clean polls)")
                    if secure_streak >= WIN_STREAK_NEEDED:
                        print_action("\n🏆 BLUE TEAM WINS — Network fully secured!")
                        print_action("   All nodes SECURE. Red Team has been repelled.")
                        break

        except requests.exceptions.ConnectionError:
            print_action("❌ Connection to ARMOR Command Server lost. Retrying in 3s...")
            time.sleep(3)
            continue

        time.sleep(1)


if __name__ == "__main__":
    try:
        run_defender_ai()
    except KeyboardInterrupt:
        print("\n[BLUE TEAM] Defense sequence aborted.")
