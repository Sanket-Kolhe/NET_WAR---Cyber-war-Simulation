"""
Blue Team Defender AI — scripts/blue_team.py
=============================================
Architecture: Reactive Agent with two AI layers

  Layer 1 — Expert System (PROLOG-style Production Rules)
            Reads live network state and fires IF→THEN rules to detect
            and respond to active threats.

  Layer 2 — Minimax + Alpha-Beta Pruning
            Looks ahead in the game tree, predicts where Red Team will
            strike next, and preemptively hardens the best target node.
"""

import time
import requests

API_URL = "http://localhost:8000/api"

# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 1 — KNOWLEDGE BASE  (PROLOG-style Production Rules)
#
#  Each rule is a dict:
#    id        – rule identifier (for logging)
#    desc      – human-readable description
#    condition – lambda(node_dict) → bool
#    action    – "patch" | "kill_process" | "block_port"
#    port      – port to block (only used when action == "block_port")
#    severity  – 0–10; higher = fires first
# ══════════════════════════════════════════════════════════════════════════════

KNOWLEDGE_BASE = [
    # R1: Database under ANY threat → emergency patch (highest priority)
    {
        "id": "R1",
        "desc": "Database under attack — emergency countermeasure",
        "condition": lambda n: n["os_type"] == "Database" and n["status"] != "SECURE",
        "action": "patch",
        "severity": 10,
    },
    # R2: Node fully owned — full patch required
    {
        "id": "R2",
        "desc": "Node has ROOT_ACCESS — full patch required",
        "condition": lambda n: n["status"] == "ROOT_ACCESS",
        "action": "patch",
        "severity": 9,
    },
    # R3: Port scan surge > 50 pkt/s — block attack-vector port
    {
        "id": "R3",
        "desc": "Port scan rate > 50/sec — block SSH/RDP entry port",
        "condition": lambda n: n["scan_rate"] > 50,
        "action": "block_port",
        "port_selector": lambda n: 22 if n["os_type"] in ("Linux", "Database") else 3389,
        "severity": 8,
    },
    # R4: Node compromised — full patch
    {
        "id": "R4",
        "desc": "Node COMPROMISED — patch to restore",
        "condition": lambda n: n["status"] == "COMPROMISED",
        "action": "patch",
        "severity": 7,
    },
    # R5: Node exposed — kill the scanning process (cheaper than patch)
    {
        "id": "R5",
        "desc": "Node EXPOSED — kill malicious process",
        "condition": lambda n: n["status"] == "EXPOSED",
        "action": "kill_process",
        "severity": 5,
    },
    # R6: High CPU on a SECURE node — early warning, kill process
    {
        "id": "R6",
        "desc": "CPU anomaly on SECURE node (malware indicator)",
        "condition": lambda n: n["cpu_usage"] > 80 and n["status"] == "SECURE",
        "action": "kill_process",
        "severity": 4,
    },
]

def run_expert_system(nodes: list) -> list:
    """
    Evaluates ALL rules against ALL nodes.
    Returns a sorted list of (severity, rule_id, action, node) tuples
    — highest severity first (priority queue ordering).
    """
    alerts = []
    for node in nodes:
        for rule in KNOWLEDGE_BASE:
            if rule["condition"](node):
                alerts.append((rule["severity"], rule["id"], rule, node))

    # Sort descending by severity so we act on the worst threats first
    alerts.sort(key=lambda x: x[0], reverse=True)
    return alerts


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 2 — MINIMAX WITH ALPHA-BETA PRUNING  (Proactive Defense)
#
#  Game model:
#    State  — simplified dict { node_id: status }
#    Red    — MAXIMIZER: tries to get as many nodes to ROOT_ACCESS as possible
#    Blue   — MINIMIZER: tries to keep as many nodes SECURE as possible
#    Depth  — 3 plies (Blue looks 3 moves ahead)
#
#  evaluate(state) — assigns a score to each board position
#    SECURE      → +10 (×3 for database)
#    EXPOSED     → +5
#    COMPROMISED → +2
#    ROOT_ACCESS → -5 (×3 for database)
#
#  minimax returns the best node_id for Blue to preemptively harden.
# ══════════════════════════════════════════════════════════════════════════════

STATUS_SCORE   = {"SECURE": 10, "EXPOSED": 5, "COMPROMISED": 2, "ROOT_ACCESS": -5}
DB_WEIGHT      = 3   # database node counts 3× in the evaluation
MINIMAX_DEPTH  = 3

def evaluate(state: dict, db_nodes: set) -> int:
    """Heuristic score for a given game state (Blue wants to maximize)."""
    score = 0
    for node_id, status in state.items():
        weight = DB_WEIGHT if node_id in db_nodes else 1
        score += STATUS_SCORE.get(status, 0) * weight
    return score


# ── Red move generator ─────────────────────────────────────────────────────
RED_KILL_CHAIN = {"SECURE": "EXPOSED", "EXPOSED": "COMPROMISED", "COMPROMISED": "ROOT_ACCESS"}

def red_successors(state: dict) -> list:
    """All states reachable by one Red Team move (advances one node one step)."""
    successors = []
    for node_id, status in state.items():
        if status in RED_KILL_CHAIN:
            new_state = dict(state)
            new_state[node_id] = RED_KILL_CHAIN[status]
            successors.append((node_id, new_state))
    return successors


# ── Blue move generator ────────────────────────────────────────────────────
def blue_successors(state: dict) -> list:
    """All states reachable by one Blue Team move (patch any non-SECURE node)."""
    successors = []
    for node_id, status in state.items():
        if status != "SECURE":
            new_state = dict(state)
            new_state[node_id] = "SECURE"
            successors.append((node_id, new_state))
    return successors


# ── Minimax core ───────────────────────────────────────────────────────────
def minimax(state: dict, depth: int, alpha: int, beta: int,
            is_maximizing: bool, db_nodes: set) -> int:
    """
    Minimax with Alpha-Beta pruning.
    Red  = maximizer (wants highest score = most compromise)
    Blue = minimizer (wants lowest score  = most SECURE)
    """
    if depth == 0:
        return evaluate(state, db_nodes)

    if is_maximizing:
        # Red Team's turn — pick the move that hurts Blue the most
        best = -999
        for _, succ in red_successors(state):
            val = minimax(succ, depth - 1, alpha, beta, False, db_nodes)
            best = max(best, val)
            alpha = max(alpha, best)
            if beta <= alpha:
                break   # β cut-off
        return best
    else:
        # Blue Team's turn — pick the move that limits Red the most
        best = 999
        for _, succ in blue_successors(state):
            val = minimax(succ, depth - 1, alpha, beta, True, db_nodes)
            best = min(best, val)
            beta = min(beta, best)
            if beta <= alpha:
                break   # α cut-off
        return best


def find_best_preemptive_target(nodes: list) -> str | None:
    """
    Runs Minimax from Blue's perspective to find the node that,
    if proactively hardened NOW, minimizes the worst-case future damage.
    Returns the node_id to preemptively patch/harden.
    """
    # Build the simplified state and identify DB nodes
    state   = {n["id"]: n["status"] for n in nodes}
    db_nodes = {n["id"] for n in nodes if n["os_type"] == "Database"}

    # Only consider vulnerable (non-SECURE) nodes as candidates
    candidates = [n["id"] for n in nodes if n["status"] != "SECURE"]
    if not candidates:
        return None  # Network is fully SECURE — nothing to do

    best_node  = None
    best_score = 999   # Blue minimizes, so start with +∞

    for node_id in candidates:
        # Simulate: Blue preemptively patches this node
        simulated = dict(state)
        simulated[node_id] = "SECURE"

        # Now ask Minimax: what's Red's best response from here?
        score = minimax(simulated, MINIMAX_DEPTH - 1, -999, 999, True, db_nodes)

        # Blue wants the move that leads to the LOWEST possible Red score
        if score < best_score:
            best_score = score
            best_node  = node_id

    return best_node


# ══════════════════════════════════════════════════════════════════════════════
#  LAYER 3 — EXECUTION  (sends commands to Member 1's backend)
# ══════def run_defender_ai():
    print_action("Initializing IDS (Intrusion Detection System)...")
    print_action(f"Knowledge Base loaded: {len(KNOWLEDGE_BASE)} production rules")
    print_action(f"Minimax depth: {MINIMAX_DEPTH} plies with Alpha-Beta pruning")
    print_action("WIN condition : All nodes SECURE for 5 consecutive polls")
    print_action("LOSE condition: Database reaches ROOT_ACCESS\n")

    patched_this_round: set = set()
    secure_streak = 0          # counts consecutive all-SECURE polls
    WIN_STREAK_NEEDED = 5      # how many clean polls = Blue Team wins

    while True:
        try:
            # ── Observe ─────────────────────────────────────────────────────
            response = requests.get(f"{API_URL}/nodes")
            if response.status_code != 200:
                print_action("Failed to fetch node states.")
                time.sleep(1)
                continue

            nodes = response.json()

            # ── Check lose condition: database at ROOT_ACCESS ────────────────
            db = next((n for n in nodes if n["os_type"] == "Database"), None)
            if db and db["status"] == "ROOT_ACCESS":
                print_action("\n💀 BLUE TEAM LOSES — Database has been fully compromised!")
                print_action("   RED TEAM wins. Simulation over.")
                break

            # ── Layer 1: Expert System — fire rules ─────────────────────────
            alerts = run_expert_system(nodes)

            if alerts:
                secure_streak = 0  # reset win counter when threats appear
                print_action(f"⚠️  Expert System: {len(alerts)} alert(s) detected")
                patched_this_round.clear()

                for severity, rule_id, rule, node in alerts:
                    node_id = node["id"]
                    if node_id in patched_this_round:
                        continue
                    print_action(
                        f"[RULE {rule_id} FIRED | sev={severity}] "
                        f"{rule['desc']} → {node_id} ({node['ip_address']})"
                    )
                    execute_action(rule, node)
                    patched_this_round.add(node_id)
                    time.sleep(0.2)

            else:
                # ── Layer 2: Minimax — proactive defense ─────────────────────
                target = find_best_preemptive_target(nodes)
                if target:
                    print_action(f"[MINIMAX] Network stable. Preemptive hardening → {target}")
                    r = requests.post(f"{API_URL}/patch", json={"target_node_id": target})
                    status = "✅" if r.status_code == 200 else "❌"
                    print_action(f"[MINIMAX] Preemptive patch {status} on {target}")
                    secure_streak = 0
                else:
                    # All nodes fully SECURE — increment win streak
                    secure_streak += 1
                    print_action(f"✅ All nodes SECURE. ({secure_streak}/{WIN_STREAK_NEEDED} clean polls)")
                    if secure_streak >= WIN_STREAK_NEEDED:
                        print_action("\n🏆 BLUE TEAM WINS — Network fully secured!")
                        print_action("   All nodes SECURE. Red Team has been repelled.")
                        break

        except requests.exceptions.ConnectionError:
            print_action("❌ Connection to ARMOR Command Server lost. Retrying in 3s...")
            time.sleep(3)
            continue

        time.sleep(1)  # poll every 1 second


if __name__ == "__main__":
    run_defender_ai()
