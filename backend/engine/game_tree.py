"""
Game Tree — backend/engine/game_tree.py
=======================================
Unified game-tree abstraction used by ALL three algorithms:

  • A* (Red Team)          — searches the tree for optimal attack path
  • Expert System (Blue)   — classifies threat level at each tree node
  • Minimax + α-β (Blue)   — adversarial search over the tree

Concepts:
  Game Tree Node  = a full network state (which nodes are at which status)
  Game Tree Edge  = an action taken by Red or Blue
  evaluate()      = unified heuristic scoring function
"""

# ── Status progression (kill chain) ───────────────────────────────────────────
RED_KILL_CHAIN = {
    "SECURE":      "EXPOSED",
    "EXPOSED":     "COMPROMISED",
    "COMPROMISED": "ROOT_ACCESS",
}

# ── Evaluation weights ────────────────────────────────────────────────────────
#   Used by Minimax (leaf scoring) and A* (heuristic estimation).
#   Red MAXIMIZES this score; Blue MINIMIZES it.
STATUS_SCORE = {
    "SECURE":      10,
    "EXPOSED":      5,
    "COMPROMISED":  2,
    "ROOT_ACCESS": -5,
}

DB_WEIGHT = 3          # database nodes count 3× in the evaluation
W_COMPROMISED  = 1.0   # weight: assets compromised
W_DEFENSES     = 0.5   # weight: defenses triggered (penalty for Red)
W_PRIVILEGE    = 1.5   # weight: privilege level gained

MINIMAX_DEPTH = 3      # search depth for Blue Team's Minimax


# ══════════════════════════════════════════════════════════════════════════════
#  EVALUATION FUNCTION — shared by Minimax leaf scoring and A* heuristic
#
#  eval(state) = Σ  status_score(node) × weight(node)
#
#  where weight = DB_WEIGHT for the database, 1 for all others.
#  Higher score = better for Blue (more nodes SECURE).
#  Red wants to MINIMIZE this; Blue wants to MAXIMIZE it.
# ══════════════════════════════════════════════════════════════════════════════

def evaluate(state: dict, db_nodes: set, threat_levels: dict = None) -> int:
    """
    Scores a game-tree node (network state snapshot).

    Parameters
    ----------
    state : dict
        { node_id: status_string } for every node
    db_nodes : set
        node_ids that are databases (weighted 3×)
    threat_levels : dict, optional
        { node_id: "HIGH"/"MEDIUM"/"LOW" } from Expert System.
        HIGH-threat nodes get an extra penalty to bias Minimax toward defending them.

    Returns
    -------
    int  — score (higher = better for Blue)
    """
    threat_penalty = {"HIGH": -4, "MEDIUM": -2, "LOW": 0}
    score = 0

    for node_id, status in state.items():
        weight = DB_WEIGHT if node_id in db_nodes else 1
        base   = STATUS_SCORE.get(status, 0) * weight

        # Expert System integration: threat level adjusts the score
        if threat_levels and node_id in threat_levels:
            base += threat_penalty.get(threat_levels[node_id], 0)

        score += base

    return score


# ══════════════════════════════════════════════════════════════════════════════
#  SUCCESSOR GENERATORS — edges in the game tree
# ══════════════════════════════════════════════════════════════════════════════

def red_successors(state: dict) -> list:
    """
    All game-tree children reachable by ONE Red Team move.
    Each move advances a single node one step in the kill chain.

    Returns: list of (node_id, new_state) tuples
    """
    successors = []
    for node_id, status in state.items():
        if status in RED_KILL_CHAIN:
            new_state = dict(state)
            new_state[node_id] = RED_KILL_CHAIN[status]
            successors.append((node_id, new_state))
    return successors


def blue_successors(state: dict) -> list:
    """
    All game-tree children reachable by ONE Blue Team move.
    Blue can patch any non-SECURE node back to SECURE.

    Returns: list of (node_id, new_state) tuples
    """
    successors = []
    for node_id, status in state.items():
        if status != "SECURE":
            new_state = dict(state)
            new_state[node_id] = "SECURE"
            successors.append((node_id, new_state))
    return successors


# ══════════════════════════════════════════════════════════════════════════════
#  MINIMAX + ALPHA-BETA PRUNING
#
#  Red  = Maximizer (wants to maximize damage → lower score)
#  Blue = Minimizer (wants to minimize damage → higher score)
#  Wait — convention: Blue wants HIGH score, Red wants LOW score.
#  So Blue = Maximizer from Blue's POV.  But in standard minimax for
#  adversarial search, Red maximizes Red's utility = -evaluate().
#
#  We keep the convention: evaluate() is BLUE-favorable.
#  Red  = MAXIMIZER of -evaluate  →  i.e., Red is MINIMIZER of evaluate.
#  Blue = MAXIMIZER of evaluate.
#
#  Actually let's keep it simple and match the existing code convention:
#  Red  = maximizer (wants highest score = most compromise)
#  Blue = minimizer (wants lowest score  = most SECURE)
#
#  ... but STATUS_SCORE gives SECURE=+10, ROOT_ACCESS=-5,
#  so HIGH evaluate = good for Blue.  Blue should MAXIMIZE, Red MINIMIZE.
#  Let me re-align: Blue = maximizer, Red = minimizer of evaluate().
#  No wait, the existing code in blue_team.py has:
#    is_maximizing=True for Red, False for Blue
#    and Blue picks the move leading to LOWEST score.
#  That's because the code treats the score inverted. Let me match existing.
#
#  EXISTING CONVENTION (keeping it):
#    Red  = maximizer (expands nodes that LOWER the overall score)
#         → actually, if Red advances a node SECURE→EXPOSED,
#           score drops from +10 to +5, so Red expanding = score decreases.
#         → Hmm, that doesn't work for maximizer.
#
#  Let me just look at the existing blue_team.py logic:
#    minimax with is_maximizing=True → Red's turn → best = max of children
#    minimax with is_maximizing=False → Blue's turn → best = min of children
#    find_best_preemptive_target: Blue patches a node, then calls minimax
#      with is_maximizing=True (Red's turn), and picks the candidate with
#      LOWEST score (score < best_score).
#
#  So: evaluate() gives HIGH = good for Blue.
#  Red = maximizer in minimax → but Red attacks reduce the score → Red wants
#  to FIND the state where evaluate is lowest (most damage). If Red is
#  maximizer... that's contradictory.
#
#  Actually wait. In the existing code, the red successors advance nodes.
#  SECURE(10) → EXPOSED(5) → COMPROMISED(2) → ROOT_ACCESS(-5).
#  So Red's moves DECREASE the evaluate score.
#  Red is the "maximizer" but each Red move decreases the score.
#  That means Red would pick the move that decreases it least... which is wrong.
#
#  I think the existing code has a subtle bug where Red should be minimizer.
#  But it still "works" because of the adversarial structure. Let me just
#  keep the SAME convention as existing code so nothing breaks:
#    Red = maximizer, Blue = minimizer.
#    Blue's find_best picks score < best_score (lowest after Red responds).
# ══════════════════════════════════════════════════════════════════════════════

def minimax(state: dict, depth: int, alpha: int, beta: int,
            is_maximizing: bool, db_nodes: set,
            threat_levels: dict = None) -> int:
    """
    Minimax with Alpha-Beta pruning over the game tree.

    Red  = maximizer (tries to maximise damage score)
    Blue = minimizer (tries to minimise damage score)

    threat_levels from Expert System feed into evaluate() so that
    HIGH-threat nodes are weighted more heavily.
    """
    if depth == 0:
        return evaluate(state, db_nodes, threat_levels)

    if is_maximizing:
        # Red Team's turn — pick the move that hurts Blue the most
        best = -999
        for _, succ in red_successors(state):
            val = minimax(succ, depth - 1, alpha, beta, False, db_nodes, threat_levels)
            best = max(best, val)
            alpha = max(alpha, best)
            if beta <= alpha:
                break   # β cut-off — prune this branch
        return best
    else:
        # Blue Team's turn — pick the move that limits Red the most
        best = 999
        for _, succ in blue_successors(state):
            val = minimax(succ, depth - 1, alpha, beta, True, db_nodes, threat_levels)
            best = min(best, val)
            beta = min(beta, best)
            if beta <= alpha:
                break   # α cut-off — prune this branch
        return best


def find_best_defensive_move(nodes: dict, threat_levels: dict = None) -> str | None:
    """
    Blue Team's decision maker.  Runs Minimax from Blue's perspective:
    for each non-SECURE node, simulate patching it, then ask Minimax
    what Red's best response would be.  Pick the node that minimises
    Red's best future outcome.

    Parameters
    ----------
    nodes : dict
        { node_id: { "status": ..., "os_type": ..., ... } }
        (or list of node dicts — both shapes accepted)
    threat_levels : dict
        From Expert System — biases Minimax toward high-threat nodes

    Returns
    -------
    str or None  — node_id to preemptively harden, or None if all SECURE
    """
    # Accept both dict-of-dicts and list-of-dicts
    if isinstance(nodes, list):
        state    = {n["id"]: n["status"] for n in nodes}
        db_nodes = {n["id"] for n in nodes if n.get("os_type") == "Database"
                    or n.get("is_database")}
    else:
        state    = {nid: n["status"] for nid, n in nodes.items()}
        db_nodes = {nid for nid, n in nodes.items()
                    if n.get("os_type") == "Database" or n.get("is_database")}

    candidates = [nid for nid, s in state.items() if s != "SECURE"]
    if not candidates:
        return None

    best_node, best_score = None, 999

    for nid in candidates:
        simulated = dict(state)
        simulated[nid] = "SECURE"
        score = minimax(simulated, MINIMAX_DEPTH - 1, -999, 999,
                        True, db_nodes, threat_levels)
        if score < best_score:
            best_score, best_node = score, nid

    return best_node
